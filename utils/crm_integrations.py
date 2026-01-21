"""CRM integrations module for MapLeads Pro."""
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime
from loguru import logger

try:
    from hubspot import HubSpot
    from hubspot.crm.contacts import SimplePublicObjectInputForCreate
    from hubspot.crm.companies import SimplePublicObjectInputForCreate as CompanyInput
    HUBSPOT_AVAILABLE = True
except ImportError:
    HUBSPOT_AVAILABLE = False

try:
    from simple_salesforce import Salesforce
    SALESFORCE_AVAILABLE = True
except ImportError:
    SALESFORCE_AVAILABLE = False

from database import db_manager, BusinessLead


def _fetch_leads_from_db(filters: Optional[Dict]) -> List[Dict]:
    """
    Shared helper to fetch leads from database.

    Args:
        filters: Optional filters (has_phone, has_email, min_quality_score, city)

    Returns:
        List of lead dictionaries
    """
    try:
        with db_manager.get_session() as session:
            query = session.query(BusinessLead)

            if filters:
                if filters.get("has_phone"):
                    query = query.filter(BusinessLead.phone.isnot(None))
                if filters.get("has_email"):
                    query = query.filter(BusinessLead.email.isnot(None))
                if filters.get("min_quality_score"):
                    query = query.filter(BusinessLead.data_quality_score >= filters["min_quality_score"])
                if filters.get("city"):
                    query = query.filter(BusinessLead.city == filters["city"])

            results = query.all()
            return [lead.to_dict() for lead in results]
    except Exception as e:
        logger.error(f"Error fetching leads: {e}")
        return []


class HubSpotIntegration:
    """HubSpot CRM integration for pushing leads."""

    def __init__(self, api_key: Optional[str] = None, access_token: Optional[str] = None):
        """
        Initialize HubSpot integration.

        Args:
            api_key: HubSpot API key (deprecated, use access_token)
            access_token: HubSpot Private App access token
        """
        if not HUBSPOT_AVAILABLE:
            raise ImportError("hubspot-api-client is required. Install with: pip install hubspot-api-client")

        self.client = None
        if access_token:
            self.client = HubSpot(access_token=access_token)
        elif api_key:
            self.client = HubSpot(api_key=api_key)

        self.stats = {
            "contacts_created": 0,
            "contacts_updated": 0,
            "companies_created": 0,
            "failed": 0
        }

    async def push_leads_as_contacts(
        self,
        leads: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None,
        update_existing: bool = True
    ) -> Dict:
        """
        Push leads to HubSpot as contacts.

        Args:
            leads: List of lead dictionaries
            filters: Database filters to fetch leads
            update_existing: Whether to update existing contacts

        Returns:
            Dict with results
        """
        if not self.client:
            return {"success": False, "error": "HubSpot client not initialized"}

        # Fetch leads if not provided
        if leads is None:
            leads = self._fetch_leads(filters)

        if not leads:
            return {"success": True, "message": "No leads to push", "created": 0}

        results = {
            "success": True,
            "created": 0,
            "updated": 0,
            "failed": 0,
            "errors": []
        }

        loop = asyncio.get_event_loop()

        for lead in leads:
            try:
                # Map lead to HubSpot contact properties
                properties = self._map_lead_to_hubspot_contact(lead)

                # Check if contact exists by email
                existing_contact = None
                if lead.get("email"):
                    try:
                        existing_contact = await loop.run_in_executor(
                            None,
                            lambda: self.client.crm.contacts.basic_api.get_by_id(
                                contact_id=lead["email"],
                                id_property="email"
                            )
                        )
                    except:
                        pass

                if existing_contact and update_existing:
                    # Update existing contact
                    await loop.run_in_executor(
                        None,
                        lambda: self.client.crm.contacts.basic_api.update(
                            contact_id=existing_contact.id,
                            simple_public_object_input={"properties": properties}
                        )
                    )
                    results["updated"] += 1
                    self.stats["contacts_updated"] += 1
                else:
                    # Create new contact
                    contact_input = SimplePublicObjectInputForCreate(properties=properties)
                    await loop.run_in_executor(
                        None,
                        lambda: self.client.crm.contacts.basic_api.create(
                            simple_public_object_input_for_create=contact_input
                        )
                    )
                    results["created"] += 1
                    self.stats["contacts_created"] += 1

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"lead_id": lead.get("id"), "error": str(e)})
                self.stats["failed"] += 1
                logger.error(f"Error pushing lead {lead.get('id')} to HubSpot: {e}")

        logger.info(f"HubSpot sync complete: {results['created']} created, {results['updated']} updated")
        return results

    async def push_leads_as_companies(
        self,
        leads: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None
    ) -> Dict:
        """
        Push leads to HubSpot as companies.

        Args:
            leads: List of lead dictionaries
            filters: Database filters

        Returns:
            Dict with results
        """
        if not self.client:
            return {"success": False, "error": "HubSpot client not initialized"}

        if leads is None:
            leads = self._fetch_leads(filters)

        if not leads:
            return {"success": True, "message": "No leads to push", "created": 0}

        results = {"success": True, "created": 0, "failed": 0, "errors": []}
        loop = asyncio.get_event_loop()

        for lead in leads:
            try:
                properties = self._map_lead_to_hubspot_company(lead)
                company_input = CompanyInput(properties=properties)

                await loop.run_in_executor(
                    None,
                    lambda: self.client.crm.companies.basic_api.create(
                        simple_public_object_input_for_create=company_input
                    )
                )

                results["created"] += 1
                self.stats["companies_created"] += 1

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"lead_id": lead.get("id"), "error": str(e)})
                self.stats["failed"] += 1

        return results

    def _map_lead_to_hubspot_contact(self, lead: Dict) -> Dict:
        """Map lead fields to HubSpot contact properties."""
        # Split business name for first/last name if no owner name
        name_parts = (lead.get("owner_name") or lead.get("business_name", "")).split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        return {
            "email": lead.get("email") or f"lead_{lead.get('id')}@placeholder.com",
            "firstname": first_name,
            "lastname": last_name,
            "phone": lead.get("phone"),
            "company": lead.get("business_name"),
            "website": lead.get("website"),
            "address": lead.get("full_address"),
            "city": lead.get("city"),
            "state": lead.get("state"),
            "zip": lead.get("pin_code"),
            "hs_lead_status": "NEW",
            "leadsource": "Google Maps Scraper"
        }

    def _map_lead_to_hubspot_company(self, lead: Dict) -> Dict:
        """Map lead fields to HubSpot company properties."""
        return {
            "name": lead.get("business_name"),
            "domain": self._extract_domain(lead.get("website")),
            "phone": lead.get("phone"),
            "address": lead.get("full_address"),
            "city": lead.get("city"),
            "state": lead.get("state"),
            "zip": lead.get("pin_code"),
            "industry": lead.get("category"),
            "website": lead.get("website"),
            "description": f"Rating: {lead.get('rating')}/5 ({lead.get('review_count')} reviews)"
        }

    def _extract_domain(self, website: Optional[str]) -> Optional[str]:
        """Extract domain from website URL."""
        if not website:
            return None
        try:
            from urllib.parse import urlparse
            parsed = urlparse(website if website.startswith("http") else f"https://{website}")
            return parsed.netloc.replace("www.", "")
        except:
            return None

    def _fetch_leads(self, filters: Optional[Dict]) -> List[Dict]:
        """Fetch leads from database using shared helper."""
        return _fetch_leads_from_db(filters)


