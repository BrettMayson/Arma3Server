use std::path::Path;
use std::sync::Arc;

use anyhow::{Context, Result, bail};
use steamroom::cdn::{CdnClient, CdnServerPool};
use steamroom::client::{LoggedIn, SteamClient};
use steamroom::depot::manifest::DepotManifest;
use steamroom::depot::{AppId, CellId, DepotId, ManifestId};
use steamroom_client::depot_config::DepotConfig;
use steamroom_client::download::{CdnChunkFetcher, DepotJob};
use tracing::{info, warn};

use super::{APP_ID, decompress_manifest};

/// Downloads a single Steam Workshop item into `install_dir`.
pub async fn download_item(
    client: &SteamClient<LoggedIn>,
    workshop_id: u64,
    install_dir: &Path,
) -> Result<()> {
    info!(workshop_id, "fetching workshop item details");

    let req = steamroom::generated::CPublishedFileGetDetailsRequest {
        publishedfileids: vec![workshop_id],
        includechildren: Some(true),
        ..Default::default()
    };
    let resp = client
        .call_service_method(
            "PublishedFile.GetDetails#1",
            &prost::Message::encode_to_vec(&req),
        )
        .await
        .context("requesting workshop item details")?;
    let details: steamroom::generated::CPublishedFileGetDetailsResponse =
        resp.decode().context("decoding workshop item details")?;

    let item = details
        .publishedfiledetails
        .first()
        .with_context(|| format!("no details returned for workshop item {workshop_id}"))?;

    let title = item.title.as_deref().unwrap_or("(untitled)");
    let hcontent = item.hcontent_file.unwrap_or(0);
    let consumer_app = item.consumer_appid.unwrap_or(APP_ID.0);

    info!(workshop_id, title, "downloading workshop item");

    if hcontent == 0 {
        info!(workshop_id, "no downloadable content for this workshop item");
        return Ok(());
    }

    let app_id = AppId(consumer_app);
    let depot_id = DepotId(consumer_app);
    let manifest_id = ManifestId(hcontent);

    let mut depot_config = DepotConfig::load(install_dir);
    let up_to_date = depot_config.is_installing(depot_id).is_none()
        && depot_config
            .get_installed(depot_id)
            .is_some_and(|(installed, _)| installed == manifest_id);
    if up_to_date {
        info!(workshop_id, "workshop item already up to date, skipping download");
        return Ok(());
    }
    if let Some(interrupted) = depot_config.is_installing(depot_id) {
        warn!(
            workshop_id,
            manifest = interrupted.0,
            "previous install of this workshop item was interrupted, re-downloading"
        );
    }

    let depot_key = client
        .get_depot_decryption_key(depot_id, app_id)
        .await
        .context("fetching workshop depot decryption key")?;
    let cdn_servers = client
        .get_cdn_servers(CellId(0), Some(5))
        .await
        .context("fetching CDN server list")?;
    if cdn_servers.is_empty() {
        bail!("Steam returned no CDN servers");
    }
    let cdn_pool = CdnServerPool::new(cdn_servers);
    let cdn = CdnClient::new().context("building CDN HTTP client")?;

    let request_code = client
        .get_manifest_request_code(app_id, depot_id, manifest_id, None, None)
        .await
        .unwrap_or(None)
        .unwrap_or(0);

    let manifest_data = cdn
        .download_manifest_pooled(&cdn_pool, depot_id, manifest_id, request_code, None)
        .await
        .context("downloading workshop manifest from CDN")?;
    let manifest_bytes = decompress_manifest(&manifest_data)?;
    let mut manifest = DepotManifest::parse(&manifest_bytes).context("parsing workshop manifest")?;
    if manifest.filenames_encrypted {
        manifest
            .decrypt_filenames(&depot_key)
            .context("decrypting workshop manifest filenames")?;
    }

    std::fs::create_dir_all(install_dir)
        .with_context(|| format!("creating workshop dir {}", install_dir.display()))?;

    depot_config.set_installing(depot_id, manifest_id, &depot_key);
    depot_config
        .save(install_dir)
        .context("saving workshop item install state")?;

    let (event_tx, event_rx) = tokio::sync::mpsc::unbounded_channel();
    let fetcher = CdnChunkFetcher::new(cdn, cdn_pool, None);
    let job = DepotJob::builder()
        .depot_id(depot_id)
        .depot_key(depot_key.clone())
        .install_dir(install_dir.to_path_buf())
        .verify(true)
        .event_sender(event_tx)
        .build()
        .context("building workshop download job")?;

    let progress = crate::ui::spawn_download_progress(install_dir.to_path_buf(), event_rx);
    let stats = job
        .download(&manifest, Arc::new(fetcher))
        .await
        .map_err(|e| anyhow::anyhow!("downloading workshop content: {e}"))?;
    progress.finish();

    depot_config.set_installed(depot_id, manifest_id, &depot_key);
    depot_config
        .save(install_dir)
        .context("saving workshop item install state")?;

    info!(
        workshop_id,
        files = stats.files_completed,
        bytes = stats.bytes_downloaded,
        "workshop item download complete"
    );
    Ok(())
}
