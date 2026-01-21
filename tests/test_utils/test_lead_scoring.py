"""Tests for lead scoring module."""
import pytest
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.lead_scoring import LeadScorer, get_lead_scorer


class TestLeadScorer:
    """Test suite for LeadScorer class."""

    @pytest.fixture
    def scorer(self):
        """Create a lead scorer instance."""
        return LeadScorer()

    @pytest.fixture
    def complete_lead(self):
        """Lead with complete data."""
        return {
            "business_name": "Premium Restaurant",
            "phone": "+91 98765 43210",
            "email": "contact@premium.com",
            "website": "https://premium.com",
            "full_address": "123 Main St, Mumbai, MH 400001",
            "city": "Mumbai",
            "state": "Maharashtra",
            "country": "India",
            "category": "Restaurant",
            "rating": 4.8,
            "review_count": 150,
            "social_facebook": "https://facebook.com/premium",
            "social_instagram": "https://instagram.com/premium",
            "social_linkedin": "https://linkedin.com/premium",
            "employees": "50-100",
            "founded_year": 2015
        }

    @pytest.fixture
    def minimal_lead(self):
        """Lead with minimal data."""
        return {
            "business_name": "Basic Shop"
        }

    def test_calculate_score_returns_dict(self, scorer, complete_lead):
        """Test that calculate_score returns a dictionary."""
        result = scorer.calculate_score(complete_lead)
        assert isinstance(result, dict)

    def test_calculate_score_includes_overall_score(self, scorer, complete_lead):
        """Test that result includes overall score."""
        result = scorer.calculate_score(complete_lead)
        assert "overall_score" in result
        assert isinstance(result["overall_score"], (int, float))

    def test_calculate_score_includes_grade(self, scorer, complete_lead):
        """Test that result includes a letter grade."""
        result = scorer.calculate_score(complete_lead)
        assert "grade" in result
        assert result["grade"] in ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F"]

    def test_calculate_score_includes_components(self, scorer, complete_lead):
        """Test that result includes component scores."""
        result = scorer.calculate_score(complete_lead)
        assert "components" in result
        assert isinstance(result["components"], dict)

    def test_complete_lead_scores_higher(self, scorer, complete_lead, minimal_lead):
        """Test that complete lead scores higher than minimal lead."""
        complete_score = scorer.calculate_score(complete_lead)
        minimal_score = scorer.calculate_score(minimal_lead)
        assert complete_score["overall_score"] > minimal_score["overall_score"]

    def test_score_is_bounded(self, scorer, complete_lead):
        """Test that score is between 0 and 100."""
        result = scorer.calculate_score(complete_lead)
        assert 0 <= result["overall_score"] <= 100

    def test_contact_info_scoring(self, scorer):
        """Test contact info scoring logic."""
        lead_with_phone = {"business_name": "Test", "phone": "+91 12345 67890"}
        lead_without = {"business_name": "Test"}

        score_with = scorer._score_contact_info(lead_with_phone)
        score_without = scorer._score_contact_info(lead_without)

        assert score_with > score_without

    def test_email_increases_contact_score(self, scorer):
        """Test that having email increases contact score."""
        lead_with_email = {"business_name": "Test", "email": "test@test.com"}
        lead_without = {"business_name": "Test"}

        score_with = scorer._score_contact_info(lead_with_email)
        score_without = scorer._score_contact_info(lead_without)

        assert score_with > score_without

    def test_high_rating_increases_reputation_score(self, scorer):
        """Test that high rating increases reputation score."""
        high_rated = {"rating": 4.8, "review_count": 100}
        low_rated = {"rating": 2.5, "review_count": 100}

        score_high = scorer._score_reputation(high_rated)
        score_low = scorer._score_reputation(low_rated)

        assert score_high > score_low

    def test_batch_score(self, scorer, complete_lead, minimal_lead):
        """Test batch scoring of multiple leads."""
        leads = [complete_lead, minimal_lead]
        results = scorer.batch_score(leads)

        assert len(results) == 2
        # Results should be sorted by score descending
        assert results[0]["lead_score"] >= results[1]["lead_score"]

    def test_recommendations_generated(self, scorer, complete_lead):
        """Test that recommendations are generated."""
        result = scorer.calculate_score(complete_lead)
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)

    def test_strengths_weaknesses_identified(self, scorer, complete_lead):
        """Test that strengths and weaknesses are identified."""
        result = scorer.calculate_score(complete_lead)
        assert "strengths" in result
        assert "weaknesses" in result


class TestGetLeadScorer:
    """Test suite for get_lead_scorer singleton."""

    def test_returns_lead_scorer_instance(self):
        """Test that get_lead_scorer returns LeadScorer instance."""
        scorer = get_lead_scorer()
        assert isinstance(scorer, LeadScorer)

    def test_returns_same_instance(self):
        """Test that get_lead_scorer returns singleton."""
        scorer1 = get_lead_scorer()
        scorer2 = get_lead_scorer()
        assert scorer1 is scorer2
