"""Unit tests for call_authenticated_api helpers (no network)."""

from __future__ import annotations

from src.workflows.agents.discovery.tools import authenticated_api as api


def test_resolve_pace_params_requires_aa():
    result = api._resolve_pace_params("", "https://pace.example/servers")
    assert isinstance(result, dict)
    assert "aa_number" in result["error"]


def test_resolve_pace_params_ok():
    url, params = api._resolve_pace_params("AA123", "https://pace.example/servers")
    assert url == "https://pace.example/servers"
    assert params["swc_id__ilike"] == "AA123"
    assert params["size"] == 100


def test_resolve_target_request_requires_url(monkeypatch):
    monkeypatch.setattr(
        api,
        "get_settings",
        lambda: type("S", (), {"pace_servers_url": ""})(),
    )
    result = api._resolve_target_request(
        current_url="",
        current_aa_number="",
        current_query_params=None,
        current_use_pace_servers_endpoint=False,
    )
    assert isinstance(result, dict)
    assert "url is required" in result["error"]


def test_apply_edit_decision():
    decision = {
        "type": "edit",
        "edited_action": {
            "name": "call_authenticated_api",
            "args": {"method": "POST", "use_pace_servers_endpoint": True},
        },
    }
    edited = api._apply_edit_decision(
        decision, "GET", "https://x", "AA1", None, None, False
    )
    assert edited[0] == "POST"
    assert edited[5] is True


def test_edited_arg_mapping_rejects_other_tool():
    result = api._edited_arg_mapping({"name": "other_tool", "args": {}})
    assert result["error"] == "invalid_tool_review_decision"


def test_authorisation_headers_missing_bearer(monkeypatch):
    monkeypatch.setattr(
        api,
        "get_settings",
        lambda: type("S", (), {"api_bearer_token": None})(),
    )
    result = api._authorisation_headers({}, use_pace_servers_endpoint=False)
    assert "error" in result
