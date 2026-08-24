use indicatif::{ProgressBar, ProgressStyle};
use owo_colors::OwoColorize;
use steamroom_client::event::DownloadEvent;
use tokio::sync::mpsc::UnboundedReceiver;
use tokio::task::JoinHandle;

/// Prints a small startup banner.
pub fn banner() {
    println!(
        "{} {}",
        "arma3server".bold().cyan(),
        format!("v{}", env!("CARGO_PKG_VERSION")).dimmed()
    );
}

pub struct DownloadProgress {
    handle: JoinHandle<()>,
}

impl DownloadProgress {
    pub fn finish(self) {
        // The event channel closes when the download job's sender drops,
        // which ends the render loop; just let the task wind down.
        drop(self.handle);
    }
}

/// Renders a progress bar driven by `DownloadEvent`s from a depot/workshop job.
pub fn spawn_download_progress(
    folder: std::path::PathBuf,
    mut events: UnboundedReceiver<DownloadEvent>,
) -> DownloadProgress {
    let handle = tokio::spawn(async move {
        let bar = ProgressBar::new(0);
        bar.set_style(
            ProgressStyle::with_template(
                "{spinner:.cyan} [{elapsed_precise}] [{bar:30.cyan/blue}] {bytes}/{total_bytes} {msg}",
            )
            .unwrap_or_else(|_| ProgressStyle::default_bar())
            .progress_chars("=> "),
        );

        let mut downloaded = (0, 0);
        let mut skipped = (0, 0);
        let mut removed = (0, 0);

        while let Some(event) = events.recv().await {
            match event {
                DownloadEvent::DownloadStarted { total_bytes, .. } => {
                    bar.set_length(total_bytes);
                }
                DownloadEvent::FileStarted { filename } => {
                    bar.set_message(filename);
                }
                DownloadEvent::ChunkCompleted { bytes } => {
                    bar.inc(bytes);
                    downloaded.1 += bytes;
                }
                DownloadEvent::FileCompleted { .. } => {
                    downloaded.0 += 1;
                }
                DownloadEvent::DepotProgress {
                    completed_bytes,
                    total_bytes,
                } => {
                    bar.set_length(total_bytes);
                    bar.set_position(completed_bytes);
                }
                DownloadEvent::FileSkipped { filename } => {
                    let size = {
                        let metadata = std::fs::metadata(folder.join(filename.replace("\\", "/")));
                        match metadata {
                            Ok(m) => m.len(),
                            Err(e) => {
                                tracing::warn!("failed to get file size for {filename}: {e}");
                                0
                            }
                        }
                    };
                    skipped.0 += 1;
                    skipped.1 += size;
                    bar.set_message("");
                    bar.inc(size);
                }
                DownloadEvent::FileRemoved { .. } => {
                    removed.0 += 1;
                }
                _ => {}
            }
        }
        bar.println(format!(
            "Download complete: {} files ({}) downloaded, {} files ({}) skipped, {} files removed",
            downloaded.0,
            indicatif::HumanBytes(downloaded.1),
            skipped.0,
            indicatif::HumanBytes(skipped.1),
            removed.0,
        ));
        bar.finish_and_clear();
    });

    DownloadProgress { handle }
}
