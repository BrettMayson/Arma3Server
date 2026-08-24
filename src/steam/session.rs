use anyhow::{Context, Result, bail};
use steamroom::client::{LoggedIn, SteamClient};
use steamroom_client::login::{CredentialsLoginFlow, LoginBuilder};
use tracing::info;

use crate::error::AppError;

/// Logs in to Steam with a username/password. Accounts with Steam Guard
/// enabled are rejected — this mirrors the original launcher's requirement
/// that Steam Guard be disabled for unattended server automation.
pub async fn login(username: &str, password: &str) -> Result<SteamClient<LoggedIn>> {
    info!(user = username, "logging in to Steam");

    let flow = LoginBuilder::new()
        .device_name("arma3server")
        .with_credentials(username, password)
        .begin()
        .await
        .context("failed to begin Steam login")?;

    let client = match flow {
        CredentialsLoginFlow::Approved(approved) => approved
            .finish()
            .await
            .context("failed to complete Steam login")?,
        CredentialsLoginFlow::NeedsConfirmation(_) => {
            bail!(AppError::SteamGuardRequired)
        }
        _ => bail!("unsupported Steam login confirmation flow"),
    };

    info!("logged in to Steam");
    Ok(client)
}
