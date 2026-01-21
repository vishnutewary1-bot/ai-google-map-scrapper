"""Export API routes."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from loguru import logger

from api.schemas.requests import ExportRequest
from api.schemas.responses import ExportResponse
from api.services.export_service import export_service

router = APIRouter()


@router.post("/export", response_model=ExportResponse)
async def export_leads(request: ExportRequest):
    """
    Export leads to various formats.

    Supported formats:
    - excel: Excel spreadsheet (.xlsx)
    - csv: CSV file
    - json: JSON file
    - cold_calling: CSV optimized for cold calling (phone, name, category)
    - email_campaign: CSV optimized for email campaigns (email, name, category)

    Optional: Also export to Google Sheets or CRM platforms.
    """
    try:
        return export_service.export(request)
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/download/{filename}")
async def download_export(filename: str):
    """Download an export file."""
    filepath = export_service.get_export_file(filename)
    if not filepath:
        raise HTTPException(status_code=404, detail="File not found")

    # Determine media type
    if filename.endswith('.xlsx'):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif filename.endswith('.csv'):
        media_type = "text/csv"
    elif filename.endswith('.json'):
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        filepath,
        filename=filename,
        media_type=media_type,
    )


@router.get("/export/list")
async def list_exports():
    """List all available export files."""
    try:
        exports = export_service.list_exports()
        return {"exports": exports, "total": len(exports)}
    except Exception as e:
        logger.error(f"Failed to list exports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/export/{filename}")
async def delete_export(filename: str):
    """Delete an export file."""
    success = export_service.delete_export(filename)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"success": True, "message": "Export deleted"}


@router.post("/export/sheets")
async def export_to_sheets(
    spreadsheet_id: str = None,
    filters: dict = None,
):
    """Export leads directly to Google Sheets."""
    try:
        from api.schemas.requests import LeadFilters

        request = ExportRequest(
            format="excel",  # Doesn't matter, sheets export is separate
            export_to_sheets=True,
            sheets_spreadsheet_id=spreadsheet_id,
            filters=LeadFilters(**filters) if filters else None,
        )

        result = export_service.export(request)

        if result.sheets_url:
            return {"success": True, "sheets_url": result.sheets_url}
        else:
            raise HTTPException(status_code=500, detail="Google Sheets export failed")

    except Exception as e:
        logger.error(f"Google Sheets export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/crm/{crm_name}")
async def export_to_crm(
    crm_name: str,
    filters: dict = None,
):
    """
    Export leads to a CRM platform.

    Supported CRMs: hubspot, salesforce, airtable, notion
    """
    valid_crms = ["hubspot", "salesforce", "airtable", "notion"]
    if crm_name not in valid_crms:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid CRM. Supported: {', '.join(valid_crms)}"
        )

    try:
        from api.schemas.requests import LeadFilters

        request = ExportRequest(
            format="json",
            export_to_crm=crm_name,
            filters=LeadFilters(**filters) if filters else None,
        )

        result = export_service.export(request)

        if result.crm_url:
            return {"success": True, "crm_url": result.crm_url}
        else:
            return {"success": True, "message": f"Exported to {crm_name}"}

    except Exception as e:
        logger.error(f"CRM export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
