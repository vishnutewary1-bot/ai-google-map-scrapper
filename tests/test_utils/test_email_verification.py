"""Tests for email verification module."""
import pytest
import asyncio
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.email_verification import EmailVerifier, get_email_verifier


class TestEmailVerifier:
    """Test suite for EmailVerifier class."""

    @pytest.fixture
    def verifier(self):
        """Create an email verifier instance."""
        return EmailVerifier()

    def test_syntax_check_valid_email(self, verifier):
        """Test syntax check for valid email."""
        is_valid, message = verifier._check_syntax("test@example.com")
        assert is_valid is True

    def test_syntax_check_invalid_email_no_at(self, verifier):
        """Test syntax check rejects email without @."""
        is_valid, message = verifier._check_syntax("testexample.com")
        assert is_valid is False

    def test_syntax_check_invalid_email_no_domain(self, verifier):
        """Test syntax check rejects email without domain."""
        is_valid, message = verifier._check_syntax("test@")
        assert is_valid is False

    def test_syntax_check_invalid_email_no_tld(self, verifier):
        """Test syntax check rejects email without TLD."""
        is_valid, message = verifier._check_syntax("test@example")
        assert is_valid is False

    def test_syntax_check_empty_email(self, verifier):
        """Test syntax check rejects empty email."""
        is_valid, message = verifier._check_syntax("")
        assert is_valid is False

    def test_syntax_check_email_too_long(self, verifier):
        """Test syntax check rejects overly long email."""
        long_email = "a" * 250 + "@example.com"
        is_valid, message = verifier._check_syntax(long_email)
        assert is_valid is False

    def test_syntax_check_consecutive_dots(self, verifier):
        """Test syntax check rejects consecutive dots."""
        is_valid, message = verifier._check_syntax("test..email@example.com")
        assert is_valid is False

    def test_disposable_domain_detected(self, verifier):
        """Test disposable email domain detection."""
        result = asyncio.run(verifier.verify_email("test@tempmail.com", level="syntax"))
        assert result["checks"]["disposable"]["is_disposable"] is True

    def test_non_disposable_domain(self, verifier):
        """Test non-disposable domain passes."""
        result = asyncio.run(verifier.verify_email("test@gmail.com", level="syntax"))
        assert result["checks"]["disposable"]["is_disposable"] is False

    def test_role_based_email_detected(self, verifier):
        """Test role-based email detection."""
        result = asyncio.run(verifier.verify_email("info@example.com", level="syntax"))
        assert result["checks"]["role_based"]["is_role_based"] is True

    def test_personal_email_not_role_based(self, verifier):
        """Test personal email is not flagged as role-based."""
        result = asyncio.run(verifier.verify_email("john.smith@example.com", level="syntax"))
        assert result["checks"]["role_based"]["is_role_based"] is False

    def test_verify_email_returns_required_fields(self, verifier):
        """Test that verify_email returns all required fields."""
        result = asyncio.run(verifier.verify_email("test@example.com", level="syntax"))

        assert "email" in result
        assert "is_valid" in result
        assert "status" in result
        assert "verification_level" in result
        assert "checks" in result
        assert "score" in result
        assert "risk_level" in result

    def test_verify_email_syntax_level(self, verifier):
        """Test verification at syntax level."""
        result = asyncio.run(verifier.verify_email("test@example.com", level="syntax"))
        assert result["verification_level"] == "syntax"

    def test_calculate_risk_level_disposable_high(self, verifier):
        """Test risk level is high for disposable email."""
        result = {
            "checks": {
                "disposable": {"is_disposable": True},
                "domain": {"passed": True}
            },
            "score": 50
        }
        risk = verifier._calculate_risk_level(result)
        assert risk == "high"

    def test_calculate_risk_level_invalid_domain_high(self, verifier):
        """Test risk level is high for invalid domain."""
        result = {
            "checks": {
                "disposable": {"is_disposable": False},
                "domain": {"passed": False}
            },
            "score": 30
        }
        risk = verifier._calculate_risk_level(result)
        assert risk == "high"

    def test_stats_tracking(self, verifier):
        """Test that verification stats are tracked."""
        asyncio.run(verifier.verify_email("valid@example.com", level="syntax"))
        stats = verifier.get_stats()

        assert "total_verified" in stats
        assert "valid" in stats
        assert "invalid" in stats

    @pytest.mark.asyncio
    async def test_verify_batch(self, verifier):
        """Test batch email verification."""
        emails = ["test1@example.com", "test2@example.com", "test3@example.com"]
        results = await verifier.verify_batch(emails, level="syntax", max_concurrent=2)

        assert len(results) == 3
        for result in results:
            assert "email" in result
            assert "is_valid" in result


class TestGetEmailVerifier:
    """Test suite for get_email_verifier singleton."""

    def test_returns_email_verifier_instance(self):
        """Test that get_email_verifier returns EmailVerifier instance."""
        verifier = get_email_verifier()
        assert isinstance(verifier, EmailVerifier)
