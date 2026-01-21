"""Tests for leads API endpoints."""
import pytest


class TestLeadsEndpoint:
    """Test suite for /api/leads endpoints."""

    def test_get_leads_returns_200(self, client):
        """Test that GET /api/leads returns 200."""
        response = client.get("/api/leads")
        assert response.status_code == 200

    def test_get_leads_returns_list(self, client):
        """Test that leads endpoint returns a list."""
        response = client.get("/api/leads")
        data = response.json()
        assert "leads" in data
        assert isinstance(data["leads"], list)

    def test_get_leads_with_limit(self, client):
        """Test leads endpoint with limit parameter."""
        response = client.get("/api/leads?limit=5")
        data = response.json()
        assert data["limit"] == 5

    def test_get_leads_with_offset(self, client):
        """Test leads endpoint with offset parameter."""
        response = client.get("/api/leads?offset=10")
        data = response.json()
        assert data["offset"] == 10

    def test_get_leads_includes_total(self, client):
        """Test that leads response includes total count."""
        response = client.get("/api/leads")
        data = response.json()
        assert "total" in data
        assert isinstance(data["total"], int)

    def test_get_leads_with_city_filter(self, client):
        """Test leads endpoint with city filter."""
        response = client.get("/api/leads?city=Mumbai")
        assert response.status_code == 200

    def test_get_leads_with_category_filter(self, client):
        """Test leads endpoint with category filter."""
        response = client.get("/api/leads?category=Restaurant")
        assert response.status_code == 200

    def test_get_leads_with_has_email_filter(self, client):
        """Test leads endpoint filtering by has_email."""
        response = client.get("/api/leads?has_email=true")
        assert response.status_code == 200

    def test_get_leads_with_has_phone_filter(self, client):
        """Test leads endpoint filtering by has_phone."""
        response = client.get("/api/leads?has_phone=true")
        assert response.status_code == 200

    def test_get_leads_with_min_rating_filter(self, client):
        """Test leads endpoint filtering by minimum rating."""
        response = client.get("/api/leads?min_rating=4.0")
        assert response.status_code == 200


class TestLeadDetailEndpoint:
    """Test suite for /api/leads/{id} endpoint."""

    def test_get_nonexistent_lead_returns_404(self, client):
        """Test that getting a non-existent lead returns 404."""
        response = client.get("/api/leads/999999")
        assert response.status_code == 404

    def test_delete_nonexistent_lead_returns_404(self, client):
        """Test that deleting a non-existent lead returns 404."""
        response = client.delete("/api/leads/999999")
        assert response.status_code == 404
