"""PACE OAuth2 client-credentials helper for discovery API calls."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


class PaceAuthError(RuntimeError):
    """Raised when PACE token acquisition fails."""


def get_pace_access_token(*, force_refresh: bool = False) -> str:
    """Return a cached PACE access token, refreshing via client credentials."""
    now = time.time()
    cached = _token_cache.get("access_token")
    expires_at = float(_token_cache.get("expires_at") or 0.0)
    if (
        not force_refresh
        and isinstance(cached, str)
        and cached
        and now < expires_at - 30
    ):
        return cached

    settings = get_settings()
    token_url = (settings.pace_token_url or "").strip()
    client_id = (settings.pace_client_id or "").strip()
    client_secret = (settings.pace_client_secret or "").strip()
    scope = (settings.pace_scope or "").strip() or None

    if not token_url or not client_id or not client_secret:
        raise PaceAuthError(
            "PACE OAuth is not configured. Set DICE_PACE_TOKEN_URL, "
            "DICE_PACE_CLIENT_ID, and DICE_PACE_CLIENT_SECRET."
        )

    data: dict[str, str] = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if scope:
        data["scope"] = scope

    try:
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = client.post(token_url, data=data)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise PaceAuthError(f"PACE token request failed: {exc}") from exc
    except ValueError as exc:
        raise PaceAuthError(f"PACE token response was not JSON: {exc}") from exc

    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise PaceAuthError("PACE token response missing access_token.")

    expires_in = float(payload.get("expires_in") or 3600)
    _token_cache["access_token"] = access_token
    _token_cache["expires_at"] = now + expires_in
    logger.info("Cached PACE access token (expires_in=%s)", expires_in)
    return access_token


def reset_pace_token_cache() -> None:
    _token_cache["access_token"] = None
    _token_cache["expires_at"] = 0.0