class SalesforceIntegration:
    """Salesforce CRM integration for pushing leads."""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        security_token: Optional[str] = None,
        domain: str = "login"
    ):
        """
        Initialize Salesforce integration.

        Args:
            username: Salesforce username
            password: Salesforce password
            security_token: Salesforce security token
            domain: Salesforce domain (login, test, or custom)
        """
        if not SALESFORCE_AVAILABLE:
            raise ImportError("simple-salesforce is required. Install with: pip install simple-salesforce")

        self.client = None
        if all([username, password, security_token]):
            self.client = Salesforce(
                username=username,
                password=password,
                security_token=security_token,
                domain=domain
            )

        self.stats = {
            "leads_created": 0,
            "accounts_created": 0,
            "contacts_created": 0,
            "failed": 0
        }

    async def push_as_leads(
        self,
        leads: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None
    ) -> Dict:
        """
        Push leads to Salesforce as Lead objects.

        Args:
            leads: List of lead dictionaries
            filters: Database filters

        Returns:
            Dict with results
        """
        if not self.client:
            return {"success": False, "error": "Salesforce client not initialized"}

        if leads is None:
            leads = self._fetch_leads(filters)

        if not leads:
            return {"success": True, "message": "No leads to push", "created": 0}

        results = {"success": True, "created": 0, "failed": 0, "errors": []}
        loop = asyncio.get_event_loop()

        for lead in leads:
            try:
                sf_lead = self._map_to_salesforce_lead(lead)

                await loop.run_in_executor(
                    None,
                    lambda: self.client.Lead.create(sf_lead)
                )

                results["created"] += 1
                self.stats["leads_created"] += 1

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"lead_id": lead.get("id"), "error": str(e)})
                self.stats["failed"] += 1
                logger.error(f"Error pushing to Salesforce: {e}")

        logger.info(f"Salesforce sync complete: {results['created']} leads created")
        return results

    async def push_as_accounts_and_contacts(
        self,
        leads: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None
    ) -> Dict:
        """
        Push leads as Account + Contact pairs.

        Args:
            leads: List of lead dictionaries
            filters: Database filters

        Returns:
            Dict with results
        """
        if not self.client:
            return {"success": False, "error": "Salesforce client not initialized"}

        if leads is None:
            leads = self._fetch_leads(filters)

        results = {
            "success": True,
            "accounts_created": 0,
            "contacts_created": 0,
            "failed": 0,
            "errors": []
        }

        loop = asyncio.get_event_loop()

        for lead in leads:
            try:
                # Create Account
                account_data = self._map_to_salesforce_account(lead)
                account_result = await loop.run_in_executor(
                    None,
                    lambda: self.client.Account.create(account_data)
                )
                account_id = account_result.get("id")
                results["accounts_created"] += 1
                self.stats["accounts_created"] += 1

                # Create Contact linked to Account
                contact_data = self._map_to_salesforce_contact(lead, account_id)
                await loop.run_in_executor(
                    None,
                    lambda: self.client.Contact.create(contact_data)
                )
                results["contacts_created"] += 1
                self.stats["contacts_created"] += 1

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"lead_id": lead.get("id"), "error": str(e)})
                self.stats["failed"] += 1

        return results

    def _map_to_salesforce_lead(self, lead: Dict) -> Dict:
        """Map lead to Salesforce Lead object."""
        name_parts = (lead.get("owner_name") or lead.get("business_name", "Unknown")).split(" ", 1)

        return {
            "FirstName": name_parts[0],
            "LastName": name_parts[1] if len(name_parts) > 1 else name_parts[0],
            "Company": lead.get("business_name") or "Unknown",
            "Email": lead.get("email"),
            "Phone": lead.get("phone"),
            "Website": lead.get("website"),
            "Street": lead.get("full_address"),
            "City": lead.get("city"),
            "State": lead.get("state"),
            "PostalCode": lead.get("pin_code"),
            "Industry": lead.get("category"),
            "LeadSource": "Google Maps Scraper",
            "Description": f"Rating: {lead.get('rating')}/5, Reviews: {lead.get('review_count')}"
        }

    def _map_to_salesforce_account(self, lead: Dict) -> Dict:
        """Map lead to Salesforce Account object."""
        return {
            "Name": lead.get("business_name") or "Unknown",
            "Phone": lead.get("phone"),
            "Website": lead.get("website"),
            "BillingStreet": lead.get("full_address"),
            "BillingCity": lead.get("city"),
            "BillingState": lead.get("state"),
            "BillingPostalCode": lead.get("pin_code"),
            "Industry": lead.get("category"),
            "Description": f"Google Maps Rating: {lead.get('rating')}/5 ({lead.get('review_count')} reviews)"
        }

    def _map_to_salesforce_contact(self, lead: Dict, account_id: str) -> Dict:
        """Map lead to Salesforce Contact object."""
        name_parts = (lead.get("owner_name") or "Business Owner").split(" ", 1)

        return {
            "AccountId": account_id,
            "FirstName": name_parts[0],
            "LastName": name_parts[1] if len(name_parts) > 1 else name_parts[0],
            "Email": lead.get("email"),
            "Phone": lead.get("phone"),
            "MailingStreet": lead.get("full_address"),
            "MailingCity": lead.get("city"),
            "MailingState": lead.get("state"),
            "MailingPostalCode": lead.get("pin_code"),
            "LeadSource": "Google Maps Scraper"
        }

    def _fetch_leads(self, filters: Optional[Dict]) -> List[Dict]:
        """Fetch leads from database using shared helper."""
        return _fetch_leads_from_db(filters)


