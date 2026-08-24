use std::path::{Path, PathBuf};

use anyhow::{Context, Result};

use crate::keys;

/// Lists immediate subdirectories of `dir` (each is treated as a mod) and syncs
/// their `.bikey` files into `keys_dir`.
pub fn scan(dir: &Path, keys_dir: &Path) -> Result<Vec<PathBuf>> {
    if !dir.is_dir() {
        return Ok(Vec::new());
    }

    let mut mods = Vec::new();
    for entry in std::fs::read_dir(dir).with_context(|| format!("reading {}", dir.display()))? {
        let entry = entry?;
        let path = entry.path();
        if path.is_dir() {
            keys::sync(&path, keys_dir)?;
            mods.push(path);
        }
    }
    mods.sort();
    Ok(mods)
}
