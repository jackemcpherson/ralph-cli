"""Unit tests for ReviewState model.

Tests cover:
- Model creation and field validation
- Config hash computation from ReviewerConfig lists
- Save/load round-trip to JSON files
- Handling of missing or invalid state files
- Config hash determinism and change detection
"""

import json
from pathlib import Path

from ralph.models import REVIEW_STATE_FILENAME, ReviewState
from ralph.models.reviewer import ReviewerConfig, ReviewerLevel


def _make_reviewers() -> list[ReviewerConfig]:
    """Create a sample list of ReviewerConfig objects for testing."""
    return [
        ReviewerConfig(
            name="test-quality",
            skill="reviewers/test-quality",
            level=ReviewerLevel.blocking,
        ),
        ReviewerConfig(
            name="python-code",
            skill="reviewers/language/python",
            level=ReviewerLevel.blocking,
            languages=["python"],
        ),
    ]


class TestReviewStateModel:
    """Tests for ReviewState model creation and fields."""

    def test_create_review_state(self) -> None:
        """Test basic ReviewState creation with all required fields."""
        state = ReviewState(
            reviewer_names=["test-quality", "python-code"],
            completed={"test-quality": True},
            timestamp="2026-02-08T10:00:00Z",
            config_hash="abc123",
        )

        assert state.reviewer_names == ["test-quality", "python-code"]
        assert state.completed == {"test-quality": True}
        assert state.timestamp == "2026-02-08T10:00:00Z"
        assert state.config_hash == "abc123"

    def test_completed_defaults_to_empty_dict(self) -> None:
        """Test that completed field defaults to empty dict."""
        state = ReviewState(
            reviewer_names=["a"],
            timestamp="2026-02-08T10:00:00Z",
            config_hash="abc",
        )

        assert state.completed == {}

    def test_serialization_round_trip(self) -> None:
        """Test that model serializes and deserializes correctly."""
        state = ReviewState(
            reviewer_names=["test-quality", "python-code"],
            completed={"test-quality": True, "python-code": False},
            timestamp="2026-02-08T10:00:00Z",
            config_hash="abc123",
        )

        json_str = state.model_dump_json()
        restored = ReviewState.model_validate_json(json_str)

        assert restored.reviewer_names == state.reviewer_names
        assert restored.completed == state.completed
        assert restored.timestamp == state.timestamp
        assert restored.config_hash == state.config_hash


class TestComputeConfigHash:
    """Tests for ReviewState.compute_config_hash."""

    def test_hash_is_deterministic(self) -> None:
        """Test that the same config produces the same hash."""
        reviewers = _make_reviewers()
        hash1 = ReviewState.compute_config_hash(reviewers)
        hash2 = ReviewState.compute_config_hash(reviewers)

        assert hash1 == hash2

    def test_hash_is_hex_string(self) -> None:
        """Test that the hash is a valid hex string."""
        reviewers = _make_reviewers()
        config_hash = ReviewState.compute_config_hash(reviewers)

        assert isinstance(config_hash, str)
        assert len(config_hash) == 64  # SHA-256 hex digest
        int(config_hash, 16)  # Should not raise

    def test_hash_changes_with_different_config(self) -> None:
        """Test that different configs produce different hashes."""
        reviewers1 = _make_reviewers()
        reviewers2 = [
            ReviewerConfig(
                name="different-reviewer",
                skill="reviewers/different",
                level=ReviewerLevel.warning,
            ),
        ]

        hash1 = ReviewState.compute_config_hash(reviewers1)
        hash2 = ReviewState.compute_config_hash(reviewers2)

        assert hash1 != hash2

    def test_hash_changes_when_level_changes(self) -> None:
        """Test that changing a reviewer's level changes the hash."""
        reviewers1 = [
            ReviewerConfig(
                name="test",
                skill="reviewers/test",
                level=ReviewerLevel.blocking,
            ),
        ]
        reviewers2 = [
            ReviewerConfig(
                name="test",
                skill="reviewers/test",
                level=ReviewerLevel.warning,
            ),
        ]

        assert ReviewState.compute_config_hash(reviewers1) != ReviewState.compute_config_hash(
            reviewers2
        )

    def test_hash_empty_list(self) -> None:
        """Test that an empty reviewer list produces a valid hash."""
        config_hash = ReviewState.compute_config_hash([])

        assert isinstance(config_hash, str)
        assert len(config_hash) == 64

    def test_hash_language_order_irrelevant(self) -> None:
        """Test that language list order does not affect the hash."""
        reviewers1 = [
            ReviewerConfig(
                name="test",
                skill="reviewers/test",
                level=ReviewerLevel.blocking,
                languages=["python", "javascript"],
            ),
        ]
        reviewers2 = [
            ReviewerConfig(
                name="test",
                skill="reviewers/test",
                level=ReviewerLevel.blocking,
                languages=["javascript", "python"],
            ),
        ]

        assert ReviewState.compute_config_hash(reviewers1) == ReviewState.compute_config_hash(
            reviewers2
        )

    def test_hash_changes_when_name_changes(self) -> None:
        """Test that changing a reviewer's name changes the hash."""
        reviewers1 = [ReviewerConfig(name="a", skill="reviewers/x", level=ReviewerLevel.blocking)]
        reviewers2 = [ReviewerConfig(name="b", skill="reviewers/x", level=ReviewerLevel.blocking)]

        assert ReviewState.compute_config_hash(reviewers1) != ReviewState.compute_config_hash(
            reviewers2
        )

    def test_hash_none_languages_vs_empty_list(self) -> None:
        """Test that None languages and empty list are treated equivalently."""
        reviewers_none = [
            ReviewerConfig(
                name="x", skill="reviewers/x", level=ReviewerLevel.blocking, languages=None
            )
        ]
        reviewers_empty: list[ReviewerConfig] = [
            ReviewerConfig(
                name="x", skill="reviewers/x", level=ReviewerLevel.blocking, languages=[]
            )
        ]
        # Both None and empty list are normalised to None in compute_config_hash
        assert ReviewState.compute_config_hash(reviewers_none) == ReviewState.compute_config_hash(
            reviewers_empty
        )


