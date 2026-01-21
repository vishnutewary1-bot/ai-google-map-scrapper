"""Social media link extraction from business websites."""
import re
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from loguru import logger
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError


class SocialMediaExtractor:
    """Extract social media links from business websites."""

    # Social media URL patterns
    SOCIAL_PATTERNS = {
        'facebook': [
            r'(?:https?://)?(?:www\.)?facebook\.com/(?!sharer)([a-zA-Z0-9._-]+)/?',
            r'(?:https?://)?(?:www\.)?fb\.com/([a-zA-Z0-9._-]+)/?',
            r'(?:https?://)?(?:m\.)?facebook\.com/([a-zA-Z0-9._-]+)/?',
        ],
        'instagram': [
            r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9._]+)/?',
            r'(?:https?://)?(?:www\.)?instagr\.am/([a-zA-Z0-9._]+)/?',
        ],
        'linkedin': [
            r'(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/([a-zA-Z0-9._-]+)/?',
            r'(?:https?://)?(?:www\.)?linkedin\.com/(?:pub)/([a-zA-Z0-9._-]+)/?',
        ],
        'twitter': [
            r'(?:https?://)?(?:www\.)?twitter\.com/([a-zA-Z0-9_]+)/?',
            r'(?:https?://)?(?:www\.)?x\.com/([a-zA-Z0-9_]+)/?',
        ],
        'youtube': [
            r'(?:https?://)?(?:www\.)?youtube\.com/(?:channel|c|user)/([a-zA-Z0-9._-]+)/?',
            r'(?:https?://)?(?:www\.)?youtube\.com/@([a-zA-Z0-9._-]+)/?',
        ],
        'tiktok': [
            r'(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9._]+)/?',
        ],
        'pinterest': [
            r'(?:https?://)?(?:www\.)?pinterest\.com/([a-zA-Z0-9._-]+)/?',
        ],
        'whatsapp': [
            r'(?:https?://)?(?:api\.)?whatsapp\.com/send\?phone=(\d+)',
            r'(?:https?://)?wa\.me/(\d+)',
        ],
    }

    # Headers to mimic a real browser
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    def __init__(self, timeout: int = 10, max_retries: int = 2):
        """
        Initialize the social media extractor.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def extract_from_website(self, website_url: str) -> Dict[str, Optional[str]]:
        """
        Extract all social media links from a website.

        Args:
            website_url: The business website URL

        Returns:
            Dictionary with social media platform names as keys and URLs as values
        """
        result = {
            'facebook': None,
            'instagram': None,
            'linkedin': None,
            'twitter': None,
            'youtube': None,
            'tiktok': None,
            'pinterest': None,
            'whatsapp': None,
        }

        if not website_url:
            return result

        try:
            # Normalize URL
            if not website_url.startswith(('http://', 'https://')):
                website_url = 'https://' + website_url

            # Fetch the page content
            html_content = self._fetch_page(website_url)
            if not html_content:
                return result

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract links from various sources
            all_links = self._extract_all_links(soup, website_url)

            # Also search in page text for social media URLs
            page_text = soup.get_text()
            text_links = self._extract_links_from_text(page_text)
            all_links.update(text_links)

            # Match social media patterns
            for link in all_links:
                for platform, patterns in self.SOCIAL_PATTERNS.items():
                    if result[platform]:  # Already found
                        continue

                    for pattern in patterns:
                        match = re.search(pattern, link, re.IGNORECASE)
                        if match:
                            result[platform] = self._normalize_social_url(platform, link, match)
                            break

            # Try to find social links on common pages (contact, about)
            if not all(result.values()):
                additional_pages = self._get_additional_pages_to_check(soup, website_url)
                for page_url in additional_pages[:3]:  # Limit to 3 additional pages
                    try:
                        page_html = self._fetch_page(page_url)
                        if page_html:
                            page_soup = BeautifulSoup(page_html, 'html.parser')
                            page_links = self._extract_all_links(page_soup, page_url)

                            for link in page_links:
                                for platform, patterns in self.SOCIAL_PATTERNS.items():
                                    if result[platform]:
                                        continue

                                    for pattern in patterns:
                                        match = re.search(pattern, link, re.IGNORECASE)
                                        if match:
                                            result[platform] = self._normalize_social_url(platform, link, match)
                                            break
                    except Exception:
                        continue

            logger.info(f"Extracted social media from {website_url}: {sum(1 for v in result.values() if v)} platforms found")

        except Exception as e:
            logger.warning(f"Error extracting social media from {website_url}: {e}")

        return result

    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content with retries."""
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    verify=False  # Some sites have SSL issues
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

    def _extract_all_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """Extract all links from a page."""
        links = set()

        # From anchor tags
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            if href:
                # Handle relative URLs
                full_url = urljoin(base_url, href)
                links.add(full_url)

        # From social media icon links (common patterns)
        for tag in soup.find_all(['a', 'div', 'span'], class_=True):
            classes = ' '.join(tag.get('class', []))
            if any(social in classes.lower() for social in ['facebook', 'instagram', 'twitter', 'linkedin', 'youtube', 'social']):
                href = tag.get('href', '')
                if href:
                    links.add(urljoin(base_url, href))

                # Check for data attributes
                for attr in ['data-href', 'data-url', 'data-link']:
                    if tag.has_attr(attr):
                        links.add(tag[attr])

        # From meta tags
        for meta in soup.find_all('meta', property=True):
            prop = meta.get('property', '')
            if 'social' in prop or any(p in prop for p in ['fb:', 'og:', 'twitter:']):
                content = meta.get('content', '')
                if content and content.startswith('http'):
                    links.add(content)

        # From script tags (JSON-LD structured data)
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string or '{}')
                self._extract_from_json_ld(data, links)
            except (json.JSONDecodeError, TypeError):
                continue

        return links

    def _extract_from_json_ld(self, data: dict, links: Set[str]):
        """Extract social media links from JSON-LD structured data."""
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ['sameAs', 'url', 'socialMedia']:
                    if isinstance(value, list):
                        links.update(v for v in value if isinstance(v, str))
                    elif isinstance(value, str):
                        links.add(value)
                elif isinstance(value, (dict, list)):
                    if isinstance(value, dict):
                        self._extract_from_json_ld(value, links)
                    else:
                        for item in value:
                            if isinstance(item, dict):
                                self._extract_from_json_ld(item, links)

    def _extract_links_from_text(self, text: str) -> Set[str]:
        """Extract URLs from plain text."""
        links = set()

        # General URL pattern
        url_pattern = r'https?://[^\s<>"\']+|www\.[^\s<>"\']+'
        matches = re.findall(url_pattern, text)
        links.update(matches)

        return links

    def _get_additional_pages_to_check(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Get additional pages that might contain social media links."""
        pages = []

        # Common page names for contact/about info
        contact_keywords = ['contact', 'about', 'about-us', 'connect', 'follow', 'social']

        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '').lower()
            text = a_tag.get_text().lower()

            if any(keyword in href or keyword in text for keyword in contact_keywords):
                full_url = urljoin(base_url, a_tag['href'])
                if full_url not in pages:
                    pages.append(full_url)

        return pages

    def _normalize_social_url(self, platform: str, url: str, match: re.Match) -> str:
        """Normalize social media URL to a standard format."""
        username = match.group(1)

        base_urls = {
            'facebook': f'https://www.facebook.com/{username}',
            'instagram': f'https://www.instagram.com/{username}',
            'linkedin': f'https://www.linkedin.com/company/{username}' if '/company/' in url.lower() else f'https://www.linkedin.com/in/{username}',
            'twitter': f'https://twitter.com/{username}',
            'youtube': f'https://www.youtube.com/@{username}' if '@' in url else f'https://www.youtube.com/channel/{username}',
            'tiktok': f'https://www.tiktok.com/@{username}',
            'pinterest': f'https://www.pinterest.com/{username}',
            'whatsapp': f'https://wa.me/{username}',
        }

        return base_urls.get(platform, url)

    def extract_from_multiple_websites(
        self,
        websites: List[str],
        max_workers: int = 5
    ) -> List[Dict[str, Optional[str]]]:
        """
        Extract social media links from multiple websites concurrently.

        Args:
            websites: List of website URLs
            max_workers: Maximum number of concurrent workers

        Returns:
            List of dictionaries with social media links for each website
        """
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(self.extract_from_website, url): url
                for url in websites
            }

            for future in future_to_url:
                url = future_to_url[future]
                try:
                    result = future.result(timeout=30)
                    results.append(result)
                except FuturesTimeoutError:
                    logger.warning(f"Timeout extracting social media from {url}")
                    results.append({k: None for k in self.SOCIAL_PATTERNS.keys()})
                except Exception as e:
                    logger.error(f"Error extracting social media from {url}: {e}")
                    results.append({k: None for k in self.SOCIAL_PATTERNS.keys()})

        return results

    def extract_from_google_maps_page(self, page) -> Dict[str, Optional[str]]:
        """
        Extract social media links directly from a Google Maps business page.

        Args:
            page: Playwright page object

        Returns:
            Dictionary with social media links found on the Google Maps page
        """
        result = {
            'facebook': None,
            'instagram': None,
            'linkedin': None,
            'twitter': None,
            'youtube': None,
        }

        try:
            # Get all links on the page
            links = page.query_selector_all('a[href]')

            for link in links:
                href = link.get_attribute('href')
                if not href:
                    continue

                for platform, patterns in self.SOCIAL_PATTERNS.items():
                    if platform not in result or result[platform]:
                        continue

                    for pattern in patterns:
                        match = re.search(pattern, href, re.IGNORECASE)
                        if match:
                            result[platform] = self._normalize_social_url(platform, href, match)
                            break

        except Exception as e:
            logger.debug(f"Error extracting social media from Google Maps page: {e}")

        return result


# Singleton instance for easy importing
social_media_extractor = SocialMediaExtractor()
