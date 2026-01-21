"""Pytest configuration and fixtures for MapLeads Pro tests."""
import os
import sys
import pytest
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set test environment
os.environ["DB_TYPE"] = "sqlite"
os.environ["DB_NAME"] = "test_mapleads"
os.environ["AUTH_ENABLED"] = "False"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from database.models import Base, BusinessLead, ScrapeJob
from api.app import create_app


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create a new database session for each test."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="module")
def client():
    """Create a test client for API tests."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def sample_lead_data():
    """Sample lead data for testing."""
    return {
        "business_name": "Test Business",
        "category": "Restaurant",
        "full_address": "123 Test St, Test City, TS 12345",
        "city": "Test City",
        "state": "Test State",
        "country": "India",
        "pin_code": "12345",
        "phone": "+91 98765 43210",
        "email": "test@testbusiness.com",
        "website": "https://testbusiness.com",
        "rating": 4.5,
        "review_count": 100,
        "latitude": 19.0760,
        "longitude": 72.8777,
        "place_id": "test_place_id_123"
    }


@pytest.fixture
def sample_leads(db_session, sample_lead_data):
    """Create sample leads in the test database."""
    leads = []
    for i in range(5):
        lead_data = sample_lead_data.copy()
        lead_data["business_name"] = f"Test Business {i+1}"
        lead_data["place_id"] = f"test_place_id_{i+1}"
        lead_data["email"] = f"test{i+1}@business.com"

        lead = BusinessLead(**lead_data)
        db_session.add(lead)
        leads.append(lead)

    db_session.commit()
    return leads


@pytest.fixture
def sample_scrape_job(db_session):
    """Create a sample scrape job."""
    job = ScrapeJob(
        search_query="restaurants in Mumbai",
        location="Mumbai",
        max_results=100,
        status="completed",
        leads_scraped=50,
        leads_target=100
    )
    db_session.add(job)
    db_session.commit()
    return job