class CRMManager:
    """Unified CRM manager for all integrations."""

    def __init__(self):
        self.hubspot: Optional[HubSpotIntegration] = None
        self.salesforce: Optional[SalesforceIntegration] = None
        self._configured_crms = []

    def configure_hubspot(self, access_token: str) -> bool:
        """Configure HubSpot integration."""
        try:
            self.hubspot = HubSpotIntegration(access_token=access_token)
            self._configured_crms.append("hubspot")
            logger.info("HubSpot integration configured")
            return True
        except Exception as e:
            logger.error(f"Failed to configure HubSpot: {e}")
            return False

    def configure_salesforce(
        self,
        username: str,
        password: str,
        security_token: str,
        domain: str = "login"
    ) -> bool:
        """Configure Salesforce integration."""
        try:
            self.salesforce = SalesforceIntegration(
                username=username,
                password=password,
                security_token=security_token,
                domain=domain
            )
            self._configured_crms.append("salesforce")
            logger.info("Salesforce integration configured")
            return True
        except Exception as e:
            logger.error(f"Failed to configure Salesforce: {e}")
            return False

    async def push_to_all(
        self,
        leads: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Push leads to all configured CRMs."""
        results = {}

        if self.hubspot:
            results["hubspot"] = await self.hubspot.push_leads_as_contacts(leads, filters)

        if self.salesforce:
            results["salesforce"] = await self.salesforce.push_as_leads(leads, filters)

        return results

    def get_configured_crms(self) -> List[str]:
        """Get list of configured CRMs."""
        return self._configured_crms

    def get_stats(self) -> Dict:
        """Get combined CRM statistics."""
        stats = {"configured_crms": self._configured_crms}

        if self.hubspot:
            stats["hubspot"] = self.hubspot.stats

        if self.salesforce:
            stats["salesforce"] = self.salesforce.stats

        return stats


# Singleton instance
_crm_manager = None

def get_crm_manager() -> CRMManager:
    """Get or create the CRM manager instance."""
    global _crm_manager
    if _crm_manager is None:
        _crm_manager = CRMManager()
    return _crm_manager
