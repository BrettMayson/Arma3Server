use std::path::Path;

use anyhow::{Context, Result};
use tracing::debug;
use walkdir::WalkDir;

/// Recursively finds `*.bikey` files under `mod_dir` and copies them into `keys_dir`.
pub fn sync(mod_dir: &Path, keys_dir: &Path) -> Result<()> {
    for entry in WalkDir::new(mod_dir)
        .into_iter()
        .filter_map(std::result::Result::ok)
    {
        let path = entry.path();
        if path.is_file()
            && path
                .extension()
                .is_some_and(|ext| ext.eq_ignore_ascii_case("bikey"))
        {
            let file_name = path.file_name().context("bikey file has no name")?;
            let dest = keys_dir.join(file_name);
            std::fs::copy(path, &dest)
                .with_context(|| format!("copying key {} -> {}", path.display(), dest.display()))?;
            debug!(key = %path.display(), "copied key");
        }
    }
    Ok(())
}

/// Clears (if configured) and (re)creates the server's `keys/` directory.
pub fn prepare(keys_dir: &Path, clear: bool) -> Result<()> {
    if clear && keys_dir.is_dir() {
        std::fs::create_dir_all("/tmp/keys").context("creating /tmp/keys")?;
        let a3_key = keys_dir.join("a3.bikey");
        if a3_key.is_file() {
            std::fs::copy(&a3_key, "/tmp/keys/a3.bikey")
                .context("copying a3.bikey to /tmp/keys")?;
        }
        std::fs::remove_dir_all(keys_dir)
            .with_context(|| format!("clearing keys dir {}", keys_dir.display()))?;
    }
    if !keys_dir.is_dir() {
        std::fs::create_dir_all(keys_dir)
            .with_context(|| format!("creating keys dir {}", keys_dir.display()))?;
        let a3_key = keys_dir.join("a3.bikey");
        if !a3_key.is_file() && Path::new("/tmp/keys/a3.bikey").is_file() {
            std::fs::copy("/tmp/keys/a3.bikey", &a3_key)
                .context("copying a3.bikey back from /tmp/keys")?;
        }
        debug!(dir = %keys_dir.display(), "created keys dir");
    }
    Ok(())
}
