"""Airtable and Notion export integrations for MapLeads Pro."""
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime
from loguru import logger

try:
    from pyairtable import Api as AirtableApi
    from pyairtable import Table
    AIRTABLE_AVAILABLE = True
except ImportError:
    AIRTABLE_AVAILABLE = False

try:
    from notion_client import AsyncClient as NotionClient
    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False

from database import db_manager, BusinessLead


class AirtableExporter:
    """Export leads to Airtable."""

    def __init__(self, api_key: str, base_id: Optional[str] = None):
        """
        Initialize Airtable exporter.

        Args:
            api_key: Airtable personal access token
            base_id: Default Airtable base ID
        """
        if not AIRTABLE_AVAILABLE:
            raise ImportError("pyairtable is required. Install with: pip install pyairtable")

        self.api = AirtableApi(api_key)
        self.base_id = base_id
        self.stats = {
            "records_created": 0,
            "records_updated": 0,
            "failed": 0
        }

    async def export_leads(
        self,
        base_id: Optional[str] = None,
        table_name: str = "Leads",
        leads: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None,
        update_existing: bool = True
    ) -> Dict:
        """
        Export leads to Airtable.

        Args:
            base_id: Airtable base ID
            table_name: Table name in the base
            leads: List of lead dictionaries
            filters: Database filters
            update_existing: Whether to update existing records

        Returns:
            Dict with export results
        """
        target_base = base_id or self.base_id
        if not target_base:
            return {"success": False, "error": "No base_id specified"}

        # Fetch leads if not provided
        if leads is None:
            leads = self._fetch_leads(filters)

        if not leads:
            return {"success": True, "message": "No leads to export", "created": 0}

        results = {
            "success": True,
            "created": 0,
            "updated": 0,
            "failed": 0,
            "errors": []
        }

        try:
            table = self.api.table(target_base, table_name)
            loop = asyncio.get_event_loop()

            for lead in leads:
                try:
                    record = self._map_lead_to_airtable(lead)

                    # Check if record exists (by place_id or phone)
                    existing = None
                    if update_existing and lead.get("place_id"):
                        existing_records = await loop.run_in_executor(
                            None,
                            lambda: table.all(formula=f"{{Place ID}} = '{lead['place_id']}'")
                        )
                        if existing_records:
                            existing = existing_records[0]

                    if existing:
                        # Update existing record
                        await loop.run_in_executor(
                            None,
                            lambda: table.update(existing["id"], record)
                        )
                        results["updated"] += 1
                        self.stats["records_updated"] += 1
                    else:
                        # Create new record
                        await loop.run_in_executor(
                            None,
                            lambda: table.create(record)
                        )
                        results["created"] += 1
                        self.stats["records_created"] += 1

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "lead_id": lead.get("id"),
                        "error": str(e)
                    })
                    self.stats["failed"] += 1
                    logger.error(f"Error exporting lead to Airtable: {e}")

            logger.info(f"Airtable export complete: {results['created']} created, {results['updated']} updated")

        except Exception as e:
            results["success"] = False
            results["error"] = str(e)
            logger.error(f"Airtable export failed: {e}")

        return results

    def _map_lead_to_airtable(self, lead: Dict) -> Dict:
        """Map lead fields to Airtable record."""
        return {
            "Business Name": lead.get("business_name"),
            "Phone": lead.get("phone"),
            "Email": lead.get("email"),
            "Website": lead.get("website"),
            "Category": lead.get("category"),
            "Full Address": lead.get("full_address"),
            "City": lead.get("city"),
            "State": lead.get("state"),
            "Pin Code": lead.get("pin_code"),
            "Rating": lead.get("rating"),
            "Review Count": lead.get("review_count"),
            "Quality Score": lead.get("data_quality_score"),
            "Place ID": lead.get("place_id"),
            "Maps URL": lead.get("maps_url"),
            "Facebook": lead.get("social_facebook"),
            "Instagram": lead.get("social_instagram"),
            "LinkedIn": lead.get("social_linkedin"),
            "Scraped At": lead.get("scraped_at"),
            "Source": "Google Maps Scraper"
        }

    async def create_base_with_table(
        self,
        base_name: str = "MapLeads",
        workspace_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a new Airtable base with leads table.
        Note: Requires enterprise Airtable plan.

        Args:
            base_name: Name for the new base
            workspace_id: Airtable workspace ID

        Returns:
            Base ID if created successfully
        """
        logger.warning("Creating bases requires Airtable Enterprise. Use existing base instead.")
        return None

    def _fetch_leads(self, filters: Optional[Dict]) -> List[Dict]:
        """Fetch leads from database."""
        try:
            with db_manager.get_session() as session:
                query = session.query(BusinessLead)

                if filters:
                    if filters.get("has_phone"):
                        query = query.filter(BusinessLead.phone.isnot(None))
                    if filters.get("has_email"):
                        query = query.filter(BusinessLead.email.isnot(None))
                    if filters.get("city"):
                        query = query.filter(BusinessLead.city == filters["city"])
                    if filters.get("min_quality_score"):
                        query = query.filter(
                            BusinessLead.data_quality_score >= filters["min_quality_score"]
                        )

                results = query.all()
                return [lead.to_dict() for lead in results]
        except Exception as e:
            logger.error(f"Error fetching leads: {e}")
            return []


class NotionExporter:
    """Export leads to Notion database."""

    def __init__(self, api_key: str, database_id: Optional[str] = None):
        """
        Initialize Notion exporter.

        Args:
            api_key: Notion integration token
            database_id: Default Notion database ID
        """
        if not NOTION_AVAILABLE:
            raise ImportError("notion-client is required. Install with: pip install notion-client")

        self.client = NotionClient(auth=api_key)
        self.database_id = database_id
        self.stats = {
            "pages_created": 0,
            "pages_updated": 0,
            "failed": 0
        }

    async def export_leads(
        self,
        database_id: Optional[str] = None,
        leads: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None,
        update_existing: bool = True
    ) -> Dict:
        """
        Export leads to Notion database.

        Args:
            database_id: Notion database ID
            leads: List of lead dictionaries
            filters: Database filters
            update_existing: Whether to update existing pages

        Returns:
            Dict with export results
        """
        target_db = database_id or self.database_id
        if not target_db:
            return {"success": False, "error": "No database_id specified"}

        # Fetch leads if not provided
        if leads is None:
            leads = self._fetch_leads(filters)

        if not leads:
            return {"success": True, "message": "No leads to export", "created": 0}

        results = {
            "success": True,
            "created": 0,
            "updated": 0,
            "failed": 0,
            "errors": []
        }

        try:
            for lead in leads:
                try:
                    properties = self._map_lead_to_notion(lead)

                    # Check if page exists (by place_id in title)
                    existing = None
                    if update_existing and lead.get("place_id"):
                        existing = await self._find_existing_page(
                            target_db,
                            lead["place_id"]
                        )

                    if existing:
                        # Update existing page
                        await self.client.pages.update(
                            page_id=existing["id"],
                            properties=properties
                        )
                        results["updated"] += 1
                        self.stats["pages_updated"] += 1
                    else:
                        # Create new page
                        await self.client.pages.create(
                            parent={"database_id": target_db},
                            properties=properties
                        )
                        results["created"] += 1
                        self.stats["pages_created"] += 1

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "lead_id": lead.get("id"),
                        "error": str(e)
                    })
                    self.stats["failed"] += 1
                    logger.error(f"Error exporting lead to Notion: {e}")

            logger.info(f"Notion export complete: {results['created']} created, {results['updated']} updated")

        except Exception as e:
            results["success"] = False
            results["error"] = str(e)
            logger.error(f"Notion export failed: {e}")

        return results

    async def _find_existing_page(
        self,
        database_id: str,
        place_id: str
    ) -> Optional[Dict]:
        """Find existing page by place_id."""
        try:
            response = await self.client.databases.query(
                database_id=database_id,
                filter={
                    "property": "Place ID",
                    "rich_text": {
                        "equals": place_id
                    }
                }
            )
            if response.get("results"):
                return response["results"][0]
        except Exception as e:
            logger.debug(f"Error finding existing page: {e}")
        return None

    def _map_lead_to_notion(self, lead: Dict) -> Dict:
        """Map lead fields to Notion page properties."""
        properties = {
            "Name": {
                "title": [{"text": {"content": lead.get("business_name", "Unknown")}}]
            },
            "Phone": {
                "phone_number": lead.get("phone")
            },
            "Email": {
                "email": lead.get("email")
            },
            "Category": {
                "select": {"name": lead.get("category", "Other")} if lead.get("category") else None
            },
            "City": {
                "rich_text": [{"text": {"content": lead.get("city", "")}}]
            },
            "State": {
                "rich_text": [{"text": {"content": lead.get("state", "")}}]
            },
            "Quality Score": {
                "number": lead.get("data_quality_score", 0)
            },
            "Rating": {
                "number": lead.get("rating")
            },
            "Review Count": {
                "number": lead.get("review_count", 0)
            },
            "Place ID": {
                "rich_text": [{"text": {"content": lead.get("place_id", "")}}]
            },
            "Source": {
                "select": {"name": "Google Maps"}
            }
        }

        # Add URL properties
        if lead.get("website"):
            properties["Website"] = {"url": lead["website"]}

        if lead.get("maps_url"):
            properties["Maps URL"] = {"url": lead["maps_url"]}

        # Remove None values
        return {k: v for k, v in properties.items() if v is not None}

    async def create_database(
        self,
        parent_page_id: str,
        database_name: str = "MapLeads"
    ) -> Optional[str]:
        """
        Create a new Notion database with lead properties.

        Args:
            parent_page_id: Parent page ID
            database_name: Name for the database

        Returns:
            Database ID if created successfully
        """
        try:
            response = await self.client.databases.create(
                parent={"page_id": parent_page_id},
                title=[{"type": "text", "text": {"content": database_name}}],
                properties={
                    "Name": {"title": {}},
                    "Phone": {"phone_number": {}},
                    "Email": {"email": {}},
                    "Website": {"url": {}},
                    "Category": {"select": {"options": []}},
                    "City": {"rich_text": {}},
                    "State": {"rich_text": {}},
                    "Quality Score": {"number": {"format": "number"}},
                    "Rating": {"number": {"format": "number"}},
                    "Review Count": {"number": {"format": "number"}},
                    "Place ID": {"rich_text": {}},
                    "Maps URL": {"url": {}},
                    "Source": {
                        "select": {
                            "options": [
                                {"name": "Google Maps", "color": "blue"}
                            ]
                        }
                    },
                    "Status": {
                        "select": {
                            "options": [
                                {"name": "New", "color": "gray"},
                                {"name": "Contacted", "color": "yellow"},
                                {"name": "Qualified", "color": "green"},
                                {"name": "Not Interested", "color": "red"}
                            ]
                        }
                    }
                }
            )

            database_id = response["id"]
            self.database_id = database_id
            logger.info(f"Created Notion database: {database_id}")
            return database_id

        except Exception as e:
            logger.error(f"Error creating Notion database: {e}")
            return None

    def _fetch_leads(self, filters: Optional[Dict]) -> List[Dict]:
        """Fetch leads from database."""
        try:
            with db_manager.get_session() as session:
                query = session.query(BusinessLead)

                if filters:
                    if filters.get("has_phone"):
                        query = query.filter(BusinessLead.phone.isnot(None))
                    if filters.get("has_email"):
                        query = query.filter(BusinessLead.email.isnot(None))
                    if filters.get("city"):
                        query = query.filter(BusinessLead.city == filters["city"])
                    if filters.get("min_quality_score"):
                        query = query.filter(
                            BusinessLead.data_quality_score >= filters["min_quality_score"]
                        )

                results = query.all()
                return [lead.to_dict() for lead in results]
        except Exception as e:
            logger.error(f"Error fetching leads: {e}")
            return []


class ExportManager:
    """Unified export manager for all platforms."""

    def __init__(self):
        self.airtable: Optional[AirtableExporter] = None
        self.notion: Optional[NotionExporter] = None
        self._configured_exports = []

    def configure_airtable(self, api_key: str, base_id: Optional[str] = None) -> bool:
        """Configure Airtable export."""
        try:
            self.airtable = AirtableExporter(api_key, base_id)
            self._configured_exports.append("airtable")
            logger.info("Airtable export configured")
            return True
        except Exception as e:
            logger.error(f"Failed to configure Airtable: {e}")
            return False

    def configure_notion(self, api_key: str, database_id: Optional[str] = None) -> bool:
        """Configure Notion export."""
        try:
            self.notion = NotionExporter(api_key, database_id)
            self._configured_exports.append("notion")
            logger.info("Notion export configured")
            return True
        except Exception as e:
            logger.error(f"Failed to configure Notion: {e}")
            return False

    async def export_to_all(
        self,
        leads: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Export leads to all configured platforms."""
        results = {}

        if self.airtable:
            results["airtable"] = await self.airtable.export_leads(leads=leads, filters=filters)

        if self.notion:
            results["notion"] = await self.notion.export_leads(leads=leads, filters=filters)

        return results

    def get_configured_exports(self) -> List[str]:
        """Get list of configured export platforms."""
        return self._configured_exports

    def get_stats(self) -> Dict:
        """Get combined export statistics."""
        stats = {"configured_exports": self._configured_exports}

        if self.airtable:
            stats["airtable"] = self.airtable.stats

        if self.notion:
            stats["notion"] = self.notion.stats

        return stats


# Singleton instance
_export_manager = None

def get_export_manager() -> ExportManager:
    """Get or create the export manager instance."""
    global _export_manager
    if _export_manager is None:
        _export_manager = ExportManager()
    return _export_manager
