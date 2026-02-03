"""Export service - business logic for data export operations."""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.schemas.requests import ExportRequest, LeadFilters
from api.schemas.responses import ExportResponse
from api.services.lead_service import lead_service

# Export utilities
try:
    from utils.exporter import export_to_excel, export_to_csv, export_to_json
    HAS_EXPORTER = True
except ImportError:
    HAS_EXPORTER = False

try:
    from utils.google_sheets_exporter import GoogleSheetsExporter
    HAS_SHEETS = True
except ImportError:
    HAS_SHEETS = False

try:
    from utils.crm_integrations import (
        export_to_hubspot,
        export_to_salesforce,
        export_to_airtable,
        export_to_notion,
    )
    HAS_CRM = True
except ImportError:
    HAS_CRM = False

# Cloud storage integration
try:
    from utils.cloud_storage import CloudStorageManager
    from config.settings import settings
    HAS_CLOUD_STORAGE = True
except ImportError:
    HAS_CLOUD_STORAGE = False
    CloudStorageManager = None


class ExportService:
    """Service for exporting leads to various formats."""

    EXPORTS_DIR = "exports"

    def __init__(self):
        """Initialize export service."""
        os.makedirs(self.EXPORTS_DIR, exist_ok=True)

    def export(self, request: ExportRequest) -> ExportResponse:
        """
        Export leads to specified format.

        Args:
            request: Export request with format and filters

        Returns:
            ExportResponse with file path or URL
        """
        try:
            # Get leads to export
            leads_data = self._get_leads_data(request)

            if not leads_data:
                return ExportResponse(
                    success=False,
                    format=request.format,
                    error="No leads to export",
                    records_exported=0,
                )

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"leads_export_{timestamp}"

            # Export based on format
            result = ExportResponse(
                success=True,
                format=request.format,
                records_exported=len(leads_data),
            )

            if request.format == "excel":
                result = self._export_excel(leads_data, base_filename, result)
            elif request.format == "csv":
                result = self._export_csv(leads_data, base_filename, result)
            elif request.format == "json":
                result = self._export_json(leads_data, base_filename, result)
            elif request.format == "cold_calling":
                result = self._export_cold_calling(leads_data, base_filename, result)
            elif request.format == "email_campaign":
                result = self._export_email_campaign(leads_data, base_filename, result)

            # Also export to Google Sheets if requested
            if request.export_to_sheets and HAS_SHEETS:
                try:
                    sheets_url = self._export_to_sheets(
                        leads_data,
                        request.sheets_spreadsheet_id
                    )
                    result.sheets_url = sheets_url
                except Exception as e:
                    logger.error(f"Google Sheets export failed: {e}")

            # Export to CRM if requested
            if request.export_to_crm and HAS_CRM:
                try:
                    crm_url = self._export_to_crm(leads_data, request.export_to_crm)
                    result.crm_url = crm_url
                except Exception as e:
                    logger.error(f"CRM export failed: {e}")

            # Upload to cloud storage if requested
            if getattr(request, 'upload_to_cloud', None) and result.filepath:
                try:
                    cloud_url = self._upload_to_cloud(
                        result.filepath,
                        getattr(request, 'cloud_provider', 's3')
                    )
                    if cloud_url:
                        result.cloud_url = cloud_url
                except Exception as e:
                    logger.error(f"Cloud upload failed: {e}")

            return result

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return ExportResponse(
                success=False,
                format=request.format,
                error=str(e),
                records_exported=0,
            )

    def _get_leads_data(self, request: ExportRequest) -> List[Dict]:
        """Get leads data based on request."""
        # If specific lead IDs provided
        if request.lead_ids:
            leads_response = lead_service.get_leads(limit=len(request.lead_ids))
            leads = [l for l in leads_response.leads if l.id in request.lead_ids]
        else:
            # Use filters
            leads_response = lead_service.get_leads(
                filters=request.filters,
                limit=10000  # Max export limit
            )
            leads = leads_response.leads

        # Convert to dictionaries
        leads_data = []
        for lead in leads:
            lead_dict = lead.model_dump()

            # Filter columns if specified
            if request.columns:
                lead_dict = {k: v for k, v in lead_dict.items() if k in request.columns}

            leads_data.append(lead_dict)

        return leads_data

    def _export_excel(
        self,
        leads_data: List[Dict],
        base_filename: str,
        result: ExportResponse
    ) -> ExportResponse:
        """Export to Excel format."""
        if not HAS_EXPORTER:
            result.success = False
            result.error = "Excel exporter not available"
            return result

        filename = f"{base_filename}.xlsx"
        filepath = os.path.join(self.EXPORTS_DIR, filename)

        export_to_excel(leads_data, filepath)

        result.filename = filename
        result.filepath = filepath
        result.download_url = f"/api/export/download/{filename}"

        return result

    def _export_csv(
        self,
        leads_data: List[Dict],
        base_filename: str,
        result: ExportResponse
    ) -> ExportResponse:
        """Export to CSV format."""
        if not HAS_EXPORTER:
            result.success = False
            result.error = "CSV exporter not available"
            return result

        filename = f"{base_filename}.csv"
        filepath = os.path.join(self.EXPORTS_DIR, filename)

        export_to_csv(leads_data, filepath)

        result.filename = filename
        result.filepath = filepath
        result.download_url = f"/api/export/download/{filename}"

        return result

    def _export_json(
        self,
        leads_data: List[Dict],
        base_filename: str,
        result: ExportResponse
    ) -> ExportResponse:
        """Export to JSON format."""
        import json

        filename = f"{base_filename}.json"
        filepath = os.path.join(self.EXPORTS_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(leads_data, f, indent=2, default=str)

        result.filename = filename
        result.filepath = filepath
        result.download_url = f"/api/export/download/{filename}"

        return result

    def _export_cold_calling(
        self,
        leads_data: List[Dict],
        base_filename: str,
        result: ExportResponse
    ) -> ExportResponse:
        """Export in cold calling format (name, phone, category, city)."""
        # Filter to only leads with phone numbers
        calling_data = []
        for lead in leads_data:
            if lead.get('phone'):
                calling_data.append({
                    'business_name': lead.get('business_name'),
                    'phone': lead.get('phone'),
                    'phone_2': lead.get('phone_2'),
                    'category': lead.get('category'),
                    'city': lead.get('city'),
                    'state': lead.get('state'),
                    'rating': lead.get('rating'),
                    'website': lead.get('website'),
                })

        if not calling_data:
            result.success = False
            result.error = "No leads with phone numbers"
            return result

        filename = f"{base_filename}_cold_calling.csv"
        filepath = os.path.join(self.EXPORTS_DIR, filename)

        if HAS_EXPORTER:
            export_to_csv(calling_data, filepath)
        else:
            import csv
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=calling_data[0].keys())
                writer.writeheader()
                writer.writerows(calling_data)

        result.filename = filename
        result.filepath = filepath
        result.download_url = f"/api/export/download/{filename}"
        result.records_exported = len(calling_data)

        return result

    def _export_email_campaign(
        self,
        leads_data: List[Dict],
        base_filename: str,
        result: ExportResponse
    ) -> ExportResponse:
        """Export in email campaign format (name, email, category)."""
        # Filter to only leads with email
        email_data = []
        for lead in leads_data:
            if lead.get('email'):
                email_data.append({
                    'business_name': lead.get('business_name'),
                    'email': lead.get('email'),
                    'email_2': lead.get('email_2'),
                    'contact_person_1': lead.get('contact_person_1'),
                    'contact_email_1': lead.get('contact_email_1'),
                    'category': lead.get('category'),
                    'city': lead.get('city'),
                    'website': lead.get('website'),
                })

        if not email_data:
            result.success = False
            result.error = "No leads with email addresses"
            return result

        filename = f"{base_filename}_email_campaign.csv"
        filepath = os.path.join(self.EXPORTS_DIR, filename)

        if HAS_EXPORTER:
            export_to_csv(email_data, filepath)
        else:
            import csv
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=email_data[0].keys())
                writer.writeheader()
                writer.writerows(email_data)

        result.filename = filename
        result.filepath = filepath
        result.download_url = f"/api/export/download/{filename}"
        result.records_exported = len(email_data)

        return result

    def _export_to_sheets(
        self,
        leads_data: List[Dict],
        spreadsheet_id: Optional[str] = None
    ) -> str:
        """Export to Google Sheets."""
        exporter = GoogleSheetsExporter()
        sheet_name = f"Leads Export - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        if spreadsheet_id:
            return exporter.export_to_existing_sheet(leads_data, spreadsheet_id, sheet_name)
        else:
            return exporter.export_to_new_sheet(leads_data, sheet_name)

    def _export_to_crm(self, leads_data: List[Dict], crm: str) -> str:
        """Export to CRM platform."""
        if crm == "hubspot":
            return export_to_hubspot(leads_data)
        elif crm == "salesforce":
            return export_to_salesforce(leads_data)
        elif crm == "airtable":
            return export_to_airtable(leads_data)
        elif crm == "notion":
            return export_to_notion(leads_data)
        else:
            raise ValueError(f"Unknown CRM: {crm}")

    def get_export_file(self, filename: str) -> Optional[str]:
        """Get full path to export file."""
        filepath = os.path.join(self.EXPORTS_DIR, filename)
        if os.path.exists(filepath):
            return filepath
        return None

    def list_exports(self) -> List[Dict]:
        """List all export files."""
        exports = []
        for filename in os.listdir(self.EXPORTS_DIR):
            filepath = os.path.join(self.EXPORTS_DIR, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                exports.append({
                    "filename": filename,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "download_url": f"/api/export/download/{filename}",
                })
        return sorted(exports, key=lambda x: x["created_at"], reverse=True)

    def delete_export(self, filename: str) -> bool:
        """Delete an export file."""
        filepath = os.path.join(self.EXPORTS_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    def _upload_to_cloud(self, filepath: str, provider: str = 's3') -> Optional[str]:
        """
        Upload export file to cloud storage.

        Args:
            filepath: Local file path to upload
            provider: Cloud provider ('s3' or 'gcs')

        Returns:
            Cloud URL if successful, None otherwise
        """
        if not HAS_CLOUD_STORAGE:
            logger.warning("Cloud storage not available")
            return None

        try:
            cloud = CloudStorageManager()

            if provider == 's3':
                # Initialize S3
                if not (settings.aws_access_key and settings.aws_secret_key and settings.s3_bucket):
                    logger.warning("S3 not configured")
                    return None

                cloud.init_s3(
                    settings.aws_access_key,
                    settings.aws_secret_key,
                    settings.aws_region
                )

                result = cloud.upload_to_s3(
                    filepath,
                    settings.s3_bucket,
                    make_public=True
                )

            elif provider == 'gcs':
                # Initialize GCS
                if not (settings.gcs_credentials_path and settings.gcs_bucket):
                    logger.warning("GCS not configured")
                    return None

                cloud.init_gcs(settings.gcs_credentials_path)

                result = cloud.upload_to_gcs(
                    filepath,
                    settings.gcs_bucket,
                    make_public=True
                )

            else:
                logger.warning(f"Unknown cloud provider: {provider}")
                return None

            if result.success:
                logger.info(f"Uploaded to {provider}: {result.url}")
                return result.url
            else:
                logger.error(f"Cloud upload failed: {result.error}")
                return None

        except Exception as e:
            logger.error(f"Cloud upload error: {e}")
            return None


# Singleton instance
export_service = ExportService()
