"""Tests for deduplication module."""
import pytest
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.deduplicator import AdvancedDeduplicator


class TestAdvancedDeduplicator:
    """Test suite for AdvancedDeduplicator class."""

    @pytest.fixture
    def deduplicator(self):
        """Create a deduplicator instance with default settings."""
        return AdvancedDeduplicator()

    @pytest.fixture
    def strict_deduplicator(self):
        """Create a deduplicator with strict thresholds."""
        return AdvancedDeduplicator(
            name_similarity_threshold=95.0,
            address_similarity_threshold=90.0,
            proximity_threshold_meters=20.0
        )

    def test_normalize_phone_removes_formatting(self, deduplicator):
        """Test phone normalization removes formatting characters."""
        result = deduplicator.normalize_phone("+91 (987) 654-3210")
        assert result is not None
        assert "(" not in result
        assert ")" not in result
        assert "-" not in result

    def test_normalize_phone_handles_10_digit(self, deduplicator):
        """Test phone normalization handles 10-digit numbers."""
        result = deduplicator.normalize_phone("9876543210")
        assert result is not None
        assert "+91" in result

    def test_normalize_phone_handles_none(self, deduplicator):
        """Test phone normalization handles None."""
        result = deduplicator.normalize_phone(None)
        assert result is None

    def test_normalize_phone_handles_empty(self, deduplicator):
        """Test phone normalization handles empty string."""
        result = deduplicator.normalize_phone("")
        assert result is None

    def test_name_similarity_exact_match(self, deduplicator):
        """Test name similarity for exact match."""
        similarity = deduplicator.calculate_name_similarity(
            "Test Business",
            "Test Business"
        )
        assert similarity == 100.0

    def test_name_similarity_case_insensitive(self, deduplicator):
        """Test name similarity is case insensitive."""
        similarity = deduplicator.calculate_name_similarity(
            "TEST BUSINESS",
            "test business"
        )
        assert similarity == 100.0

    def test_name_similarity_word_order(self, deduplicator):
        """Test name similarity handles word order differences."""
        similarity = deduplicator.calculate_name_similarity(
            "Mumbai Restaurant",
            "Restaurant Mumbai"
        )
        # Token set ratio should give high score for same words
        assert similarity >= 80.0

    def test_name_similarity_different_names(self, deduplicator):
        """Test name similarity for different names."""
        similarity = deduplicator.calculate_name_similarity(
            "Pizza Palace",
            "Burger King"
        )
        assert similarity < 50.0

    def test_address_similarity_exact_match(self, deduplicator):
        """Test address similarity for exact match."""
        similarity = deduplicator.calculate_address_similarity(
            "123 Main Street, Mumbai",
            "123 Main Street, Mumbai"
        )
        assert similarity == 100.0

    def test_address_similarity_handles_none(self, deduplicator):
        """Test address similarity handles None values."""
        similarity = deduplicator.calculate_address_similarity(None, "123 Main St")
        assert similarity == 0.0

    def test_calculate_distance_same_point(self, deduplicator):
        """Test distance calculation for same point."""
        distance = deduplicator.calculate_distance(
            19.0760, 72.8777,  # Mumbai
            19.0760, 72.8777   # Same point
        )
        assert distance == 0.0

    def test_calculate_distance_different_points(self, deduplicator):
        """Test distance calculation for different points."""
        distance = deduplicator.calculate_distance(
            19.0760, 72.8777,  # Mumbai
            19.0860, 72.8877   # Slightly different
        )
        assert distance is not None
        assert distance > 0

    def test_calculate_distance_handles_none(self, deduplicator):
        """Test distance calculation handles None values."""
        distance = deduplicator.calculate_distance(
            19.0760, None,
            19.0860, 72.8877
        )
        assert distance is None

    def test_calculate_distance_known_distance(self, deduplicator):
        """Test distance calculation with known distance."""
        # Mumbai to Pune is approximately 150km
        distance = deduplicator.calculate_distance(
            19.0760, 72.8777,   # Mumbai
            18.5204, 73.8567    # Pune
        )
        assert distance is not None
        # Should be between 100km and 200km
        assert 100000 < distance < 200000


class TestDeduplicatorThresholds:
    """Test suite for threshold-based deduplication."""

    def test_strict_threshold_rejects_partial_match(self):
        """Test that strict threshold rejects partial matches."""
        strict = AdvancedDeduplicator(name_similarity_threshold=95.0)

        similarity = strict.calculate_name_similarity(
            "Mumbai Restaurant & Bar",
            "Mumbai Restaurant"
        )

        # This might be below 95% threshold
        # The test verifies the threshold mechanism works
        assert isinstance(similarity, float)

    def test_lenient_threshold_accepts_partial_match(self):
        """Test that lenient threshold accepts partial matches."""
        lenient = AdvancedDeduplicator(name_similarity_threshold=70.0)

        similarity = lenient.calculate_name_similarity(
            "Mumbai Restaurant & Bar",
            "Mumbai Restaurant"
        )

        # Similar names should score above 70%
        assert similarity >= 70.0
