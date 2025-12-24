"""Website enrichment for extracting emails and social media links."""
import re
import aiohttp
from bs4 import BeautifulSoup
from typing import Dict, Optional, List
from loguru import logger
from email_validator import validate_email, EmailNotValidError


class WebsiteEnricher:
    """Enriches business data by scraping their websites."""

    def __init__(self, timeout: int = 15):
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def enrich_from_website(self, website_url: str) -> Dict:
        """
        Extract additional data from business website.

        Returns dict with: email, social_links, owner_name
        """
        enrichment_data = {
            'email': None,
            'social_facebook': None,
            'social_instagram': None,
            'social_twitter': None,
            'social_linkedin': None,
            'social_youtube': None,
            'owner_name': None
        }

        try:
            # Fetch website content
            html = await self._fetch_website(website_url)
            if not html:
                return enrichment_data

            # Parse HTML
            soup = BeautifulSoup(html, 'lxml')

            # Extract email
            enrichment_data['email'] = await self._extract_email(soup, html)

            # Extract social media links
            social_links = await self._extract_social_media(soup)
            enrichment_data.update(social_links)

            # Extract owner name
            enrichment_data['owner_name'] = await self._extract_owner_name(soup)

            logger.info(f"Website enrichment completed for {website_url}")
            return enrichment_data

        except Exception as e:
            logger.error(f"Error enriching website {website_url}: {e}")
            return enrichment_data

    async def _fetch_website(self, url: str) -> Optional[str]:
        """Fetch website HTML content."""
        try:
            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        logger.debug(f"Website returned status {response.status}")
                        return None

        except Exception as e:
            logger.debug(f"Error fetching website: {e}")
            return None

    async def _extract_email(self, soup: BeautifulSoup, html: str) -> Optional[str]:
        """Extract email address from website."""
        emails = set()

        # Method 1: Find mailto: links
        mailto_links = soup.find_all('a', href=re.compile(r'mailto:', re.I))
        for link in mailto_links:
            email = link['href'].replace('mailto:', '').split('?')[0].strip()
            emails.add(email.lower())

        # Method 2: Regex pattern matching
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        found_emails = re.findall(email_pattern, html)
        emails.update([e.lower() for e in found_emails])

        # Method 3: Check specific sections (contact, footer)
        contact_sections = soup.find_all(['div', 'section', 'footer'],
                                        class_=re.compile(r'contact|footer|email', re.I))
        for section in contact_sections:
            section_emails = re.findall(email_pattern, section.get_text())
            emails.update([e.lower() for e in section_emails])

        # Filter out common invalid emails
        invalid_patterns = [
            'example.com', 'test.com', 'domain.com', '@gmail.com',
            'info@wix.com', 'support@', 'noreply@'
        ]

        valid_emails = []
        for email in emails:
            # Skip invalid patterns
            if any(pattern in email for pattern in invalid_patterns):
                continue

            # Validate email format
            try:
                validate_email(email)
                valid_emails.append(email)
            except EmailNotValidError:
                continue

        # Return first valid email
        if valid_emails:
            logger.info(f"Found email: {valid_emails[0]}")
            return valid_emails[0]

        return None

    async def _extract_social_media(self, soup: BeautifulSoup) -> Dict:
        """Extract social media links."""
        social = {
            'social_facebook': None,
            'social_instagram': None,
            'social_twitter': None,
            'social_linkedin': None,
            'social_youtube': None
        }

        # Find all links
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href'].lower()

            # Facebook
            if 'facebook.com' in href or 'fb.com' in href or 'fb.me' in href:
                if not social['social_facebook']:
                    social['social_facebook'] = link['href']

            # Instagram
            elif 'instagram.com' in href:
                if not social['social_instagram']:
                    social['social_instagram'] = link['href']

            # Twitter/X
            elif 'twitter.com' in href or 'x.com' in href:
                if not social['social_twitter']:
                    social['social_twitter'] = link['href']

            # LinkedIn
            elif 'linkedin.com' in href:
                if not social['social_linkedin']:
                    social['social_linkedin'] = link['href']

            # YouTube
            elif 'youtube.com' in href or 'youtu.be' in href:
                if not social['social_youtube']:
                    social['social_youtube'] = link['href']

        # Log found social links
        found = [k.replace('social_', '') for k, v in social.items() if v]
        if found:
            logger.info(f"Found social links: {', '.join(found)}")

        return social

    async def _extract_owner_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract owner/founder name from about page."""
        try:
            # Look for common patterns
            patterns = [
                r'founded by ([A-Z][a-z]+ [A-Z][a-z]+)',
                r'by ([A-Z][a-z]+ [A-Z][a-z]+)',
                r'owner:?\s*([A-Z][a-z]+ [A-Z][a-z]+)',
                r'director:?\s*([A-Z][a-z]+ [A-Z][a-z]+)'
            ]

            # Check about sections
            about_sections = soup.find_all(['div', 'section'],
                                          class_=re.compile(r'about|team|founder', re.I))

            for section in about_sections:
                text = section.get_text()
                for pattern in patterns:
                    match = re.search(pattern, text, re.I)
                    if match:
                        name = match.group(1).strip()
                        logger.info(f"Found owner name: {name}")
                        return name

        except Exception as e:
            logger.debug(f"Error extracting owner name: {e}")

        return None
