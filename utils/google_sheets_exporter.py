"""Google Sheets export integration for MapLeads Pro."""
import json
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
from loguru import logger

try:
    import gspread
    from google.oauth2.service_account import Credentials
    from google.oauth2.credentials import Credentials as UserCredentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

from database import db_manager, BusinessLead


# Google Sheets API scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]


class GoogleSheetsExporter:
    """Export scraped data directly to Google Sheets."""

    def __init__(self, credentials_path: str = "config/google_credentials.json"):
        """
        Initialize Google Sheets exporter.

        Args:
            credentials_path: Path to Google service account or OAuth credentials JSON
        """
        if not GSPREAD_AVAILABLE:
            raise ImportError("gspread and google-auth packages are required. Install with: pip install gspread google-auth google-auth-oauthlib")

        self.credentials_path = Path(credentials_path)
        self.token_path = Path("config/google_token.json")
        self.client = None
        self._authenticated = False

    def authenticate_service_account(self, credentials_path: Optional[str] = None) -> bool:
        """
        Authenticate using a service account.

        Args:
            credentials_path: Path to service account JSON file

        Returns:
            True if authentication successful
        """
        try:
            creds_path = Path(credentials_path) if credentials_path else self.credentials_path

            if not creds_path.exists():
                logger.error(f"Credentials file not found: {creds_path}")
                return False

            credentials = Credentials.from_service_account_file(
                str(creds_path),
                scopes=SCOPES
            )

            self.client = gspread.authorize(credentials)
            self._authenticated = True
            logger.info("Successfully authenticated with Google Sheets (Service Account)")
            return True

        except Exception as e:
            logger.error(f"Failed to authenticate with service account: {e}")
            return False

    def authenticate_oauth(self, credentials_path: Optional[str] = None) -> bool:
        """
        Authenticate using OAuth2 (for personal accounts).

        Args:
            credentials_path: Path to OAuth credentials JSON file

        Returns:
            True if authentication successful
        """
        try:
            creds_path = Path(credentials_path) if credentials_path else self.credentials_path
            creds = None

            # Check for existing token
            if self.token_path.exists():
                with open(self.token_path, 'r') as token:
                    token_data = json.load(token)
                    creds = UserCredentials.from_authorized_user_info(token_data, SCOPES)

            # Refresh or get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not creds_path.exists():
                        logger.error(f"OAuth credentials file not found: {creds_path}")
                        return False

                    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                    creds = flow.run_local_server(port=0)

                # Save token for future use
                self.token_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())

            self.client = gspread.authorize(creds)
            self._authenticated = True
            logger.info("Successfully authenticated with Google Sheets (OAuth)")
            return True

        except Exception as e:
            logger.error(f"Failed to authenticate with OAuth: {e}")
            return False

    def create_spreadsheet(self, title: str, share_with: Optional[List[str]] = None) -> Optional[str]:
        """
        Create a new Google Spreadsheet.

        Args:
            title: Spreadsheet title
            share_with: List of email addresses to share with

        Returns:
            Spreadsheet URL if successful, None otherwise
        """
        if not self._authenticated:
            logger.error("Not authenticated. Call authenticate_service_account() or authenticate_oauth() first.")
            return None

        try:
            spreadsheet = self.client.create(title)

            # Share with specified emails
            if share_with:
                for email in share_with:
                    spreadsheet.share(email, perm_type='user', role='writer')
                    logger.info(f"Shared spreadsheet with: {email}")

            logger.info(f"Created spreadsheet: {spreadsheet.url}")
            return spreadsheet.url

        except Exception as e:
            logger.error(f"Failed to create spreadsheet: {e}")
            return None

    def export_to_sheets(
        self,
        spreadsheet_url: Optional[str] = None,
        spreadsheet_name: Optional[str] = None,
        sheet_name: str = "Leads",
        data: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None,
        include_headers: bool = True,
        clear_existing: bool = False,
        share_with: Optional[List[str]] = None
    ) -> Dict:
        """
        Export leads to Google Sheets.

        Args:
            spreadsheet_url: URL of existing spreadsheet (if None, creates new)
            spreadsheet_name: Name for new spreadsheet (if spreadsheet_url is None)
            sheet_name: Name of the worksheet
            data: List of lead dictionaries (if None, fetches from DB)
            filters: Database filters to apply
            include_headers: Whether to include header row
            clear_existing: Whether to clear existing data before export
            share_with: List of emails to share new spreadsheet with

        Returns:
            Dict with export results (url, rows_exported, etc.)
        """
        if not self._authenticated:
            logger.error("Not authenticated. Call authenticate_service_account() or authenticate_oauth() first.")
            return {"success": False, "error": "Not authenticated"}

        try:
            # Get data from database if not provided
            if data is None:
                data = self._fetch_from_database(filters)

            if not data:
                logger.warning("No data to export")
                return {"success": False, "error": "No data to export"}

            # Open or create spreadsheet
            if spreadsheet_url:
                spreadsheet = self.client.open_by_url(spreadsheet_url)
            else:
                title = spreadsheet_name or f"MapLeads Export - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                spreadsheet = self.client.create(title)

                if share_with:
                    for email in share_with:
                        spreadsheet.share(email, perm_type='user', role='writer')

            # Get or create worksheet
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=len(data) + 10, cols=25)

            # Clear existing data if requested
            if clear_existing:
                worksheet.clear()

            # Define columns for export
            columns = [
                'id', 'business_name', 'phone', 'email', 'website', 'category',
                'full_address', 'city', 'state', 'pin_code', 'rating', 'review_count',
                'data_quality_score', 'social_facebook', 'social_instagram',
                'social_twitter', 'social_linkedin', 'place_id', 'maps_url', 'scraped_at'
            ]

            # Prepare rows
            rows = []

            if include_headers:
                # Format headers
                headers = [col.replace('_', ' ').title() for col in columns]
                rows.append(headers)

            # Add data rows
            for lead in data:
                row = []
                for col in columns:
                    value = lead.get(col, '')
                    # Convert datetime to string
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    elif value is None:
                        value = ''
                    row.append(str(value))
                rows.append(row)

            # Find starting row (append mode)
            if not clear_existing and not include_headers:
                start_row = len(worksheet.get_all_values()) + 1
            else:
                start_row = 1

            # Update cells in batch
            if rows:
                end_col = chr(ord('A') + len(columns) - 1)
                end_row = start_row + len(rows) - 1
                cell_range = f'A{start_row}:{end_col}{end_row}'

                worksheet.update(cell_range, rows)

                # Format header row if included
                if include_headers and start_row == 1:
                    worksheet.format('A1:T1', {
                        'backgroundColor': {'red': 0.27, 'green': 0.45, 'blue': 0.77},
                        'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                        'horizontalAlignment': 'CENTER'
                    })

                    # Freeze header row
                    worksheet.freeze(rows=1)

                    # Auto-resize columns
                    worksheet.columns_auto_resize(0, len(columns) - 1)

            result = {
                "success": True,
                "spreadsheet_url": spreadsheet.url,
                "spreadsheet_id": spreadsheet.id,
                "sheet_name": sheet_name,
                "rows_exported": len(data),
                "total_rows": len(rows),
                "exported_at": datetime.now().isoformat()
            }

            logger.info(f"Exported {len(data)} leads to Google Sheets: {spreadsheet.url}")
            return result

        except Exception as e:
            logger.error(f"Failed to export to Google Sheets: {e}")
            return {"success": False, "error": str(e)}

    def append_to_sheet(
        self,
        spreadsheet_url: str,
        sheet_name: str = "Leads",
        data: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None
    ) -> Dict:
        """
        Append new leads to existing Google Sheet (incremental export).

        Args:
            spreadsheet_url: URL of the spreadsheet
            sheet_name: Name of the worksheet
            data: List of lead dictionaries
            filters: Database filters

        Returns:
            Dict with append results
        """
        return self.export_to_sheets(
            spreadsheet_url=spreadsheet_url,
            sheet_name=sheet_name,
            data=data,
            filters=filters,
            include_headers=False,
            clear_existing=False
        )

    def sync_to_sheet(
        self,
        spreadsheet_url: str,
        sheet_name: str = "Leads",
        filters: Optional[Dict] = None,
        last_sync_id: Optional[int] = None
    ) -> Dict:
        """
        Sync only new leads since last sync (based on ID).

        Args:
            spreadsheet_url: URL of the spreadsheet
            sheet_name: Name of the worksheet
            filters: Database filters
            last_sync_id: Only sync leads with ID > this value

        Returns:
            Dict with sync results including new last_sync_id
        """
        try:
            # Fetch only new leads
            with db_manager.get_session() as session:
                query = session.query(BusinessLead)

                if last_sync_id:
                    query = query.filter(BusinessLead.id > last_sync_id)

                # Apply additional filters
                if filters:
                    if filters.get('has_phone'):
                        query = query.filter(BusinessLead.phone.isnot(None))
                    if filters.get('has_email'):
                        query = query.filter(BusinessLead.email.isnot(None))
                    if filters.get('city'):
                        query = query.filter(BusinessLead.city == filters['city'])

                leads = query.order_by(BusinessLead.id.asc()).all()
                data = [lead.to_dict() for lead in leads]

                # Get new last sync ID
                new_last_sync_id = leads[-1].id if leads else last_sync_id

            if not data:
                return {
                    "success": True,
                    "message": "No new leads to sync",
                    "rows_synced": 0,
                    "last_sync_id": last_sync_id
                }

            # Append to sheet
            result = self.append_to_sheet(
                spreadsheet_url=spreadsheet_url,
                sheet_name=sheet_name,
                data=data
            )

            if result.get("success"):
                result["last_sync_id"] = new_last_sync_id
                result["rows_synced"] = len(data)

            return result

        except Exception as e:
            logger.error(f"Failed to sync to Google Sheets: {e}")
            return {"success": False, "error": str(e)}

    def _fetch_from_database(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch data from database with optional filters."""
        try:
            with db_manager.get_session() as session:
                query = session.query(BusinessLead)

                if filters:
                    if filters.get('has_phone'):
                        query = query.filter(BusinessLead.phone.isnot(None))
                    if filters.get('has_website'):
                        query = query.filter(BusinessLead.website.isnot(None))
                    if filters.get('has_email'):
                        query = query.filter(BusinessLead.email.isnot(None))
                    if filters.get('city'):
                        query = query.filter(BusinessLead.city == filters['city'])
                    if filters.get('state'):
                        query = query.filter(BusinessLead.state == filters['state'])
                    if filters.get('category'):
                        query = query.filter(BusinessLead.category == filters['category'])
                    if filters.get('min_quality_score'):
                        query = query.filter(BusinessLead.data_quality_score >= filters['min_quality_score'])
                    if filters.get('search_query'):
                        query = query.filter(BusinessLead.search_query == filters['search_query'])

                results = query.all()
                return [lead.to_dict() for lead in results]

        except Exception as e:
            logger.error(f"Error fetching from database: {e}")
            return []

    def list_spreadsheets(self, limit: int = 20) -> List[Dict]:
        """
        List recent spreadsheets accessible by the authenticated account.

        Args:
            limit: Maximum number of spreadsheets to return

        Returns:
            List of spreadsheet info dicts
        """
        if not self._authenticated:
            return []

        try:
            spreadsheets = self.client.list_spreadsheet_files(limit=limit)
            return [
                {
                    "id": s.get('id'),
                    "name": s.get('name'),
                    "url": f"https://docs.google.com/spreadsheets/d/{s.get('id')}"
                }
                for s in spreadsheets
            ]
        except Exception as e:
            logger.error(f"Failed to list spreadsheets: {e}")
            return []

    def get_sheet_info(self, spreadsheet_url: str) -> Optional[Dict]:
        """
        Get information about a spreadsheet.

        Args:
            spreadsheet_url: URL of the spreadsheet

        Returns:
            Dict with spreadsheet info
        """
        if not self._authenticated:
            return None

        try:
            spreadsheet = self.client.open_by_url(spreadsheet_url)
            worksheets = spreadsheet.worksheets()

            return {
                "id": spreadsheet.id,
                "title": spreadsheet.title,
                "url": spreadsheet.url,
                "worksheets": [
                    {
                        "name": ws.title,
                        "rows": ws.row_count,
                        "cols": ws.col_count
                    }
                    for ws in worksheets
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get spreadsheet info: {e}")
            return None


# Singleton instance
_sheets_exporter = None

def get_sheets_exporter() -> GoogleSheetsExporter:
    """Get or create the Google Sheets exporter instance."""
    global _sheets_exporter
    if _sheets_exporter is None:
        _sheets_exporter = GoogleSheetsExporter()
    return _sheets_exporter
