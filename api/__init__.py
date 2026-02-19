"""Steam API module for Arma 3 server content management.

This module provides a facade for Steam CDN operations with automatic
retry and session reset capabilities.

Public API:
    - SteamSession: Session class with automatic retry/reset and download methods
    - CDLC_IDS: Mapping of CDLC names to depot IDs

Example usage:
    session = SteamSession.login(username, password, config=config)
    session.download_depot(233781)
    session.download_workshop(843425103)
"""

from .config import CDLC_IDS, DEFAULT_CONFIG, ARMA3_SERVER_APP_ID
from .session import SteamSession

__all__ = [
    "SteamSession",
    "CDLC_IDS",
    "DEFAULT_CONFIG",
    "ARMA3_SERVER_APP_ID",
]
