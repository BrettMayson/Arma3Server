use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use regex::Regex;
use tracing::info;

use crate::config::Config;

/// A fully-built launch plan: main server args plus one arg list per headless client.
pub struct LaunchPlan {
    pub main_args: Vec<String>,
    pub headless_args: Vec<Vec<String>>,
}

fn mod_arg(flag: &str, mods: &[PathBuf]) -> String {
    let joined = mods
        .iter()
        .map(|p| p.display().to_string())
        .collect::<Vec<_>>()
        .join(";");
    format!("-{flag}={joined}")
}

/// Substitutes `$profile`/`$i`/`$ii` in a headless client profile-name template.
/// `$ii` must be substituted before `$i` since it shares its prefix.
fn substitute_hc_profile(template: &str, profile: &str, i: u32) -> String {
    template
        .replace("$ii", &(i + 1).to_string())
        .replace("$profile", profile)
        .replace("$i", &i.to_string())
}

/// Builds the main server + headless client launch arguments, mirroring the
/// original Python launcher's command construction.
pub fn build(
    config: &Config,
    mods: &[PathBuf],
    server_mods: &[PathBuf],
    server_dir: &Path,
) -> Result<LaunchPlan> {
    let mut base_args = vec![
        format!("-limitFPS={}", config.server.limit_fps),
        format!("-world={}", config.server.world),
    ];
    base_args.extend(config.server.params.split_whitespace().map(str::to_string));
    base_args.push(mod_arg("mod", mods));
    for cdlc in &config.server.cdlc {
        base_args.push(format!("-mod={cdlc}"));
    }

    let mut main_args = base_args.clone();
    let mut headless_args = Vec::new();

    if config.headless.clients > 0 {
        let config_path = server_dir
            .join("configs")
            .join(&config.server.config);
        let data = std::fs::read_to_string(&config_path)
            .with_context(|| format!("reading server config {}", config_path.display()))?;

        let kv_regex = Regex::new(r"(?m)(.+?)(?:\s+)?=(?:\s+)?(.+?)(?:$|/|;)")?;
        let mut config_values = std::collections::HashMap::new();
        for cap in kv_regex.captures_iter(&data) {
            config_values.insert(cap[1].trim().to_lowercase(), cap[2].trim().to_string());
        }

        let mut patched = data;
        if !config_values.contains_key("headlessclients[]") {
            patched.push_str("\nheadlessclients[] = {\"127.0.0.1\"};\n");
        }
        if !config_values.contains_key("localclient[]") {
            patched.push_str("\nlocalclient[] = {\"127.0.0.1\"};\n");
        }

        let tmp_config = std::env::temp_dir().join("arma3.cfg");
        std::fs::write(&tmp_config, &patched)
            .with_context(|| format!("writing patched headless config {}", tmp_config.display()))?;

        main_args.push(format!("-config={}", tmp_config.display()));

        let mut client_args = base_args.clone();
        client_args.push(format!("-config={}", tmp_config.display()));
        client_args.push("-client".to_string());
        client_args.push("-connect=127.0.0.1".to_string());
        client_args.push(format!("-port={}", config.server.port));
        if let Some(password) = config_values.get("password") {
            client_args.push(format!("-password={password}"));
        }

        for i in 0..config.headless.clients {
            let name = substitute_hc_profile(&config.headless.profile, &config.server.profile, i);
            let mut args = client_args.clone();
            args.push(format!("-name={name}"));
            info!(client = i, name, "prepared headless client");
            headless_args.push(args);
        }
    } else {
        main_args.push(format!(
            "-config={}",
            server_dir.join("configs").join(&config.server.config).display()
        ));
    }

    main_args.push(format!("-port={}", config.server.port));
    main_args.push(format!("-name={}", config.server.profile));
    main_args.push(format!(
        "-profiles={}",
        server_dir.join("configs").join("profiles").display()
    ));

    if !server_mods.is_empty() {
        main_args.push(mod_arg("serverMod", server_mods));
    }

    Ok(LaunchPlan {
        main_args,
        headless_args,
    })
}
