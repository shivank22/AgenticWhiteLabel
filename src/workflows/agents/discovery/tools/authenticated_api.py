"""Authenticated REST API tool.

Calls protected endpoints with a Bearer token supplied at runtime through
config["configurable"]["bearer_token"] (or fallback env config).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from langchain_core.tools import tool

try:
    from langchain.tools import ToolRuntime  # type: ignore[import]
except ImportError:  # pragma: no cover - version skew
    from langgraph.prebuilt.tool_node import ToolRuntime  # type: ignore[import]

from src.config.settings import get_settings
from src.io.api_results import persist_successful_api_result
from src.workflows.agents.discovery.tools.pace_auth import (
    PaceAuthError,
    get_pace_access_token,
)
from src.workflows.tools.hitl import request_tool_review, review_tool_call

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_ALLOWED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})


def _edited_arg_mapping(edited_action: Any) -> dict[str, Any] | dict[str, str | int]:
    if not isinstance(edited_action, dict):
        return {
            "error": "invalid_tool_review_decision",
            "detail": "Edited action is missing.",
            "status_code": 400,
        }

    edited_name = str(edited_action.get("name") or "")
    if edited_name and edited_name != "call_authenticated_api":
        return {
            "error": "invalid_tool_review_decision",
            "detail": "Tool name edits are not allowed.",
            "status_code": 400,
        }

    edited_args = edited_action.get("args")
    if not isinstance(edited_args, dict):
        return {
            "error": "invalid_tool_review_decision",
            "detail": "edited_action.args must be an object.",
            "status_code": 400,
        }
    return edited_args


def _updated_optional_mapping(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) or value is None else None


def _apply_string_edits(current: dict[str, Any], edited_args: dict[str, Any]) -> None:
    for key in ("method", "url", "aa_number"):
        if key in edited_args:
            fallback = current[key] if key == "method" else ""
            current[key] = str(edited_args.get(key) or fallback)


def _apply_mapping_edits(current: dict[str, Any], edited_args: dict[str, Any]) -> None:
    if "json_body" in edited_args:
        current["json_body"] = _updated_optional_mapping(edited_args.get("json_body"))
    if "query_params" in edited_args:
        current["query_params"] = _updated_optional_mapping(
            edited_args.get("query_params")
        )


def _reviewed_request(
    *,
    method: str,
    url: str,
    aa_number: str,
    json_body: dict[str, Any] | None,
    query_params: dict[str, Any] | None,
    use_pace_servers_endpoint: bool,
    configurable: dict[str, Any],
) -> (
    tuple[str, str, str, dict[str, Any] | None, dict[str, Any] | None, bool]
    | dict[str, Any]
):
    proposed_action: dict[str, Any] = {
        "name": "call_authenticated_api",
        "args": {
            "method": method,
            "url": url,
            "aa_number": aa_number,
            "json_body": json_body,
            "query_params": query_params,
            "use_pace_servers_endpoint": use_pace_servers_endpoint,
        },
    }
    review = review_tool_call(
        action=proposed_action,
        reason="External authenticated API calls require human approval.",
        tool_name="call_authenticated_api",
        phase=str(configurable.get("phase") or "discovery"),
        request_fn=request_tool_review,
    )
    decision_type = str(review.get("type") or "").strip().lower()
    if decision_type not in {"approve", "edit"}:
        return {
            "error": "tool_approval_denied",
            "detail": str(review.get("message") or "Action rejected by reviewer."),
            "status_code": 403,
        }

    if decision_type != "edit":
        return (
            method,
            url,
            aa_number,
            json_body,
            query_params,
            use_pace_servers_endpoint,
        )

    return _apply_edit_decision(
        review,
        method,
        url,
        aa_number,
        json_body,
        query_params,
        use_pace_servers_endpoint,
    )


def _resolve_target_request(
    *,
    current_url: str,
    current_aa_number: str,
    current_query_params: dict[str, Any] | None,
    current_use_pace_servers_endpoint: bool,
) -> tuple[str, dict[str, Any]] | dict[str, Any]:
    pace_servers_url = get_settings().pace_servers_url
    if current_use_pace_servers_endpoint:
        return _resolve_pace_params(current_aa_number, pace_servers_url)

    target_url = current_url.strip()
    if not target_url:
        return {"error": "url is required when use_pace_servers_endpoint is false."}
    return target_url, dict(current_query_params or {})


def _authorisation_headers(
    configurable: dict[str, Any],
    use_pace_servers_endpoint: bool = False,
) -> dict[str, str] | dict[str, Any]:
    """Build authorization headers. For PACE, use OAuth2 token from WEB SPN."""
    if use_pace_servers_endpoint:
        logger.info("Requesting PACE access token via client credentials")
        try:
            token = get_pace_access_token()
            logger.info("PACE access token acquired successfully")
        except PaceAuthError as exc:
            logger.error("PACE token generation failed: %s", exc, exc_info=True)
            return {"error": f"PACE token generation failed: {exc}"}
        except Exception as exc:
            logger.error(
                "Unexpected error during PACE token acquisition: %s",
                exc,
                exc_info=True,
            )
            return {"error": f"Unexpected error: {exc}"}
    else:
        token = configurable.get("bearer_token") or get_settings().api_bearer_token
        if not token:
            logger.error(
                "Bearer token not configured (configurable.bearer_token=%s, DICE_API_BEARER_TOKEN=%s)",
                bool(configurable.get("bearer_token")),
                bool(get_settings().api_bearer_token),
            )
            return {
                "error": "Bearer token not configured. Pass config.configurable.bearer_token or set environment variable."
            }

        if len(token) < 32:
            logger.error(
                "Bearer token too weak: length=%d (minimum 32 required).",
                len(token),
            )
            return {
                "error": "Bearer token is too weak (minimum 32 characters required). Provide a valid token."
            }

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _apply_edit_decision(
    decision: dict[str, Any],
    method: str,
    url: str,
    aa_number: str,
    json_body: dict[str, Any] | None,
    query_params: dict[str, Any] | None,
    use_pace_servers_endpoint: bool,
) -> (
    tuple[str, str, str, dict[str, Any] | None, dict[str, Any] | None, bool]
    | dict[str, Any]
):
    """Apply edit decision to parameters. Returns tuple of edited args or error dict."""
    edited_args = _edited_arg_mapping(decision.get("edited_action"))
    if "error" in edited_args:
        return edited_args

    current: dict[str, Any] = {
        "method": method,
        "url": url,
        "aa_number": aa_number,
        "json_body": json_body,
        "query_params": query_params,
        "use_pace_servers_endpoint": use_pace_servers_endpoint,
    }

    _apply_string_edits(current, edited_args)
    _apply_mapping_edits(current, edited_args)
    if "use_pace_servers_endpoint" in edited_args:
        current["use_pace_servers_endpoint"] = bool(
            edited_args.get("use_pace_servers_endpoint")
        )

    return (
        current["method"],
        current["url"],
        current["aa_number"],
        current["json_body"],
        current["query_params"],
        current["use_pace_servers_endpoint"],
    )


def _resolve_pace_params(
    aa_number: str,
    pace_servers_url: str,
) -> tuple[str, dict[str, Any]] | dict[str, Any]:
    """Resolve PACE server URL and parameters. Returns (url, params) or error dict."""
    target_url = pace_servers_url.strip()
    if not target_url:
        return {
            "error": (
                "PACE servers URL is not configured. "
                "Set DICE_PACE_SERVERS_URL or [external] pace_servers_url."
            ),
        }
    aa_code = aa_number.strip()
    if not aa_code:
        return {
            "error": "aa_number is required when use_pace_servers_endpoint is true.",
        }
    params: dict[str, Any] = {
        "swc_id__ilike": aa_code,
        "order_by": "+inka",
        "size": 100,
    }
    return (target_url, params)


def _execute_api_call(
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any] | None,
    params: dict[str, Any] | None,
) -> dict[str, Any]:
    """Execute HTTP request and return response. Returns response dict or error dict."""
    logger.warning("Calling authenticated API: %s %s", method, url)
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_body or None,
                params=params or None,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Authenticated API call failed: HTTP %s from %s | body=%s",
            exc.response.status_code,
            url,
            exc.response.text[:500],
        )
        return {
            "error": f"HTTP {exc.response.status_code} from {url}",
            "status_code": exc.response.status_code,
            "detail": exc.response.text[:500],
        }
    except httpx.HTTPError as exc:
        logger.error(
            "Authenticated API call to %s raised %s: %s",
            url,
            type(exc).__name__,
            exc,
        )
        return {"error": f"Request to {url} failed: {exc!s}"}

    logger.warning(
        "Authenticated API call succeeded: %s %s -> HTTP %s",
        method,
        url,
        response.status_code,
    )

    try:
        data: Any = response.json()
    except Exception:
        data = response.text

    return {"status_code": response.status_code, "data": data}


@tool
async def call_authenticated_api(
    method: str = "GET",
    url: str = "",
    aa_number: str = "",
    json_body: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    use_pace_servers_endpoint: bool = False,
    runtime: ToolRuntime[Any] = None,
) -> dict[str, Any]:
    """Call an authenticated API endpoint and return the response.

    Typical discovery usage:
    - Set use_pace_servers_endpoint=True and provide aa_number.
    - Pass the returned data directly to populate_discovery_artifacts_from_servers.
    """
    if runtime is None:
        return {
            "error": "runtime_not_available",
            "detail": "LangGraph ToolRuntime was not injected.",
            "status_code": 500,
        }

    configurable = dict((runtime.config or {}).get("configurable", {}))
    reviewed_request = _reviewed_request(
        method=method,
        url=url,
        aa_number=aa_number,
        json_body=json_body,
        query_params=query_params,
        use_pace_servers_endpoint=use_pace_servers_endpoint,
        configurable=configurable,
    )
    if isinstance(reviewed_request, dict):
        return reviewed_request
    (
        current_method,
        current_url,
        current_aa_number,
        current_json_body,
        current_query_params,
        current_use_pace_servers_endpoint,
    ) = reviewed_request

    resolved = _resolve_target_request(
        current_url=current_url,
        current_aa_number=current_aa_number,
        current_query_params=current_query_params,
        current_use_pace_servers_endpoint=current_use_pace_servers_endpoint,
    )
    if isinstance(resolved, dict):
        return resolved
    target_url, params = resolved

    normalised = current_method.upper().strip()
    if normalised not in _ALLOWED_METHODS:
        return {
            "error": (
                f"Unsupported HTTP method '{current_method}'. "
                f"Allowed: {sorted(_ALLOWED_METHODS)}"
            ),
        }

    headers = _authorisation_headers(
        configurable,
        use_pace_servers_endpoint=current_use_pace_servers_endpoint,
    )
    if "error" in headers:
        return headers

    response = await asyncio.to_thread(
        _execute_api_call,
        normalised,
        target_url,
        headers,
        current_json_body,
        params,
    )

    if current_use_pace_servers_endpoint:
        return await persist_successful_api_result(
            runtime=runtime,
            api_name="pace_servers",
            path="/scratch/discovery/pace-servers.json",
            response=response,
        )

    return response
