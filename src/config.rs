use serde::{Deserialize, Serialize};

/// Steam account and branch settings.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct SteamConfig {
    pub user: String,
    pub password: String,
    pub branch: String,
    pub branch_password: String,
}

impl Default for SteamConfig {
    fn default() -> Self {
        Self {
            user: String::new(),
            password: String::new(),
            branch: "public".to_string(),
            branch_password: String::new(),
        }
    }
}

/// Arma 3 server process settings.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ServerConfig {
    pub binary: String,
    pub config: String,
    pub profile: String,
    pub world: String,
    pub limit_fps: u32,
    pub params: String,
    pub port: u16,
    pub skip_install: bool,
    pub clear_keys: bool,
    pub cdlc: Vec<String>,
}

impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            binary: "./arma3server_x64".to_string(),
            config: "main.cfg".to_string(),
            profile: "main".to_string(),
            world: "empty".to_string(),
            limit_fps: 1000,
            params: String::new(),
            port: 2302,
            skip_install: false,
            clear_keys: true,
            cdlc: Vec::new(),
        }
    }
}

/// Mod loading settings.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ModsConfig {
    pub local: bool,
    pub preset: String,
}

impl Default for ModsConfig {
    fn default() -> Self {
        Self {
            local: true,
            preset: String::new(),
        }
    }
}

/// Headless client spawning settings.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct HeadlessConfig {
    pub clients: u32,
    pub profile: String,
}

impl Default for HeadlessConfig {
    fn default() -> Self {
        Self {
            clients: 0,
            // `$profile`/`$i`/`$ii` are substituted at launch time.
            profile: "$profile-hc-$i".to_string(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct Config {
    pub steam: SteamConfig,
    pub server: ServerConfig,
    pub mods: ModsConfig,
    pub headless: HeadlessConfig,
}

impl Config {
    /// Load config layering an optional TOML file under `ARMA3_*` env var overrides.
    pub fn load() -> anyhow::Result<Self> {
        use figment::Figment;
        use figment::providers::{Env, Format, Serialized, Toml};

        let toml_path = std::env::var("ARMA3_CONFIG_FILE")
            .unwrap_or_else(|_| "./config.toml".to_string());

        let mut figment = Figment::from(Serialized::defaults(Config::default()));
        if std::path::Path::new(&toml_path).exists() {
            figment = figment.merge(Toml::file(&toml_path));
        }
        figment = figment.merge(Env::prefixed("ARMA3_").split("__"));

        let mut config: Config = figment.extract()?;

        // `ARMA3_SERVER__CDLC` is a flat comma-separated list rather than a
        // TOML array, so figment's env parsing can't populate it reliably.
        if let Ok(raw) = std::env::var("ARMA3_SERVER__CDLC") {
            config.server.cdlc = raw
                .split(',')
                .map(|s| s.trim().to_lowercase())
                .filter(|s| !s.is_empty())
                .collect();
        }

        Ok(config)
    }
}
