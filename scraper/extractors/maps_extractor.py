"""Google Maps page data extraction module."""

import re
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs, unquote
from loguru import logger

try:
    from playwright.sync_api import Page
except ImportError:
    Page = None


class MapsExtractor:
    """Extract business data from Google Maps business detail pages."""

    # Selectors for various fields (multiple fallbacks)
    SELECTORS = {
        "name": [
            'h1[data-attrid="title"]',
            'h1.DUwDvf',
            'h1[class*="fontHeadlineLarge"]',
            'div[role="main"] h1',
            'h1',
        ],
        "address": [
            'button[data-item-id="address"] div.fontBodyMedium',
            'button[data-item-id*="address"]',
            'div[data-attrid="kc:/location/location:address"]',
            '[data-tooltip="Copy address"]',
            'button[aria-label*="Address"]',
        ],
        "phone": [
            'button[data-item-id*="phone"] div.fontBodyMedium',
            'button[data-item-id*="phone"]',
            'a[href^="tel:"]',
            'button[aria-label*="Phone"]',
            '[data-tooltip="Copy phone number"]',
        ],
        "website": [
            'a[data-item-id="authority"]',
            'a[aria-label*="Website"]',
            'a[data-tooltip="Open website"]',
            'a[href*="url?q="]',
        ],
        "category": [
            'button[jsaction*="category"]',
            'span[jsaction*="category"]',
            'button.DkEaL',
            'div[class*="fontBodyMedium"]:has-text("·")',
        ],
        "rating": [
            'div.F7nice span[aria-hidden="true"]',
            'span[role="img"][aria-label*="stars"]',
            'div[class*="fontDisplayLarge"]',
            'span.ceNzKf',
        ],
        "review_count": [
            'span[aria-label*="reviews"]',
            'button[jsaction*="reviews"] span',
            'span:has-text("reviews")',
            'div.F7nice span:nth-child(2)',
        ],
        "hours": [
            'table[class*="eK4R0e"]',
            'div[aria-label*="hours"]',
            'button[data-item-id*="hours"]',
            'div[jsaction*="hours"]',
        ],
        "price_level": [
            'span[aria-label*="Price"]',
            'span:has-text("$")',
        ],
    }

    def extract(self, page: Page, search_query: str = "") -> Dict:
        """
        Extract all business data from a Google Maps detail page.

        Args:
            page: Playwright page object on a business detail page
            search_query: Original search query for context

        Returns:
            Dictionary with all extracted business data
        """
        result = {
            # Basic info
            "business_name": None,
            "address": None,
            "city": None,
            "state": None,
            "pincode": None,
            "country": None,
            "phone": None,
            "website": None,
            "category": None,

            # Ratings
            "rating": None,
            "review_count": None,
            "price_level": None,

            # Hours
            "business_hours": {},
            "is_open_now": None,

            # Location
            "latitude": None,
            "longitude": None,

            # IDs
            "place_id": None,
            "cid": None,
            "maps_url": None,

            # Metadata
            "search_query": search_query,
        }

        try:
            # Wait for page to be ready (don't use networkidle - too slow for Google Maps)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass  # Continue anyway
            time.sleep(2)  # Give time for dynamic content to render

            # Extract each field
            result["business_name"] = self._extract_business_name(page)
            result["phone"] = self._extract_phone(page)
            result["website"] = self._extract_website(page)
            result["category"] = self._extract_category(page)
            result["rating"] = self._extract_rating(page)
            result["review_count"] = self._extract_review_count(page)
            result["price_level"] = self._extract_price_level(page)
            result["business_hours"] = self._extract_business_hours(page)

            # Extract address and parse components
            address_data = self._extract_address(page)
            result.update(address_data)

            # Extract coordinates from URL
            coords = self._extract_coordinates(page.url)
            result["latitude"] = coords[0]
            result["longitude"] = coords[1]

            # Extract IDs
            result["place_id"] = self._extract_place_id(page.url)
            result["cid"] = self._extract_cid(page)
            result["maps_url"] = page.url

            logger.debug(f"Extracted data for: {result.get('business_name', 'Unknown')}")

        except Exception as e:
            logger.error(f"Error extracting maps data: {e}")

        return result

    def _extract_business_name(self, page: Page) -> Optional[str]:
        """Extract business name."""
        for selector in self.SELECTORS["name"]:
            try:
                element = page.query_selector(selector)
                if element:
                    name = element.inner_text().strip()
                    if name and len(name) > 1:
                        return name
            except Exception:
                continue
        return None

    def _extract_address(self, page: Page) -> Dict:
        """Extract and parse address into components."""
        result = {
            "address": None,
            "city": None,
            "state": None,
            "pincode": None,
            "country": None,
        }

        address_text = None

        for selector in self.SELECTORS["address"]:
            try:
                element = page.query_selector(selector)
                if element:
                    # Get aria-label or text content
                    aria = element.get_attribute("aria-label")
                    if aria and "Address:" in aria:
                        address_text = aria.replace("Address:", "").strip()
                    else:
                        address_text = element.inner_text().strip()

                    if address_text and len(address_text) > 5:
                        break
            except Exception:
                continue

        if address_text:
            result["address"] = address_text
            parsed = self._parse_address(address_text)
            result.update(parsed)

        return result

    def _parse_address(self, address: str) -> Dict:
        """Parse address string into components."""
        result = {
            "city": None,
            "state": None,
            "pincode": None,
            "country": None,
        }

        if not address:
            return result

        # Split by commas
        parts = [p.strip() for p in address.split(",")]

        # Indian address format: "123 Street, City, State PIN"
        india_pin_match = re.search(r"(\d{6})", address)
        if india_pin_match:
            result["pincode"] = india_pin_match.group(1)
            result["country"] = "India"

            # Try to extract state and city
            if len(parts) >= 2:
                last_part = parts[-1].strip()
                # State with PIN
                state_pin_match = re.search(r"([A-Za-z\s]+)\s*\d{6}", last_part)
                if state_pin_match:
                    result["state"] = state_pin_match.group(1).strip()

                if len(parts) >= 3:
                    result["city"] = parts[-2].strip()
                elif len(parts) >= 2:
                    result["city"] = parts[-1].replace(result.get("pincode", ""), "").strip()

            return result

        # US address format: "123 Street, City, STATE ZIP, Country"
        us_zip_match = re.search(r"([A-Z]{2})\s*(\d{5}(?:-\d{4})?)", address)
        if us_zip_match:
            result["state"] = us_zip_match.group(1)
            result["pincode"] = us_zip_match.group(2)
            result["country"] = "USA"

            if len(parts) >= 2:
                # City is usually before state
                for i, part in enumerate(parts):
                    if result["state"] in part:
                        if i > 0:
                            result["city"] = parts[i - 1].strip()
                        break

            return result

        # UK postcode format
        uk_postcode_match = re.search(r"([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})", address, re.IGNORECASE)
        if uk_postcode_match:
            result["pincode"] = uk_postcode_match.group(1).upper()
            result["country"] = "United Kingdom"

            if len(parts) >= 2:
                result["city"] = parts[-2].strip() if len(parts) > 2 else parts[0].strip()

            return result

        # Generic fallback: assume last part is country/region, second to last is city
        if len(parts) >= 2:
            result["city"] = parts[-2].strip() if len(parts) > 2 else parts[-1].strip()

        if len(parts) >= 3:
            result["country"] = parts[-1].strip()

        return result

    def _extract_phone(self, page: Page) -> Optional[str]:
        """Extract phone number."""
        for selector in self.SELECTORS["phone"]:
            try:
                element = page.query_selector(selector)
                if element:
                    # Try href first (tel: link)
                    href = element.get_attribute("href")
                    if href and href.startswith("tel:"):
                        phone = href.replace("tel:", "").strip()
                        return self._normalize_phone(phone)

                    # Try aria-label
                    aria = element.get_attribute("aria-label")
                    if aria:
                        phone_match = re.search(r"[\d\s\-+()]{7,}", aria)
                        if phone_match:
                            return self._normalize_phone(phone_match.group(0))

                    # Try text content
                    text = element.inner_text().strip()
                    if text:
                        phone_match = re.search(r"[\d\s\-+()]{7,}", text)
                        if phone_match:
                            return self._normalize_phone(phone_match.group(0))
            except Exception:
                continue

        return None

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number format."""
        if not phone:
            return phone

        # Remove common prefixes
        phone = phone.strip()

        # Keep digits, +, and spaces for readability
        cleaned = re.sub(r"[^\d+\s\-()]", "", phone)

        return cleaned.strip()

    def _extract_website(self, page: Page) -> Optional[str]:
        """Extract website URL."""
        for selector in self.SELECTORS["website"]:
            try:
                element = page.query_selector(selector)
                if element:
                    href = element.get_attribute("href")
                    if href:
                        # Handle Google redirect URLs
                        if "url?q=" in href:
                            parsed = urlparse(href)
                            params = parse_qs(parsed.query)
                            if "q" in params:
                                return unquote(params["q"][0])

                        # Direct URL
                        if href.startswith("http"):
                            return href

            except Exception:
                continue

        return None

    def _extract_category(self, page: Page) -> Optional[str]:
        """Extract business category."""
        for selector in self.SELECTORS["category"]:
            try:
                element = page.query_selector(selector)
                if element:
                    text = element.inner_text().strip()
                    # Clean up category text
                    if text and "·" not in text:
                        return text
                    elif text and "·" in text:
                        # Usually format: "Category · Price · Status"
                        return text.split("·")[0].strip()
            except Exception:
                continue

        return None

    def _extract_rating(self, page: Page) -> Optional[float]:
        """Extract star rating."""
        for selector in self.SELECTORS["rating"]:
            try:
                element = page.query_selector(selector)
                if element:
                    # Try aria-label (e.g., "4.5 stars")
                    aria = element.get_attribute("aria-label")
                    if aria:
                        rating_match = re.search(r"([\d.]+)\s*star", aria, re.IGNORECASE)
                        if rating_match:
                            return float(rating_match.group(1))

                    # Try text content
                    text = element.inner_text().strip()
                    if text:
                        rating_match = re.search(r"^([\d.]+)$", text)
                        if rating_match:
                            rating = float(rating_match.group(1))
                            if 0 <= rating <= 5:
                                return rating
            except Exception:
                continue

        return None

    def _extract_review_count(self, page: Page) -> Optional[int]:
        """Extract number of reviews using multiple strategies."""
        # Strategy 1: aria-label with "X reviews"
        try:
            elements = page.query_selector_all('[aria-label*="reviews"]')
            for element in elements:
                aria = element.get_attribute("aria-label")
                if aria:
                    match = re.search(r"([\d,]+)\s*review", aria, re.IGNORECASE)
                    if match:
                        return int(match.group(1).replace(",", ""))
        except Exception:
            pass

        # Strategy 2: Parenthetical count like "(1,234)"
        try:
            elements = page.query_selector_all('span, div')
            for element in elements[:50]:  # Limit search
                text = element.inner_text().strip()
                if text:
                    # Match "(1,234)" pattern
                    match = re.search(r"\(([\d,]+)\)", text)
                    if match:
                        count = int(match.group(1).replace(",", ""))
                        if 0 < count < 1000000:  # Sanity check
                            return count
        except Exception:
            pass

        # Strategy 3: Text with "reviews" word
        for selector in self.SELECTORS["review_count"]:
            try:
                element = page.query_selector(selector)
                if element:
                    text = element.inner_text().strip()
                    if text:
                        match = re.search(r"([\d,]+)\s*review", text, re.IGNORECASE)
                        if match:
                            return int(match.group(1).replace(",", ""))

                        # Just a number
                        match = re.search(r"^([\d,]+)$", text)
                        if match:
                            return int(match.group(1).replace(",", ""))
            except Exception:
                continue

        return None

    def _extract_price_level(self, page: Page) -> Optional[str]:
        """Extract price level ($, $$, $$$, $$$$)."""
        for selector in self.SELECTORS["price_level"]:
            try:
                element = page.query_selector(selector)
                if element:
                    aria = element.get_attribute("aria-label")
                    if aria and "price" in aria.lower():
                        # Count dollar signs or extract level
                        dollars = re.search(r"(\$+)", aria)
                        if dollars:
                            return dollars.group(1)

                    text = element.inner_text().strip()
                    if text:
                        dollars = re.search(r"^(\$+)$", text)
                        if dollars:
                            return dollars.group(1)
            except Exception:
                continue

        return None

    def _extract_business_hours(self, page: Page) -> Dict:
        """Extract business hours for all days."""
        hours = {}

        try:
            # Try to find hours table
            for selector in self.SELECTORS["hours"]:
                table = page.query_selector(selector)
                if table:
                    # Try to expand hours if collapsed
                    try:
                        expand_button = page.query_selector('button[aria-label*="hours"], button[aria-expanded="false"]')
                        if expand_button:
                            expand_button.click()
                            time.sleep(0.5)
                    except Exception:
                        pass

                    # Extract from table rows
                    rows = table.query_selector_all("tr")
                    for row in rows:
                        cells = row.query_selector_all("td")
                        if len(cells) >= 2:
                            day = cells[0].inner_text().strip()
                            time_range = cells[1].inner_text().strip()
                            if day and time_range:
                                hours[day] = time_range

                    if hours:
                        break

            # Fallback: try aria-label parsing
            if not hours:
                hours_element = page.query_selector('[aria-label*="Sunday"], [aria-label*="Monday"]')
                if hours_element:
                    aria = hours_element.get_attribute("aria-label")
                    if aria:
                        # Parse "Monday: 9 AM – 5 PM" patterns
                        day_pattern = r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[:\s]+([^,;]+)"
                        matches = re.findall(day_pattern, aria, re.IGNORECASE)
                        for day, time_range in matches:
                            hours[day.capitalize()] = time_range.strip()

        except Exception as e:
            logger.debug(f"Error extracting hours: {e}")

        return hours

    def _extract_coordinates(self, url: str) -> Tuple[Optional[float], Optional[float]]:
        """Extract latitude and longitude from Maps URL."""
        try:
            # Pattern: @lat,lng,zoom
            match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
            if match:
                return float(match.group(1)), float(match.group(2))

            # Pattern: ll=lat,lng
            match = re.search(r"ll=(-?\d+\.\d+),(-?\d+\.\d+)", url)
            if match:
                return float(match.group(1)), float(match.group(2))

            # Pattern: center=lat,lng
            match = re.search(r"center=(-?\d+\.\d+),(-?\d+\.\d+)", url)
            if match:
                return float(match.group(1)), float(match.group(2))

        except Exception as e:
            logger.debug(f"Error extracting coordinates: {e}")

        return None, None

    def _extract_place_id(self, url: str) -> Optional[str]:
        """Extract Google Place ID from URL."""
        try:
            # Pattern: place_id=XXX or data=!1m1!4b1!2m1!1sPlaceID
            match = re.search(r"place_id=([A-Za-z0-9_-]+)", url)
            if match:
                return match.group(1)

            # From /maps/place/ URL path
            match = re.search(r"/maps/place/[^/]+/data=.*?!1s([^!]+)", url)
            if match:
                place_id = match.group(1)
                if place_id.startswith("0x"):
                    return None  # This is a CID, not place_id
                return place_id

        except Exception as e:
            logger.debug(f"Error extracting place_id: {e}")

        return None

    def _extract_cid(self, page: Page) -> Optional[str]:
        """Extract Google CID (Customer ID)."""
        try:
            url = page.url

            # Pattern: cid=XXXXX
            match = re.search(r"cid=(\d+)", url)
            if match:
                return match.group(1)

            # From data parameter
            match = re.search(r"!1s(0x[0-9a-fA-F]+:[0-9a-fA-Fx]+)", url)
            if match:
                return match.group(1)

            # Try to find in page source
            content = page.content()
            match = re.search(r'"cid":"(\d+)"', content)
            if match:
                return match.group(1)

        except Exception as e:
            logger.debug(f"Error extracting CID: {e}")

        return None

    def extract_is_open_now(self, page: Page) -> Optional[bool]:
        """Check if business is currently open."""
        try:
            # Look for "Open" or "Closed" indicators
            open_indicator = page.query_selector('span:has-text("Open now"), span:has-text("Open ⋅")')
            if open_indicator:
                return True

            closed_indicator = page.query_selector('span:has-text("Closed"), span:has-text("Closed ⋅")')
            if closed_indicator:
                return False

        except Exception:
            pass

        return None


# Singleton instance
_maps_extractor = None


def get_maps_extractor() -> MapsExtractor:
    """Get or create the Maps extractor instance."""
    global _maps_extractor
    if _maps_extractor is None:
        _maps_extractor = MapsExtractor()
    return _maps_extractor
