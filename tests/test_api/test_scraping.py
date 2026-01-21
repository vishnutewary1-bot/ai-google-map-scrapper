"""Tests for scraping API endpoints."""
import pytest


class TestScrapingEndpoint:
    """Test suite for /api/scrape endpoints."""

    def test_scrape_requires_query(self, client):
        """Test that scrape endpoint requires query parameter."""
        response = client.post(
            "/api/scrape",
            json={}
        )
        assert response.status_code == 422  # Validation error

    def test_scrape_accepts_valid_request(self, client):
        """Test that scrape endpoint accepts valid request."""
        response = client.post(
            "/api/scrape",
            json={
                "query": "restaurants in Mumbai",
                "max_results": 10
            }
        )
        # Should return 200 (job created) or 202 (accepted)
        assert response.status_code in [200, 202]

    def test_scrape_returns_job_id(self, client):
        """Test that scrape returns a job ID."""
        response = client.post(
            "/api/scrape",
            json={
                "query": "hotels in Delhi",
                "max_results": 5
            }
        )
        if response.status_code == 200:
            data = response.json()
            assert "job_id" in data or "id" in data


class TestJobsEndpoint:
    """Test suite for /api/jobs endpoints."""

    def test_get_jobs_returns_200(self, client):
        """Test that GET /api/jobs returns 200."""
        response = client.get("/api/jobs")
        assert response.status_code == 200

    def test_get_jobs_returns_list(self, client):
        """Test that jobs endpoint returns a list."""
        response = client.get("/api/jobs")
        data = response.json()
        assert isinstance(data, list) or "jobs" in data

    def test_get_nonexistent_job_returns_404(self, client):
        """Test that getting non-existent job returns 404."""
        response = client.get("/api/jobs/999999")
        assert response.status_code == 404
