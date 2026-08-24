use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use regex::Regex;
use steamroom::client::{LoggedIn, SteamClient};
use tracing::info;

use crate::keys;
use crate::steam;

const USER_AGENT: &str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36";

/// Loads an Arma 3 Launcher `.html` preset (local path or URL), downloads every
/// referenced workshop item, and syncs their keys into `keys_dir`.
pub async fn load(
    client: &SteamClient<LoggedIn>,
    source: &str,
    workshop_dir: &Path,
    keys_dir: &Path,
) -> Result<Vec<PathBuf>> {
    let html = if source.starts_with("http") {
        info!(url = source, "fetching mod preset");
        let http = reqwest::Client::builder().user_agent(USER_AGENT).build()?;
        http.get(source)
            .send()
            .await
            .context("fetching preset URL")?
            .error_for_status()
            .context("preset URL returned an error")?
            .text()
            .await
            .context("reading preset response body")?
    } else {
        std::fs::read_to_string(source).with_context(|| format!("reading preset {source}"))?
    };

    let regex = Regex::new(r#"filedetails/\?id=(\d+)""#)?;
    let mut mod_dirs = Vec::new();
    for capture in regex.captures_iter(&html) {
        let workshop_id: u64 = capture[1].parse()?;
        let dest = workshop_dir.join(workshop_id.to_string());
        steam::workshop::download_item(client, workshop_id, &dest).await?;
        keys::sync(&dest, keys_dir)?;
        mod_dirs.push(dest);
    }
    Ok(mod_dirs)
}
