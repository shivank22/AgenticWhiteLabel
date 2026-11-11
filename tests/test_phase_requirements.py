"""Tests for phase transition requirements and deterministic checks."""

import pytest
from unittest.mock import MagicMock

from src.workflows.phase_requirements import (
    PHASES,
    PHASE_ORDER,
    CheckResult,
    TransitionResult,
    check_phase_requirements,
)


def _mock_backend(files: dict[str, str | None]) -> MagicMock:
    """Create a mock backend with specified file contents.
    
    Args:
        files: dict mapping paths to content (None means file not found)
    """
    backend = MagicMock()
    
    def mock_read(path: str):
        result = MagicMock()
        content = files.get(path)
        if content is None:
            result.error = f"File not found: {path}"
            result.file_data = None
        else:
            result.error = None
            result.file_data = {"content": content}
        return result
    
    backend.read = mock_read
    return backend


class TestPhaseDefinitions:
    """Test that phase definitions are valid."""

    def test_all_phases_defined(self):
        assert set(PHASE_ORDER) == set(PHASES.keys())

    def test_phase_order_is_tuple(self):
        assert isinstance(PHASE_ORDER, tuple)
        assert len(PHASE_ORDER) == 4

    def test_each_phase_has_required_fields(self):
        for phase, config in PHASES.items():
            assert "description" in config, f"{phase} missing description"
            assert isinstance(config.get("required_files", []), list)
            assert isinstance(config.get("required_state", []), list)


class TestTransitionToDiscovery:
    """Test requirements for transitioning to discovery phase."""

    def test_discovery_blocked_without_artifact(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": None,
            "/scratch/supervisor/canvas.md": "canvas content",
        })
        state = {"aa_number": "AA123"}
        
        result = check_phase_requirements("discovery", state, backend)
        
        assert not result.allowed
        assert "artifact.yaml" in result.message

    def test_discovery_blocked_without_supervisor_canvas(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": "artifact content",
            "/scratch/supervisor/canvas.md": None,
        })
        state = {"aa_number": "AA123"}
        
        result = check_phase_requirements("discovery", state, backend)
        
        assert not result.allowed
        assert "supervisor/canvas.md" in result.message

    def test_discovery_blocked_without_aa_number(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": "artifact content",
            "/scratch/supervisor/canvas.md": "canvas content",
        })
        state = {}
        
        result = check_phase_requirements("discovery", state, backend)
        
        assert not result.allowed
        assert "aa_number" in result.message

    def test_discovery_allowed_with_all_prerequisites(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": "artifact content",
            "/scratch/supervisor/canvas.md": "canvas content",
        })
        state = {"aa_number": "AA123"}
        
        result = check_phase_requirements("discovery", state, backend)
        
        assert result.allowed
        assert result.target_phase == "discovery"


class TestTransitionToDesign:
    """Test requirements for transitioning to design phase."""

    def test_design_blocked_without_discovery_status(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": "content",
            "/artifacts/discovery/discovery-details.yaml": "content",
            "/scratch/discovery/canvas.md": "content",
        })
        state = {"aa_number": "AA123", "discovery_status": None}
        
        result = check_phase_requirements("design", state, backend)
        
        assert not result.allowed
        assert "discovery_status" in result.message

    def test_design_blocked_with_wrong_discovery_status(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": "content",
            "/artifacts/discovery/discovery-details.yaml": "content",
            "/scratch/discovery/canvas.md": "content",
        })
        state = {"aa_number": "AA123", "discovery_status": "in_progress"}
        
        result = check_phase_requirements("design", state, backend)
        
        assert not result.allowed
        assert "discovery_status" in result.message
        assert "in_progress" in result.message

    def test_design_blocked_without_discovery_details(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": "content",
            "/artifacts/discovery/discovery-details.yaml": None,
            "/scratch/discovery/canvas.md": "content",
        })
        state = {"aa_number": "AA123", "discovery_status": "complete"}
        
        result = check_phase_requirements("design", state, backend)
        
        assert not result.allowed
        assert "discovery-details.yaml" in result.message

    def test_design_allowed_with_all_prerequisites(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": "content",
            "/artifacts/discovery/discovery-details.yaml": "discovery data",
            "/scratch/discovery/canvas.md": "canvas content",
        })
        state = {"aa_number": "AA123", "discovery_status": "complete"}
        
        result = check_phase_requirements("design", state, backend)
        
        assert result.allowed
        assert result.target_phase == "design"


class TestTransitionToComplete:
    """Test requirements for transitioning to complete phase."""

    def test_complete_blocked_without_design_artifact(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": "content",
            "/artifacts/discovery/discovery-details.yaml": "content",
            "/artifacts/design/design.yaml": None,
            "/scratch/design/canvas.md": "content",
        })
        state = {"aa_number": "AA123"}
        
        result = check_phase_requirements("complete", state, backend)
        
        assert not result.allowed
        assert "design.yaml" in result.message

    def test_complete_blocked_without_design_canvas(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": "content",
            "/artifacts/discovery/discovery-details.yaml": "content",
            "/artifacts/design/design.yaml": "content",
            "/scratch/design/canvas.md": None,
        })
        state = {"aa_number": "AA123"}
        
        result = check_phase_requirements("complete", state, backend)
        
        assert not result.allowed
        assert "design/canvas.md" in result.message

    def test_complete_allowed_with_all_prerequisites(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": "content",
            "/artifacts/discovery/discovery-details.yaml": "content",
            "/artifacts/design/design.yaml": "design data",
            "/scratch/design/canvas.md": "canvas content",
        })
        state = {"aa_number": "AA123"}
        
        result = check_phase_requirements("complete", state, backend)
        
        assert result.allowed
        assert result.target_phase == "complete"


class TestTransitionResultSerialization:
    """Test TransitionResult.to_dict() serialization."""

    def test_to_dict_includes_all_fields(self):
        result = TransitionResult(
            allowed=False,
            current_phase="intake",
            target_phase="discovery",
            checks=(
                CheckResult("file", "/path", True, "ok"),
                CheckResult("state", "field", False, "missing"),
            ),
            message="Blocked",
        )
        
        d = result.to_dict()
        
        assert d["allowed"] is False
        assert d["current_phase"] == "intake"
        assert d["target_phase"] == "discovery"
        assert len(d["checks"]) == 2
        assert d["checks"][0]["passed"] is True
        assert d["checks"][1]["passed"] is False


class TestEdgeCases:
    """Test edge cases and normalization."""

    def test_completed_normalized_to_complete(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": "content",
            "/artifacts/discovery/discovery-details.yaml": "content",
            "/artifacts/design/design.yaml": "content",
            "/scratch/design/canvas.md": "content",
        })
        state = {"aa_number": "AA123"}
        
        result = check_phase_requirements("completed", state, backend)
        
        assert result.target_phase == "complete"

    def test_unknown_phase_rejected(self):
        backend = _mock_backend({})
        state = {}
        
        result = check_phase_requirements("unknown_phase", state, backend)
        
        assert not result.allowed
        assert "Unknown phase" in result.message

    def test_empty_file_fails_check(self):
        backend = _mock_backend({
            "/artifacts/artifact.yaml": "   ",  # whitespace only
            "/scratch/supervisor/canvas.md": "content",
        })
        state = {"aa_number": "AA123"}
        
        result = check_phase_requirements("discovery", state, backend)
        
        assert not result.allowed
        assert "empty" in result.message.lower()

    def test_intake_has_no_requirements(self):
        backend = _mock_backend({})
        state = {}
        
        result = check_phase_requirements("intake", state, backend)
        
        assert result.allowed
