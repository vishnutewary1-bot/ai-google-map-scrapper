"""Tests for health check endpoint."""
import pytest


class TestHealthEndpoint:
    """Test suite for /api/health endpoint."""

    def test_health_check_returns_200(self, client):
        """Test that health check returns 200 OK."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_check_returns_healthy_status(self, client):
        """Test that health check returns healthy status."""
        response = client.get("/api/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_includes_version(self, client):
        """Test that health check includes version."""
        response = client.get("/api/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == "2.0.0"

    def test_health_check_includes_database_status(self, client):
        """Test that health check includes database status."""
        response = client.get("/api/health")
        data = response.json()
        assert "database" in data

    def test_health_check_includes_timestamp(self, client):
        """Test that health check includes timestamp."""
        response = client.get("/api/health")
        data = response.json()
        assert "timestamp" in data
