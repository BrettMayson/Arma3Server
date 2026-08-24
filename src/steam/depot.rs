use std::path::Path;
use std::sync::Arc;

use anyhow::{Context, Result, bail};
use steamroom::cdn::{CdnClient, CdnServerPool};
use steamroom::client::{LoggedIn, SteamClient};
use steamroom::depot::manifest::DepotManifest;
use steamroom::depot::{CellId, DepotId};
use steamroom_client::depot_config::DepotConfig;
use steamroom_client::download::{CdnChunkFetcher, DepotJob};
use steamroom_client::manifest::ManifestCache;
use tracing::{debug, info, warn};

use super::{APP_ID, decompress_manifest};

/// Downloads the given depot (on `branch`) into `install_dir`.
pub async fn download(
    client: &SteamClient<LoggedIn>,
    depot_id: u32,
    branch: &str,
    install_dir: &Path,
) -> Result<()> {
    let depot_id = DepotId(depot_id);

    let details = client
        .app_details(APP_ID)
        .await
        .context("fetching Arma 3 app info from Steam")?;

    let manifest_id = details
        .depot(depot_id)
        .and_then(|d| d.manifest(branch))
        .map(|m| m.manifest_id)
        .with_context(|| format!("no manifest found for depot {} on branch {branch}", depot_id.0))?;

    let mut depot_config = DepotConfig::load(install_dir);
    let up_to_date = depot_config.is_installing(depot_id).is_none()
        && depot_config
            .get_installed(depot_id)
            .is_some_and(|(installed, _)| installed == manifest_id);
    if up_to_date {
        info!(
            depot = depot_id.0,
            manifest = manifest_id.0,
            "depot already up to date, skipping download"
        );
        return Ok(());
    }
    if let Some(interrupted) = depot_config.is_installing(depot_id) {
        warn!(
            depot = depot_id.0,
            manifest = interrupted.0,
            "previous install of this depot was interrupted, re-downloading"
        );
    }

    info!(depot = depot_id.0, manifest = manifest_id.0, branch, "downloading depot");

    let depot_key = client
        .get_depot_decryption_key(depot_id, APP_ID)
        .await
        .context("fetching depot decryption key")?;

    let cdn_servers = client
        .get_cdn_servers(CellId(0), Some(20))
        .await
        .context("fetching CDN server list")?;
    if cdn_servers.is_empty() {
        bail!("Steam returned no CDN servers");
    }
    let cdn_server = cdn_servers[0].clone();
    let cdn_pool = CdnServerPool::new(cdn_servers);
    let cdn = CdnClient::new().context("building CDN HTTP client")?;

    let request_code = client
        .get_manifest_request_code(APP_ID, depot_id, manifest_id, Some(branch), None)
        .await
        .unwrap_or(None)
        .unwrap_or(0);

    let cdn_auth_token = client
        .get_cdn_auth_token(APP_ID, depot_id, &cdn_server.host)
        .await
        .ok()
        .and_then(|t| t.token);

    let manifest_cache = ManifestCache::new(ManifestCache::default_path());
    let manifest_bytes = if let Some(cached) = manifest_cache.load(depot_id, manifest_id) {
        debug!("using cached manifest for depot {}", depot_id.0);
        cached
    } else {
        info!("downloading manifest...");
        let raw = cdn
            .download_manifest_pooled(
                &cdn_pool,
                depot_id,
                manifest_id,
                request_code,
                cdn_auth_token.as_deref(),
            )
            .await
            .context("downloading manifest from CDN")?;
        let decompressed = decompress_manifest(&raw)?;
        let _ = manifest_cache.save(depot_id, manifest_id, &decompressed, &raw);
        decompressed
    };

    let mut manifest = DepotManifest::parse(&manifest_bytes).context("parsing depot manifest")?;
    if manifest.filenames_encrypted {
        manifest
            .decrypt_filenames(&depot_key)
            .context("decrypting manifest filenames")?;
    }

    std::fs::create_dir_all(install_dir)
        .with_context(|| format!("creating install dir {}", install_dir.display()))?;

    depot_config.set_installing(depot_id, manifest_id, &depot_key);
    depot_config
        .save(install_dir)
        .context("saving depot install state")?;

    let (event_tx, event_rx) = tokio::sync::mpsc::unbounded_channel();
    let fetcher = CdnChunkFetcher::new(cdn, cdn_pool, cdn_auth_token);
    let job = DepotJob::builder()
        .depot_id(depot_id)
        .depot_key(depot_key.clone())
        .install_dir(install_dir.to_path_buf())
        .verify(true)
        .event_sender(event_tx)
        .build()
        .context("building depot download job")?;

    let progress = crate::ui::spawn_download_progress(install_dir.to_path_buf(), event_rx);
    let stats = job
        .download(&manifest, Arc::new(fetcher))
        .await
        .map_err(|e| anyhow::anyhow!("downloading depot content: {e}"))?;
    progress.finish();

    depot_config.set_installed(depot_id, manifest_id, &depot_key);
    depot_config
        .save(install_dir)
        .context("saving depot install state")?;

    info!(
        files = stats.files_completed,
        bytes = stats.bytes_downloaded,
        "depot download complete"
    );
    Ok(())
}
