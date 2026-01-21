"""Contact information extraction from business websites."""
import re
from typing import Dict, List, Optional, Tuple, Set
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from loguru import logger
import time
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor


@dataclass
class ContactPerson:
    """Represents a contact person extracted from a website."""
    name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class ContactInfo:
    """Represents all contact information extracted from a website."""
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    contacts: List[ContactPerson] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        return {
            'email_1': self.emails[0] if len(self.emails) > 0 else None,
            'email_2': self.emails[1] if len(self.emails) > 1 else None,
            'email_3': self.emails[2] if len(self.emails) > 2 else None,
            'phone_1': self.phones[0] if len(self.phones) > 0 else None,
            'phone_2': self.phones[1] if len(self.phones) > 1 else None,
            'phone_3': self.phones[2] if len(self.phones) > 2 else None,
            'contact_name_1': self.contacts[0].name if len(self.contacts) > 0 else None,
            'contact_title_1': self.contacts[0].title if len(self.contacts) > 0 else None,
            'contact_email_1': self.contacts[0].email if len(self.contacts) > 0 else None,
            'contact_name_2': self.contacts[1].name if len(self.contacts) > 1 else None,
            'contact_title_2': self.contacts[1].title if len(self.contacts) > 1 else None,
            'contact_email_2': self.contacts[1].email if len(self.contacts) > 1 else None,
            'contact_name_3': self.contacts[2].name if len(self.contacts) > 2 else None,
            'contact_title_3': self.contacts[2].title if len(self.contacts) > 2 else None,
            'contact_email_3': self.contacts[2].email if len(self.contacts) > 2 else None,
        }


