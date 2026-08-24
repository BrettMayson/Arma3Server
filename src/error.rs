use thiserror::Error;

/// Errors that need to be matched on by callers (everything else flows through `anyhow`).
#[derive(Debug, Error)]
pub enum AppError {
    #[error(
        "Steam Guard is enabled for this account. Disable Steam Guard (or use an account without 2FA) for unattended server automation."
    )]
    SteamGuardRequired,
}
