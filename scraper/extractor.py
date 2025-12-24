"""Data extraction logic for Google Maps listings."""
from playwright.async_api import Page
from typing import Dict, Optional, List
import re
from loguru import logger
from datetime import datetime


class DataExtractor:
    """Extracts business data from Google Maps pages."""

    @staticmethod
    async def extract_business_data(page: Page, search_query: str) -> Optional[Dict]:
        """Extract all available business data from a Google Maps listing page."""
        try:
            data = {
                'search_query': search_query,
                'scraped_at': datetime.now(),
            }

            # Extract business name
            data['business_name'] = await DataExtractor._extract_business_name(page)
            if not data['business_name']:
                logger.warning("Could not extract business name, skipping")
                return None

            # Extract address components
            address_data = await DataExtractor._extract_address(page)
            data.update(address_data)

            # Extract phone number
            data['phone'] = await DataExtractor._extract_phone(page)

            # Extract website
            data['website'] = await DataExtractor._extract_website(page)

            # Extract category
            data['category'] = await DataExtractor._extract_category(page)

            # Extract rating and reviews
            rating_data = await DataExtractor._extract_rating_reviews(page)
            data.update(rating_data)

            # Extract Google Maps URL and Place ID
            data['maps_url'] = page.url
            data['place_id'] = await DataExtractor._extract_place_id(page)

            # Extract coordinates from URL
            coords = await DataExtractor._extract_coordinates(page)
            data.update(coords)

            # Calculate data quality score
            data['data_quality_score'] = DataExtractor._calculate_quality_score(data)

            logger.info(f"Extracted data for: {data['business_name']} (quality: {data['data_quality_score']}%)")
            return data

        except Exception as e:
            logger.error(f"Error extracting business data: {e}")
            return None

    @staticmethod
    async def _extract_business_name(page: Page) -> Optional[str]:
        """Extract business name from the page."""
        selectors = [
            'h1.DUwDvf',  # Main heading
            'h1[class*="fontHeadline"]',
            'h1.tAiQdd',
            'div[role="main"] h1',
        ]

        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    name = await element.inner_text()
                    if name and name.strip():
                        return name.strip()
            except:
                continue

        return None

    @staticmethod
    async def _extract_address(page: Page) -> Dict:
        """Extract full address and parse components."""
        address_data = {
            'full_address': None,
            'city': None,
            'state': None,
            'pin_code': None,
        }

        selectors = [
            'button[data-item-id="address"]',
            'div[data-item-id="address"]',
            'button[aria-label*="Address"]',
        ]

        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    # Try aria-label first
                    aria_label = await element.get_attribute('aria-label')
                    if aria_label and 'Address:' in aria_label:
                        address = aria_label.replace('Address:', '').strip()
                        address_data['full_address'] = address
                        break

                    # Try inner text
                    text = await element.inner_text()
                    if text and text.strip():
                        address_data['full_address'] = text.strip()
                        break
            except:
                continue

        # Parse address components if we have an address
        if address_data['full_address']:
            address_data.update(DataExtractor._parse_address_components(address_data['full_address']))

        return address_data

    @staticmethod
    def _parse_address_components(address: str) -> Dict:
        """Parse city, state, and pin code from full address."""
        components = {
            'city': None,
            'state': None,
            'pin_code': None,
        }

        # Extract pin code (Indian format: 6 digits)
        pin_match = re.search(r'\b(\d{6})\b', address)
        if pin_match:
            components['pin_code'] = pin_match.group(1)

        # Common Indian states (abbreviated and full names)
        states = [
            'Maharashtra', 'Delhi', 'Karnataka', 'Tamil Nadu', 'Gujarat', 'Rajasthan',
            'Uttar Pradesh', 'West Bengal', 'Madhya Pradesh', 'Kerala', 'Telangana',
            'Andhra Pradesh', 'Punjab', 'Haryana', 'Bihar', 'Odisha', 'Assam',
            'MH', 'DL', 'KA', 'TN', 'GJ', 'RJ', 'UP', 'WB', 'MP', 'KL', 'TG', 'AP',
        ]

        for state in states:
            if state in address:
                components['state'] = state
                break

        # Try to extract city (usually before state or pin code)
        # This is a simple heuristic and may need improvement
        parts = address.split(',')
        for i, part in enumerate(parts):
            part = part.strip()
            if components['state'] and components['state'] in part:
                # City is likely in the previous part
                if i > 0:
                    components['city'] = parts[i - 1].strip()
                break
            elif components['pin_code'] and components['pin_code'] in part:
                # City might be in this or previous part
                if i > 0:
                    components['city'] = parts[i - 1].strip()
                break

        return components

    @staticmethod
    async def _extract_phone(page: Page) -> Optional[str]:
        """Extract phone number from the page."""
        selectors = [
            'button[data-item-id*="phone"]',
            'button[aria-label*="Phone"]',
            'a[href^="tel:"]',
        ]

        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    # Try aria-label
                    aria_label = await element.get_attribute('aria-label')
                    if aria_label:
                        # Extract phone from aria-label
                        phone_match = re.search(r'[\d\s\-\+\(\)]+', aria_label)
                        if phone_match:
                            phone = phone_match.group().strip()
                            # Clean up phone number
                            phone = re.sub(r'[^\d\+]', '', phone)
                            if len(phone) >= 10:
                                return phone

                    # Try href for tel: links
                    href = await element.get_attribute('href')
                    if href and href.startswith('tel:'):
                        phone = href.replace('tel:', '').strip()
                        phone = re.sub(r'[^\d\+]', '', phone)
                        if len(phone) >= 10:
                            return phone

                    # Try inner text
                    text = await element.inner_text()
                    if text:
                        phone_match = re.search(r'[\d\s\-\+\(\)]+', text)
                        if phone_match:
                            phone = phone_match.group().strip()
                            phone = re.sub(r'[^\d\+]', '', phone)
                            if len(phone) >= 10:
                                return phone
            except:
                continue

        return None

    @staticmethod
    async def _extract_website(page: Page) -> Optional[str]:
        """Extract website URL from the page."""
        selectors = [
            'a[data-item-id="authority"]',
            'a[aria-label*="Website"]',
            'a[href*="http"][data-item-id*="website"]',
        ]

        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    href = await element.get_attribute('href')
                    if href and (href.startswith('http://') or href.startswith('https://')):
                        # Google Maps sometimes wraps URLs
                        if 'google.com/url?' in href:
                            # Extract actual URL from Google redirect
                            url_match = re.search(r'[?&]q=([^&]+)', href)
                            if url_match:
                                from urllib.parse import unquote
                                return unquote(url_match.group(1))
                        return href
            except:
                continue

        return None

    @staticmethod
    async def _extract_category(page: Page) -> Optional[str]:
        """Extract business category from the page."""
        selectors = [
            'button[jsaction*="category"]',
            'button.DkEaL',
            'div[class*="category"]',
        ]

        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and text.strip():
                        return text.strip()
            except:
                continue

        return None

    @staticmethod
    async def _extract_rating_reviews(page: Page) -> Dict:
        """Extract rating and review count."""
        data = {
            'rating': None,
            'review_count': None,
        }

        try:
            # Rating is usually in format "4.5" with stars
            rating_selectors = [
                'div.F7nice span[aria-hidden="true"]',
                'span.ceNzKf[aria-hidden="true"]',
            ]

            for selector in rating_selectors:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    rating_match = re.search(r'(\d+\.?\d*)', text)
                    if rating_match:
                        data['rating'] = float(rating_match.group(1))
                        break

            # Review count is usually in format "(123)"
            review_selectors = [
                'div.F7nice span[aria-label*="reviews"]',
                'button[aria-label*="reviews"]',
            ]

            for selector in review_selectors:
                element = await page.query_selector(selector)
                if element:
                    aria_label = await element.get_attribute('aria-label')
                    if aria_label:
                        review_match = re.search(r'(\d+)\s+review', aria_label)
                        if review_match:
                            data['review_count'] = int(review_match.group(1))
                            break

        except Exception as e:
            logger.debug(f"Error extracting rating/reviews: {e}")

        return data

    @staticmethod
    async def _extract_place_id(page: Page) -> Optional[str]:
        """Extract Google Place ID from URL or page data."""
        try:
            url = page.url

            # Try to extract from URL patterns
            # Pattern 1: /maps/place/[name]/data=...!1s[ChIJ...]
            place_id_match = re.search(r'!1s(ChIJ[a-zA-Z0-9_-]+)', url)
            if place_id_match:
                return place_id_match.group(1)

            # Pattern 2: cid parameter (CID can be converted to Place ID, but we'll store CID)
            cid_match = re.search(r'[?&]cid=(\d+)', url)
            if cid_match:
                return f"cid:{cid_match.group(1)}"

        except Exception as e:
            logger.debug(f"Error extracting place ID: {e}")

        return None

    @staticmethod
    async def _extract_coordinates(page: Page) -> Dict:
        """Extract latitude and longitude from URL."""
        coords = {
            'latitude': None,
            'longitude': None,
        }

        try:
            url = page.url

            # Pattern: @latitude,longitude,zoom
            coords_match = re.search(r'@(-?\d+\.?\d*),(-?\d+\.?\d*),', url)
            if coords_match:
                coords['latitude'] = float(coords_match.group(1))
                coords['longitude'] = float(coords_match.group(2))

        except Exception as e:
            logger.debug(f"Error extracting coordinates: {e}")

        return coords

    @staticmethod
    def _calculate_quality_score(data: Dict) -> int:
        """Calculate data quality score (0-100) based on completeness."""
        important_fields = [
            'business_name',
            'full_address',
            'city',
            'state',
            'pin_code',
            'phone',
            'website',
            'category',
            'place_id',
        ]

        filled = sum(1 for field in important_fields if data.get(field))
        total = len(important_fields)

        return int((filled / total) * 100)