class ContactExtractor:
    """Extract contact information (emails, phones, contact persons) from websites."""

    # Email patterns
    EMAIL_PATTERNS = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    ]

    # Phone patterns for various formats
    PHONE_PATTERNS = [
        # International format with + prefix
        r'\+\d{1,4}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
        # US format: (xxx) xxx-xxxx or xxx-xxx-xxxx
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        # Indian format: +91 xxxxx xxxxx or 0xxxxx xxxxx
        r'(?:\+91|0)?[-.\s]?\d{5}[-.\s]?\d{5}',
        # General 10+ digit numbers
        r'\d{10,15}',
        # With country code and various separators
        r'\+?\d{1,4}[-.\s]?\d{2,5}[-.\s]?\d{2,5}[-.\s]?\d{2,5}',
    ]

    # Common job titles to identify contact persons
    JOB_TITLES = [
        'CEO', 'CFO', 'CTO', 'COO', 'CMO', 'CIO',
        'Chief Executive Officer', 'Chief Financial Officer',
        'Chief Technology Officer', 'Chief Operating Officer',
        'President', 'Vice President', 'VP',
        'Director', 'Manager', 'Owner', 'Founder',
        'General Manager', 'Managing Director', 'MD',
        'Partner', 'Principal', 'Head of',
        'Sales Manager', 'Marketing Manager', 'HR Manager',
        'Business Development', 'Customer Service',
        'Contact Person', 'Proprietor',
    ]

    # Headers to mimic a real browser
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    # Emails to exclude (generic/invalid)
    EXCLUDED_EMAIL_PATTERNS = [
        r'example\.com',
        r'test\.com',
        r'domain\.com',
        r'email\.com',
        r'your.*@',
        r'name@',
        r'info@info',
        r'support@support',
        r'sentry\.io',
        r'gravatar\.com',
        r'placeholder',
    ]

    def __init__(self, timeout: int = 10, max_retries: int = 2):
        """
        Initialize the contact extractor.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def extract_from_website(self, website_url: str) -> ContactInfo:
        """
        Extract all contact information from a website.

        Args:
            website_url: The business website URL

        Returns:
            ContactInfo object with all extracted contact information
        """
        contact_info = ContactInfo()

        if not website_url:
            return contact_info

        try:
            # Normalize URL
            if not website_url.startswith(('http://', 'https://')):
                website_url = 'https://' + website_url

            # Fetch the main page
            html_content = self._fetch_page(website_url)
            if not html_content:
                return contact_info

            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract from main page
            self._extract_from_soup(soup, contact_info, website_url)

            # Check contact page if exists
            contact_pages = self._find_contact_pages(soup, website_url)
            for page_url in contact_pages[:3]:  # Limit to 3 pages
                try:
                    page_html = self._fetch_page(page_url)
                    if page_html:
                        page_soup = BeautifulSoup(page_html, 'html.parser')
                        self._extract_from_soup(page_soup, contact_info, page_url)
                except Exception:
                    continue

            # Check about page
            about_pages = self._find_about_pages(soup, website_url)
            for page_url in about_pages[:2]:  # Limit to 2 pages
                try:
                    page_html = self._fetch_page(page_url)
                    if page_html:
                        page_soup = BeautifulSoup(page_html, 'html.parser')
                        self._extract_from_soup(page_soup, contact_info, page_url)
                except Exception:
                    continue

            # Deduplicate and clean results
            contact_info.emails = self._deduplicate_emails(contact_info.emails)[:3]
            contact_info.phones = self._deduplicate_phones(contact_info.phones)[:3]
            contact_info.contacts = contact_info.contacts[:3]

            logger.info(
                f"Extracted from {website_url}: "
                f"{len(contact_info.emails)} emails, "
                f"{len(contact_info.phones)} phones, "
                f"{len(contact_info.contacts)} contacts"
            )

        except Exception as e:
            logger.warning(f"Error extracting contacts from {website_url}: {e}")

        return contact_info

    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content with retries."""
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    verify=True
                )
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                    continue
                logger.debug(f"Failed to fetch {url}: {e}")
                return None
        return None

    def _extract_from_soup(self, soup: BeautifulSoup, contact_info: ContactInfo, base_url: str):
        """Extract contact information from BeautifulSoup object."""
        # Get page text
        page_text = soup.get_text(separator=' ')

        # Extract emails
        emails = self._extract_emails(soup, page_text)
        contact_info.emails.extend(emails)

        # Extract phones
        phones = self._extract_phones(soup, page_text)
        contact_info.phones.extend(phones)

        # Extract contact persons
        contacts = self._extract_contact_persons(soup, page_text)
        contact_info.contacts.extend(contacts)

    def _extract_emails(self, soup: BeautifulSoup, page_text: str) -> List[str]:
        """Extract email addresses from page."""
        emails = set()

        # From mailto links
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            if href.startswith('mailto:'):
                email = href.replace('mailto:', '').split('?')[0].strip()
                if self._is_valid_email(email):
                    emails.add(email.lower())

        # From page text using regex
        for pattern in self.EMAIL_PATTERNS:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for email in matches:
                if self._is_valid_email(email):
                    emails.add(email.lower())

        # From meta tags
        for meta in soup.find_all('meta'):
            content = meta.get('content', '')
            for pattern in self.EMAIL_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for email in matches:
                    if self._is_valid_email(email):
                        emails.add(email.lower())

        # From structured data
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string or '{}')
                self._extract_emails_from_json(data, emails)
            except:
                continue

        return list(emails)

    def _extract_emails_from_json(self, data, emails: Set[str]):
        """Extract emails from JSON-LD data."""
        if isinstance(data, dict):
            for key, value in data.items():
                if key.lower() in ['email', 'contactemail', 'emailaddress']:
                    if isinstance(value, str) and self._is_valid_email(value):
                        emails.add(value.lower())
                elif isinstance(value, (dict, list)):
                    if isinstance(value, dict):
                        self._extract_emails_from_json(value, emails)
                    else:
                        for item in value:
                            if isinstance(item, dict):
                                self._extract_emails_from_json(item, emails)

    def _is_valid_email(self, email: str) -> bool:
        """Check if email is valid and not generic/placeholder."""
        if not email or '@' not in email:
            return False

        # Check basic format
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return False

        # Check exclusion patterns
        for pattern in self.EXCLUDED_EMAIL_PATTERNS:
            if re.search(pattern, email, re.IGNORECASE):
                return False

        return True

    def _extract_phones(self, soup: BeautifulSoup, page_text: str) -> List[str]:
        """Extract phone numbers from page."""
        phones = set()

        # From tel links
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            if href.startswith('tel:'):
                phone = href.replace('tel:', '').strip()
                clean_phone = self._clean_phone(phone)
                if clean_phone:
                    phones.add(clean_phone)

        # From page text using regex
        for pattern in self.PHONE_PATTERNS:
            matches = re.findall(pattern, page_text)
            for phone in matches:
                clean_phone = self._clean_phone(phone)
                if clean_phone:
                    phones.add(clean_phone)

        # From itemprop phone
        for elem in soup.find_all(itemprop='telephone'):
            phone = elem.get_text().strip()
            clean_phone = self._clean_phone(phone)
            if clean_phone:
                phones.add(clean_phone)

        # From common phone containers
        phone_containers = soup.find_all(['span', 'div', 'p', 'a'], class_=lambda c: c and any(
            word in str(c).lower() for word in ['phone', 'tel', 'mobile', 'contact-number']
        ))
        for container in phone_containers:
            text = container.get_text().strip()
            for pattern in self.PHONE_PATTERNS:
                matches = re.findall(pattern, text)
                for phone in matches:
                    clean_phone = self._clean_phone(phone)
                    if clean_phone:
                        phones.add(clean_phone)

        return list(phones)

    def _clean_phone(self, phone: str) -> Optional[str]:
        """Clean and validate phone number."""
        if not phone:
            return None

        # Remove common non-digit characters except + at the start
        cleaned = re.sub(r'[^\d+]', '', phone)

        # Ensure it starts correctly if has +
        if cleaned.startswith('+'):
            cleaned = '+' + cleaned[1:].replace('+', '')
        else:
            cleaned = cleaned.replace('+', '')

        # Validate length
        digits_only = cleaned.replace('+', '')
        if len(digits_only) < 10 or len(digits_only) > 15:
            return None

        # Format nicely
        if len(digits_only) == 10:
            # US/India local format
            return f"{digits_only[:5]} {digits_only[5:]}"
        elif cleaned.startswith('+'):
            return cleaned
        else:
            return digits_only

        return None

    def _extract_contact_persons(self, soup: BeautifulSoup, page_text: str) -> List[ContactPerson]:
        """Extract contact person information."""
        contacts = []

        # Look for team/about sections
        team_sections = soup.find_all(['div', 'section', 'ul'], class_=lambda c: c and any(
            word in str(c).lower() for word in ['team', 'staff', 'leadership', 'management', 'people', 'about']
        ))

        for section in team_sections:
            # Look for person cards
            person_cards = section.find_all(['div', 'li', 'article'], class_=lambda c: c and any(
                word in str(c).lower() for word in ['member', 'person', 'team-member', 'staff-member', 'card']
            ))

            for card in person_cards[:5]:  # Limit per section
                contact = self._extract_person_from_card(card)
                if contact and contact.name:
                    contacts.append(contact)

        # Look for structured data
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string or '{}')
                self._extract_persons_from_json(data, contacts)
            except:
                continue

        # Look for common patterns in text
        title_pattern = '|'.join(self.JOB_TITLES)
        pattern = rf'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-,]\s*({title_pattern})'

        matches = re.findall(pattern, page_text, re.IGNORECASE)
        for name, title in matches[:3]:
            if len(name) > 3 and len(name) < 50:
                contact = ContactPerson(name=name.strip(), title=title.strip())
                contacts.append(contact)

        return contacts

    def _extract_person_from_card(self, card) -> Optional[ContactPerson]:
        """Extract person information from a card element."""
        contact = ContactPerson()

        # Look for name
        name_elem = card.find(['h2', 'h3', 'h4', 'span', 'p'], class_=lambda c: c and any(
            word in str(c).lower() for word in ['name', 'title', 'heading']
        ))
        if name_elem:
            contact.name = name_elem.get_text().strip()

        if not contact.name:
            # Try first heading
            heading = card.find(['h2', 'h3', 'h4'])
            if heading:
                contact.name = heading.get_text().strip()

        # Look for title/position
        title_elem = card.find(['span', 'p', 'div'], class_=lambda c: c and any(
            word in str(c).lower() for word in ['position', 'role', 'designation', 'title', 'job']
        ))
        if title_elem:
            contact.title = title_elem.get_text().strip()

        # Look for email in card
        email_link = card.find('a', href=lambda h: h and h.startswith('mailto:'))
        if email_link:
            contact.email = email_link.get('href').replace('mailto:', '').split('?')[0]

        return contact if contact.name else None

    def _extract_persons_from_json(self, data, contacts: List[ContactPerson]):
        """Extract person information from JSON-LD data."""
        if isinstance(data, dict):
            if data.get('@type') in ['Person', 'Employee', 'ContactPoint']:
                contact = ContactPerson(
                    name=data.get('name'),
                    title=data.get('jobTitle') or data.get('roleName'),
                    email=data.get('email'),
                )
                if contact.name:
                    contacts.append(contact)

            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    if isinstance(value, dict):
                        self._extract_persons_from_json(value, contacts)
                    else:
                        for item in value:
                            if isinstance(item, dict):
                                self._extract_persons_from_json(item, contacts)

    def _find_contact_pages(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Find contact page URLs."""
        pages = []
        keywords = ['contact', 'contact-us', 'kontakt', 'contacto', 'reach-us', 'get-in-touch']

        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '').lower()
            text = a_tag.get_text().lower()

            if any(keyword in href or keyword in text for keyword in keywords):
                full_url = urljoin(base_url, a_tag['href'])
                if full_url not in pages and self._is_same_domain(base_url, full_url):
                    pages.append(full_url)

        return pages

    def _find_about_pages(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Find about page URLs."""
        pages = []
        keywords = ['about', 'about-us', 'team', 'our-team', 'leadership', 'management', 'people']

        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '').lower()
            text = a_tag.get_text().lower()

            if any(keyword in href or keyword in text for keyword in keywords):
                full_url = urljoin(base_url, a_tag['href'])
                if full_url not in pages and self._is_same_domain(base_url, full_url):
                    pages.append(full_url)

        return pages

    def _is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs are from the same domain."""
        try:
            domain1 = urlparse(url1).netloc.lower()
            domain2 = urlparse(url2).netloc.lower()
            return domain1 == domain2 or domain1.endswith('.' + domain2) or domain2.endswith('.' + domain1)
        except:
            return False

    def _deduplicate_emails(self, emails: List[str]) -> List[str]:
        """Deduplicate and sort emails by priority."""
        seen = set()
        unique = []

        # Priority order: info@, contact@, hello@, others
        priority_prefixes = ['info@', 'contact@', 'hello@', 'sales@', 'support@', 'admin@']

        # Sort by priority
        def get_priority(email):
            email_lower = email.lower()
            for i, prefix in enumerate(priority_prefixes):
                if email_lower.startswith(prefix):
                    return i
            return len(priority_prefixes)

        sorted_emails = sorted(emails, key=get_priority)

        for email in sorted_emails:
            email_lower = email.lower()
            if email_lower not in seen:
                seen.add(email_lower)
                unique.append(email)

        return unique

    def _deduplicate_phones(self, phones: List[str]) -> List[str]:
        """Deduplicate phone numbers."""
        seen = set()
        unique = []

        for phone in phones:
            # Normalize for comparison
            normalized = re.sub(r'[^\d]', '', phone)
            if normalized not in seen and len(normalized) >= 10:
                seen.add(normalized)
                unique.append(phone)

        return unique

    def extract_from_google_maps_page(self, page) -> Dict[str, Optional[str]]:
        """
        Extract multiple phone numbers from Google Maps page.

        Args:
            page: Playwright page object

        Returns:
            Dictionary with phone numbers
        """
        phones = []

        try:
            # Primary phone
            phone_selectors = [
                'button[data-item-id*="phone"]',
                'button[aria-label*="Phone"]',
                'a[href^="tel:"]',
            ]

            for selector in phone_selectors:
                elements = page.query_selector_all(selector)
                for element in elements:
                    aria_label = element.get_attribute('aria-label')
                    if aria_label:
                        phone_match = re.search(r'[\d\s\-\+\(\)]+', aria_label)
                        if phone_match:
                            phone = phone_match.group().strip()
                            clean_phone = self._clean_phone(phone)
                            if clean_phone and clean_phone not in phones:
                                phones.append(clean_phone)

                    href = element.get_attribute('href')
                    if href and href.startswith('tel:'):
                        phone = href.replace('tel:', '').strip()
                        clean_phone = self._clean_phone(phone)
                        if clean_phone and clean_phone not in phones:
                            phones.append(clean_phone)

        except Exception as e:
            logger.debug(f"Error extracting phones from Google Maps page: {e}")

        return {
            'phone_1': phones[0] if len(phones) > 0 else None,
            'phone_2': phones[1] if len(phones) > 1 else None,
            'phone_3': phones[2] if len(phones) > 2 else None,
        }


# Singleton instance for easy importing
contact_extractor = ContactExtractor()
