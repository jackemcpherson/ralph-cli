"""Unit tests for Manifest model and functions.

Focused tests for manifest handling:
- Manifest model creation and serialization
- Loading/saving manifests to/from files
"""

import json
from pathlib import Path

from ralph.models import Manifest, load_manifest, save_manifest


class TestManifest:
    """Tests for the Manifest model."""

    def test_manifest_creation_and_serialization(self) -> None:
        """Test Manifest creation with camelCase alias and serialization."""
        # Test creation with camelCase alias
        manifest = Manifest(
            installed=["ralph-prd", "ralph-tasks"],
            syncedAt="2026-01-21T10:00:00Z",
        )

        assert manifest.installed == ["ralph-prd", "ralph-tasks"]
        assert manifest.synced_at == "2026-01-21T10:00:00Z"

        # Verify serialization uses camelCase
        json_str = manifest.model_dump_json(by_alias=True)
        data = json.loads(json_str)
        assert "syncedAt" in data
        assert "synced_at" not in data


class TestLoadSaveManifest:
    """Tests for load_manifest and save_manifest functions."""

    def test_load_manifest_from_valid_file(self, tmp_path: Path) -> None:
        """Test loading a valid manifest file."""
        manifest_data = {
            "installed": ["ralph-prd", "ralph-tasks"],
            "syncedAt": "2026-01-21T10:00:00Z",
        }

        manifest_file = tmp_path / ".ralph-manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))

        manifest = load_manifest(manifest_file)

        assert manifest is not None
        assert manifest.installed == ["ralph-prd", "ralph-tasks"]

    def test_load_manifest_returns_none_for_nonexistent(self, tmp_path: Path) -> None:
        """Test loading a nonexistent file returns None."""
        result = load_manifest(tmp_path / "nonexistent.json")
        assert result is None

    def test_save_load_round_trip(self, tmp_path: Path) -> None:
        """Test that save_manifest and load_manifest are inverse operations."""
        original = Manifest(
            installed=["ralph-prd", "ralph-tasks"],
            synced_at="2026-01-21T10:00:00Z",
        )

        manifest_file = tmp_path / ".ralph-manifest.json"
        save_manifest(original, manifest_file)

        # Verify file contents use camelCase
        data = json.loads(manifest_file.read_text())
        assert data["syncedAt"] == "2026-01-21T10:00:00Z"

        # Verify round-trip
        loaded = load_manifest(manifest_file)
        assert loaded is not None
        assert loaded.installed == original.installed
