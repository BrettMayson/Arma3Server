mod config;
mod error;
mod keys;
mod launch;
mod mods;
mod steam;
mod ui;

use anyhow::{Context, Result};
use std::path::PathBuf;
use tokio::process::Command;
use tracing::info;
use tracing_subscriber::EnvFilter;

use config::Config;

const SERVER_DIR: &str = "./server";

const DEFAULT_CONTENT_DEPOT: u32 = 233781;
const LINUX_SERVER_DEPOT: u32 = 233783;
const PROFILING_DEPOT: u32 = 233785;

fn cdlc_depot_id(name: &str) -> Option<u32> {
    Some(match name {
        "csla" => 233793,
        "gm" => 233792,
        "vn" => 233794,
        "ws" => 233795,
        "spe" => 233788,
        "rf" => 233799,
        "ef" => 233798,
        _ => return None,
    })
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .without_time()
        .init();

    ui::banner();

    let config = Config::load().context("loading configuration")?;
    let server_dir = PathBuf::from(SERVER_DIR).canonicalize().expect("server dir should exist");
    let keys_dir = server_dir.join("keys");

    keys::prepare(&keys_dir, config.server.clear_keys)?;

    let mut mods = Vec::new();

    if !config.server.skip_install {
        let client = steam::session::login(&config.steam.user, &config.steam.password).await?;
        let branch = &config.steam.branch;
        info!(branch, "using Steam branch");

        steam::depot::download(&client, DEFAULT_CONTENT_DEPOT, branch, &server_dir)
            .await
            .context("downloading default content depot")?;
        steam::depot::download(&client, LINUX_SERVER_DEPOT, branch, &server_dir)
            .await
            .context("downloading Linux server depot")?;
        if config.server.binary.contains("profiling") {
            steam::depot::download(&client, PROFILING_DEPOT, branch, &server_dir)
                .await
                .context("downloading profiling depot")?;
        }

        for cdlc in &config.server.cdlc {
            let Some(depot_id) = cdlc_depot_id(cdlc) else {
                anyhow::bail!("unknown CDLC flag: {cdlc}");
            };
            info!(cdlc, "downloading CDLC");
            steam::depot::download(&client, depot_id, "creatordlc", &server_dir)
                .await
                .with_context(|| format!("downloading CDLC {cdlc}"))?;
        }

        if !config.mods.preset.is_empty() {
            let workshop_dir = server_dir.join("workshop");
            mods.extend(
                mods::preset::load(&client, &config.mods.preset, &workshop_dir, &keys_dir).await?,
            );
        }
    } else if !config.mods.preset.is_empty() {
        // Preset mods still require Steam even when server install is skipped.
        let client = steam::session::login(&config.steam.user, &config.steam.password).await?;
        let workshop_dir = server_dir.join("workshop");
        mods.extend(
            mods::preset::load(&client, &config.mods.preset, &workshop_dir, &keys_dir).await?,
        );
    }

    if config.mods.local {
        let local_mods_dir = server_dir.join("mods");
        mods.extend(mods::local::scan(&local_mods_dir, &keys_dir)?);
    }

    let server_mods_dir = server_dir.join("servermods");
    let server_mods = mods::local::scan(&server_mods_dir, &keys_dir)?;

    let plan = launch::build(&config, &mods, &server_mods, &server_dir)?;

    for args in &plan.headless_args {
        info!(?args, "launching headless client");
        Command::new(&config.server.binary)
            .args(args)
            .current_dir(&server_dir)
            .spawn()
            .context("spawning headless client")?;
    }

    let server_bin = server_dir.join(&config.server.binary);

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = std::fs::metadata(&server_bin)
            .with_context(|| format!("reading metadata for {}", config.server.binary))?
            .permissions();
        perms.set_mode(0o755);
        std::fs::set_permissions(&server_bin, perms)
            .with_context(|| format!("setting permissions for {}", config.server.binary))?;
    }

    info!(args = ?plan.main_args, "launching Arma 3 server");
    let status = Command::new(server_bin)
        .args(&plan.main_args)
        .current_dir(server_dir)
        .status()
        .await
        .context("launching Arma 3 server")?;

    std::process::exit(status.code().unwrap_or(1));
}