class TestSaveAndLoad:
    """Tests for ReviewState.save and ReviewState.load."""

    def test_save_creates_json_file(self, tmp_path: Path) -> None:
        """Test that save writes a valid JSON file."""
        state = ReviewState(
            reviewer_names=["test-quality"],
            completed={"test-quality": True},
            timestamp="2026-02-08T10:00:00Z",
            config_hash="abc123",
        )

        state_file = tmp_path / REVIEW_STATE_FILENAME
        state.save(state_file)

        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["reviewer_names"] == ["test-quality"]
        assert data["completed"] == {"test-quality": True}

    def test_load_valid_file(self, tmp_path: Path) -> None:
        """Test loading a valid state file."""
        state_data = {
            "reviewer_names": ["test-quality", "python-code"],
            "completed": {"test-quality": True},
            "timestamp": "2026-02-08T10:00:00Z",
            "config_hash": "abc123",
        }

        state_file = tmp_path / REVIEW_STATE_FILENAME
        state_file.write_text(json.dumps(state_data))

        loaded = ReviewState.load(state_file)

        assert loaded is not None
        assert loaded.reviewer_names == ["test-quality", "python-code"]
        assert loaded.completed == {"test-quality": True}

    def test_load_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Test that loading a nonexistent file returns None."""
        result = ReviewState.load(tmp_path / "nonexistent.json")
        assert result is None

    def test_load_invalid_json_returns_none(self, tmp_path: Path) -> None:
        """Test that loading invalid JSON returns None."""
        state_file = tmp_path / REVIEW_STATE_FILENAME
        state_file.write_text("not valid json {{{")

        result = ReviewState.load(state_file)
        assert result is None

    def test_load_invalid_schema_returns_none(self, tmp_path: Path) -> None:
        """Test that loading JSON with wrong schema returns None."""
        state_file = tmp_path / REVIEW_STATE_FILENAME
        state_file.write_text(json.dumps({"wrong": "schema"}))

        result = ReviewState.load(state_file)
        assert result is None

    def test_save_load_round_trip(self, tmp_path: Path) -> None:
        """Test that save and load are inverse operations."""
        reviewers = _make_reviewers()
        original = ReviewState(
            reviewer_names=[r.name for r in reviewers],
            completed={"test-quality": True, "python-code": False},
            timestamp="2026-02-08T10:00:00Z",
            config_hash=ReviewState.compute_config_hash(reviewers),
        )

        state_file = tmp_path / REVIEW_STATE_FILENAME
        original.save(state_file)

        loaded = ReviewState.load(state_file)

        assert loaded is not None
        assert loaded.reviewer_names == original.reviewer_names
        assert loaded.completed == original.completed
        assert loaded.timestamp == original.timestamp
        assert loaded.config_hash == original.config_hash
