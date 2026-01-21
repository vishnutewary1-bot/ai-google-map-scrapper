"""Tests for database models."""
import pytest
from datetime import datetime
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.models import BusinessLead, ScrapeJob, ExportHistory


class TestBusinessLead:
    """Test suite for BusinessLead model."""

    def test_create_business_lead(self, db_session):
        """Test creating a business lead."""
        lead = BusinessLead(
            business_name="Test Restaurant",
            category="Restaurant",
            city="Mumbai",
            phone="+91 98765 43210"
        )
        db_session.add(lead)
        db_session.commit()

        assert lead.id is not None
        assert lead.business_name == "Test Restaurant"

    def test_to_dict_returns_all_fields(self, db_session):
        """Test that to_dict returns all expected fields."""
        lead = BusinessLead(
            business_name="Test Business",
            city="Mumbai",
            phone="+91 12345 67890",
            email="test@test.com"
        )
        db_session.add(lead)
        db_session.commit()

        lead_dict = lead.to_dict()

        assert "id" in lead_dict
        assert "business_name" in lead_dict
        assert "city" in lead_dict
        assert "phone" in lead_dict
        assert "email" in lead_dict
        assert "created_at" in lead_dict

    def test_to_export_dict_returns_export_fields(self, db_session):
        """Test that to_export_dict returns export-optimized fields."""
        lead = BusinessLead(
            business_name="Export Test",
            website="https://test.com",
            rating=4.5,
            review_count=100
        )
        db_session.add(lead)
        db_session.commit()

        export_dict = lead.to_export_dict()

        assert "name" in export_dict
        assert "site" in export_dict
        assert "rating" in export_dict
        assert "reviews" in export_dict
        assert export_dict["name"] == "Export Test"

    def test_calculate_quality_score(self, db_session):
        """Test quality score calculation."""
        lead = BusinessLead(
            business_name="Quality Test",
            phone="+91 98765 43210",
            email="test@test.com",
            website="https://test.com",
            city="Mumbai",
            rating=4.5
        )
        db_session.add(lead)
        db_session.commit()

        score = lead.calculate_quality_score()

        assert 0 <= score <= 100
        assert lead.data_quality_score == score

    def test_has_social_media_true(self, db_session):
        """Test has_social_media returns True when social links exist."""
        lead = BusinessLead(
            business_name="Social Test",
            social_facebook="https://facebook.com/test"
        )
        db_session.add(lead)
        db_session.commit()

        assert lead.has_social_media() is True

    def test_has_social_media_false(self, db_session):
        """Test has_social_media returns False when no social links."""
        lead = BusinessLead(business_name="No Social Test")
        db_session.add(lead)
        db_session.commit()

        assert lead.has_social_media() is False

    def test_has_contact_info_true(self, db_session):
        """Test has_contact_info returns True when contact info exists."""
        lead = BusinessLead(
            business_name="Contact Test",
            phone="+91 98765 43210"
        )
        db_session.add(lead)
        db_session.commit()

        assert lead.has_contact_info() is True

    def test_has_contact_info_false(self, db_session):
        """Test has_contact_info returns False when no contact info."""
        lead = BusinessLead(business_name="No Contact Test")
        db_session.add(lead)
        db_session.commit()

        assert lead.has_contact_info() is False

    def test_get_all_phones(self, db_session):
        """Test get_all_phones returns all phone numbers."""
        lead = BusinessLead(
            business_name="Multi Phone Test",
            phone="+91 11111 11111",
            phone_1="+91 22222 22222",
            phone_2="+91 33333 33333"
        )
        db_session.add(lead)
        db_session.commit()

        phones = lead.get_all_phones()

        assert len(phones) == 3
        assert "+91 11111 11111" in phones

    def test_get_all_emails(self, db_session):
        """Test get_all_emails returns all emails."""
        lead = BusinessLead(
            business_name="Multi Email Test",
            email="primary@test.com",
            email_1="secondary@test.com"
        )
        db_session.add(lead)
        db_session.commit()

        emails = lead.get_all_emails()

        assert len(emails) == 2
        assert "primary@test.com" in emails

    def test_unique_place_id_constraint(self, db_session):
        """Test that place_id must be unique."""
        lead1 = BusinessLead(
            business_name="Lead 1",
            place_id="unique_place_123"
        )
        db_session.add(lead1)
        db_session.commit()

        lead2 = BusinessLead(
            business_name="Lead 2",
            place_id="unique_place_123"  # Duplicate
        )
        db_session.add(lead2)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()


class TestScrapeJob:
    """Test suite for ScrapeJob model."""

    def test_create_scrape_job(self, db_session):
        """Test creating a scrape job."""
        job = ScrapeJob(
            search_query="restaurants in Mumbai",
            location="Mumbai",
            max_results=100
        )
        db_session.add(job)
        db_session.commit()

        assert job.id is not None
        assert job.status == "pending"

    def test_to_dict_returns_all_fields(self, db_session):
        """Test that to_dict returns all expected fields."""
        job = ScrapeJob(
            search_query="hotels in Delhi",
            max_results=50
        )
        db_session.add(job)
        db_session.commit()

        job_dict = job.to_dict()

        assert "id" in job_dict
        assert "search_query" in job_dict
        assert "status" in job_dict
        assert "leads_scraped" in job_dict
        assert "progress_percent" in job_dict

    def test_get_progress_percent_zero(self, db_session):
        """Test progress percent is 0 when no leads."""
        job = ScrapeJob(
            search_query="test",
            leads_target=100,
            leads_scraped=0
        )
        db_session.add(job)
        db_session.commit()

        assert job.get_progress_percent() == 0

    def test_get_progress_percent_partial(self, db_session):
        """Test progress percent calculation."""
        job = ScrapeJob(
            search_query="test",
            leads_target=100,
            leads_scraped=50
        )
        db_session.add(job)
        db_session.commit()

        assert job.get_progress_percent() == 50

    def test_get_progress_percent_complete(self, db_session):
        """Test progress percent at 100%."""
        job = ScrapeJob(
            search_query="test",
            leads_target=100,
            leads_scraped=100
        )
        db_session.add(job)
        db_session.commit()

        assert job.get_progress_percent() == 100

    def test_get_progress_percent_capped(self, db_session):
        """Test progress percent is capped at 100%."""
        job = ScrapeJob(
            search_query="test",
            leads_target=100,
            leads_scraped=150  # Over target
        )
        db_session.add(job)
        db_session.commit()

        assert job.get_progress_percent() == 100


class TestExportHistory:
    """Test suite for ExportHistory model."""

    def test_create_export_history(self, db_session):
        """Test creating an export history record."""
        export = ExportHistory(
            filename="test_export.csv",
            format="csv",
            record_count=100
        )
        db_session.add(export)
        db_session.commit()

        assert export.id is not None
        assert export.status == "completed"

    def test_export_with_filters(self, db_session):
        """Test export history with filters stored."""
        export = ExportHistory(
            filename="filtered_export.xlsx",
            format="excel",
            record_count=50,
            filters={"city": "Mumbai", "has_email": True}
        )
        db_session.add(export)
        db_session.commit()

        assert export.filters is not None
        assert export.filters["city"] == "Mumbai"
