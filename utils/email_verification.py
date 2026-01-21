"""Email verification service for MapLeads Pro."""
import re
import socket
import asyncio
import dns.resolver
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from loguru import logger

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from database import db_manager, BusinessLead


class EmailVerifier:
    """
    Email verification service with multiple verification levels.

    Verification Levels:
    1. Syntax Check - Basic email format validation
    2. Domain Check - Verify domain exists and has MX records
    3. SMTP Check - Verify mailbox exists (where possible)
    4. API Check - Use external API for comprehensive validation
    """

    # Common disposable email domains
    DISPOSABLE_DOMAINS = {
        "tempmail.com", "throwaway.email", "guerrillamail.com", "10minutemail.com",
        "mailinator.com", "yopmail.com", "sharklasers.com", "maildrop.cc",
        "temp-mail.org", "fakeinbox.com", "emailondeck.com", "tempail.com"
    }

    # Common role-based emails (not personal)
    ROLE_BASED_PREFIXES = {
        "admin", "administrator", "info", "contact", "support", "help", "sales",
        "marketing", "billing", "accounting", "hr", "jobs", "careers", "press",
        "media", "webmaster", "postmaster", "hostmaster", "abuse", "noreply",
        "no-reply", "feedback", "office", "team", "hello", "service"
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_provider: str = "abstract"  # "abstract", "hunter", "neverbounce"
    ):
        """
        Initialize email verifier.

        Args:
            api_key: Optional API key for external verification service
            api_provider: API provider name
        """
        self.api_key = api_key
        self.api_provider = api_provider
        self.stats = {
            "total_verified": 0,
            "valid": 0,
            "invalid": 0,
            "risky": 0,
            "unknown": 0
        }

    async def verify_email(
        self,
        email: str,
        level: str = "domain"  # "syntax", "domain", "smtp", "api"
    ) -> Dict:
        """
        Verify an email address.

        Args:
            email: Email address to verify
            level: Verification level

        Returns:
            Dict with verification results
        """
        result = {
            "email": email,
            "is_valid": False,
            "status": "unknown",
            "verification_level": level,
            "checks": {},
            "score": 0,
            "risk_level": "unknown",
            "verified_at": datetime.now().isoformat()
        }

        try:
            # Level 1: Syntax check (always performed)
            syntax_valid, syntax_details = self._check_syntax(email)
            result["checks"]["syntax"] = {
                "passed": syntax_valid,
                "details": syntax_details
            }

            if not syntax_valid:
                result["status"] = "invalid_syntax"
                self.stats["invalid"] += 1
                return result

            # Extract domain
            domain = email.split("@")[1].lower()

            # Check for disposable email
            is_disposable = domain in self.DISPOSABLE_DOMAINS
            result["checks"]["disposable"] = {
                "passed": not is_disposable,
                "is_disposable": is_disposable
            }

            # Check for role-based email
            prefix = email.split("@")[0].lower()
            is_role_based = prefix in self.ROLE_BASED_PREFIXES
            result["checks"]["role_based"] = {
                "passed": True,  # Not invalid, just noted
                "is_role_based": is_role_based
            }

            if level == "syntax":
                result["is_valid"] = syntax_valid
                result["status"] = "valid_syntax"
                result["score"] = 50
                self.stats["valid"] += 1
                return result

            # Level 2: Domain check
            if level in ["domain", "smtp", "api"]:
                domain_valid, mx_records = await self._check_domain(domain)
                result["checks"]["domain"] = {
                    "passed": domain_valid,
                    "mx_records": mx_records[:3] if mx_records else []
                }

                if not domain_valid:
                    result["status"] = "invalid_domain"
                    result["score"] = 20
                    self.stats["invalid"] += 1
                    return result

                if level == "domain":
                    result["is_valid"] = True
                    result["status"] = "valid_domain"
                    result["score"] = 70
                    self.stats["valid"] += 1
                    return result

            # Level 3: SMTP check
            if level in ["smtp", "api"]:
                smtp_valid, smtp_details = await self._check_smtp(email, mx_records[0] if mx_records else None)
                result["checks"]["smtp"] = {
                    "passed": smtp_valid,
                    "details": smtp_details
                }

                if level == "smtp":
                    result["is_valid"] = smtp_valid
                    result["status"] = "valid_smtp" if smtp_valid else "invalid_smtp"
                    result["score"] = 90 if smtp_valid else 40
                    if smtp_valid:
                        self.stats["valid"] += 1
                    else:
                        self.stats["risky"] += 1
                    return result

            # Level 4: API check
            if level == "api" and self.api_key:
                api_result = await self._check_api(email)
                result["checks"]["api"] = api_result
                result["is_valid"] = api_result.get("is_valid", False)
                result["status"] = api_result.get("status", "unknown")
                result["score"] = api_result.get("score", 50)

                if result["is_valid"]:
                    self.stats["valid"] += 1
                else:
                    self.stats["invalid"] += 1

            # Calculate risk level
            result["risk_level"] = self._calculate_risk_level(result)
            self.stats["total_verified"] += 1

        except Exception as e:
            logger.error(f"Error verifying email {email}: {e}")
            result["error"] = str(e)
            result["status"] = "error"
            self.stats["unknown"] += 1

        return result

    def _check_syntax(self, email: str) -> Tuple[bool, str]:
        """Check email syntax."""
        # Basic regex pattern for email validation
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not email:
            return False, "Empty email"

        if len(email) > 254:
            return False, "Email too long"

        if not re.match(pattern, email):
            return False, "Invalid email format"

        local_part = email.split("@")[0]
        if len(local_part) > 64:
            return False, "Local part too long"

        # Check for consecutive dots
        if ".." in email:
            return False, "Consecutive dots not allowed"

        return True, "Valid syntax"

    async def _check_domain(self, domain: str) -> Tuple[bool, List[str]]:
        """Check domain MX records."""
        try:
            loop = asyncio.get_event_loop()

            def resolve_mx():
                try:
                    answers = dns.resolver.resolve(domain, 'MX')
                    return [str(r.exchange) for r in answers]
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout) as e:
                    logger.debug(f"MX resolution failed for {domain}: {e}")
                    return []

            mx_records = await loop.run_in_executor(None, resolve_mx)

            if mx_records:
                return True, mx_records

            # Try A record as fallback
            def resolve_a():
                try:
                    dns.resolver.resolve(domain, 'A')
                    return True
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout) as e:
                    logger.debug(f"A record resolution failed for {domain}: {e}")
                    return False

            has_a_record = await loop.run_in_executor(None, resolve_a)

            return has_a_record, []

        except Exception as e:
            logger.debug(f"Domain check error for {domain}: {e}")
            return False, []

    async def _check_smtp(
        self,
        email: str,
        mx_host: Optional[str]
    ) -> Tuple[bool, str]:
        """
        Check if mailbox exists via SMTP.
        Note: Many servers block this check.
        """
        if not mx_host:
            return False, "No MX host available"

        try:
            loop = asyncio.get_event_loop()

            def smtp_check():
                import smtplib

                # Remove trailing dot if present
                host = mx_host.rstrip(".")

                try:
                    with smtplib.SMTP(host, 25, timeout=10) as smtp:
                        smtp.helo("verify.mapleads.pro")
                        smtp.mail("verify@mapleads.pro")
                        code, message = smtp.rcpt(email)

                        if code == 250:
                            return True, "Mailbox exists"
                        elif code == 550:
                            return False, "Mailbox does not exist"
                        else:
                            return None, f"Unknown response: {code}"

                except smtplib.SMTPServerDisconnected:
                    return None, "Server disconnected (verification blocked)"
                except smtplib.SMTPConnectError:
                    return None, "Could not connect to mail server"
                except socket.timeout:
                    return None, "Connection timeout"
                except Exception as e:
                    return None, str(e)

            result, details = await asyncio.wait_for(
                loop.run_in_executor(None, smtp_check),
                timeout=15
            )

            if result is None:
                return False, details
            return result, details

        except asyncio.TimeoutError:
            return False, "SMTP check timeout"
        except Exception as e:
            logger.debug(f"SMTP check error: {e}")
            return False, str(e)

    async def _check_api(self, email: str) -> Dict:
        """Check email using external API."""
        if not self.api_key or not AIOHTTP_AVAILABLE:
            return {"error": "API not configured"}

        try:
            if self.api_provider == "abstract":
                url = f"https://emailvalidation.abstractapi.com/v1/?api_key={self.api_key}&email={email}"
            elif self.api_provider == "hunter":
                url = f"https://api.hunter.io/v2/email-verifier?email={email}&api_key={self.api_key}"
            elif self.api_provider == "neverbounce":
                url = f"https://api.neverbounce.com/v4/single/check?key={self.api_key}&email={email}"
            else:
                return {"error": f"Unknown provider: {self.api_provider}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_api_response(data)
                    else:
                        return {"error": f"API error: {response.status}"}

        except Exception as e:
            logger.error(f"API check error: {e}")
            return {"error": str(e)}

    def _parse_api_response(self, data: Dict) -> Dict:
        """Parse API response based on provider."""
        result = {
            "is_valid": False,
            "status": "unknown",
            "score": 50
        }

        try:
            if self.api_provider == "abstract":
                result["is_valid"] = data.get("deliverability") == "DELIVERABLE"
                result["status"] = data.get("deliverability", "unknown").lower()
                result["score"] = data.get("quality_score", 0.5) * 100

            elif self.api_provider == "hunter":
                status = data.get("data", {}).get("status", "unknown")
                result["is_valid"] = status == "valid"
                result["status"] = status
                result["score"] = data.get("data", {}).get("score", 50)

            elif self.api_provider == "neverbounce":
                status = data.get("result", "unknown")
                result["is_valid"] = status == "valid"
                result["status"] = status
                result["score"] = 90 if status == "valid" else 30

        except Exception as e:
            logger.debug(f"Error parsing API response: {e}")

        return result

    def _calculate_risk_level(self, result: Dict) -> str:
        """Calculate overall risk level."""
        checks = result.get("checks", {})

        # High risk indicators
        if checks.get("disposable", {}).get("is_disposable"):
            return "high"

        if not checks.get("domain", {}).get("passed"):
            return "high"

        if not checks.get("smtp", {}).get("passed") and result.get("verification_level") == "smtp":
            return "medium"

        if checks.get("role_based", {}).get("is_role_based"):
            return "low"  # Role-based emails are not invalid, just noted

        if result.get("score", 0) >= 80:
            return "low"
        elif result.get("score", 0) >= 50:
            return "medium"
        else:
            return "high"

    async def verify_batch(
        self,
        emails: List[str],
        level: str = "domain",
        max_concurrent: int = 5
    ) -> List[Dict]:
        """
        Verify multiple emails concurrently.

        Args:
            emails: List of email addresses
            level: Verification level
            max_concurrent: Maximum concurrent verifications

        Returns:
            List of verification results
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def verify_with_limit(email: str):
            async with semaphore:
                return await self.verify_email(email, level)

        tasks = [verify_with_limit(email) for email in emails]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "email": emails[i],
                    "is_valid": False,
                    "status": "error",
                    "error": str(result)
                })
            else:
                processed_results.append(result)

        return processed_results

    async def verify_leads(
        self,
        filters: Optional[Dict] = None,
        level: str = "domain",
        update_db: bool = True
    ) -> Dict:
        """
        Verify emails for leads in database.

        Args:
            filters: Database filters
            level: Verification level
            update_db: Whether to update lead records

        Returns:
            Summary of verification results
        """
        results = {
            "total": 0,
            "verified": 0,
            "valid": 0,
            "invalid": 0,
            "no_email": 0,
            "details": []
        }

        try:
            with db_manager.get_session() as session:
                query = session.query(BusinessLead).filter(
                    BusinessLead.email.isnot(None)
                )

                if filters:
                    if filters.get("city"):
                        query = query.filter(BusinessLead.city == filters["city"])
                    if filters.get("category"):
                        query = query.filter(BusinessLead.category == filters["category"])

                leads = query.all()
                results["total"] = len(leads)

                emails = [lead.email for lead in leads if lead.email]

                if not emails:
                    results["no_email"] = results["total"]
                    return results

                # Verify all emails
                verifications = await self.verify_batch(emails, level)

                for lead, verification in zip(leads, verifications):
                    if verification.get("is_valid"):
                        results["valid"] += 1
                    else:
                        results["invalid"] += 1

                    results["verified"] += 1

                    # Store result
                    results["details"].append({
                        "lead_id": lead.id,
                        "email": lead.email,
                        "verification": verification
                    })

                session.commit()

        except Exception as e:
            logger.error(f"Error verifying leads: {e}")
            results["error"] = str(e)

        return results

    def get_stats(self) -> Dict:
        """Get verification statistics."""
        return {
            **self.stats,
            "validity_rate": (
                self.stats["valid"] / self.stats["total_verified"] * 100
                if self.stats["total_verified"] > 0 else 0
            )
        }


# Singleton instance
_email_verifier = None

def get_email_verifier(api_key: Optional[str] = None, api_provider: str = "abstract") -> EmailVerifier:
    """Get or create the email verifier instance."""
    global _email_verifier
    if _email_verifier is None:
        _email_verifier = EmailVerifier(api_key, api_provider)
    return _email_verifier
