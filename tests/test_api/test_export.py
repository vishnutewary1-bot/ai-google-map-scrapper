"""Tests for export API endpoints."""
import pytest


class TestExportEndpoint:
    """Test suite for /api/export endpoints."""

    def test_export_csv_returns_200(self, client):
        """Test CSV export returns 200."""
        response = client.post(
            "/api/export",
            json={"format": "csv", "limit": 10}
        )
        assert response.status_code == 200

    def test_export_json_returns_200(self, client):
        """Test JSON export returns 200."""
        response = client.post(
            "/api/export",
            json={"format": "json", "limit": 10}
        )
        assert response.status_code == 200

    def test_export_excel_returns_200(self, client):
        """Test Excel export returns 200."""
        response = client.post(
            "/api/export",
            json={"format": "excel", "limit": 10}
        )
        assert response.status_code == 200

    def test_export_returns_filename(self, client):
        """Test that export returns a filename."""
        response = client.post(
            "/api/export",
            json={"format": "csv", "limit": 10}
        )
        data = response.json()
        assert "filename" in data
        assert data["filename"].endswith(".csv")

    def test_export_returns_download_url(self, client):
        """Test that export returns a download URL."""
        response = client.post(
            "/api/export",
            json={"format": "csv", "limit": 10}
        )
        data = response.json()
        assert "download_url" in data

    def test_export_returns_records_count(self, client):
        """Test that export returns records exported count."""
        response = client.post(
            "/api/export",
            json={"format": "csv", "limit": 10}
        )
        data = response.json()
        assert "records_exported" in data
        assert isinstance(data["records_exported"], int)

    def test_export_with_filters(self, client):
        """Test export with filters."""
        response = client.post(
            "/api/export",
            json={
                "format": "csv",
                "limit": 10,
                "filters": {
                    "city": "Mumbai",
                    "has_email": True
                }
            }
        )
        assert response.status_code == 200

    def test_export_cold_calling_format(self, client):
        """Test cold calling format export."""
        response = client.post(
            "/api/export",
            json={"format": "cold_calling", "limit": 10}
        )
        assert response.status_code == 200

    def test_export_email_campaign_format(self, client):
        """Test email campaign format export."""
        response = client.post(
            "/api/export",
            json={"format": "email_campaign", "limit": 10}
        )
        assert response.status_code == 200


class TestExportDownload:
    """Test suite for /api/export/download endpoint."""

    def test_download_nonexistent_file_returns_404(self, client):
        """Test that downloading non-existent file returns 404."""
        response = client.get("/api/export/download/nonexistent.csv")
        assert response.status_code == 404
