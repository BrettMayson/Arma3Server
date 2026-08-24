pub mod depot;
pub mod session;
pub mod workshop;

use steamroom::depot::AppId;

/// Arma 3's Steam app ID.
pub const APP_ID: AppId = AppId(233780);

/// Manifest data from the CDN is zip-compressed; unwrap it if so.
pub(crate) fn decompress_manifest(data: &[u8]) -> anyhow::Result<Vec<u8>> {
    if data.len() > 2 && data[0] == 0x50 && data[1] == 0x4B {
        let cursor = std::io::Cursor::new(data);
        let mut archive = zip::ZipArchive::new(cursor)?;
        let mut file = archive.by_index(0)?;
        let mut buf = Vec::new();
        std::io::Read::read_to_end(&mut file, &mut buf)?;
        Ok(buf)
    } else {
        Ok(data.to_vec())
    }
}
