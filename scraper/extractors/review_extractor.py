"""Review extraction module for Google Maps scraper - Enhanced version."""
import re
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from loguru import logger

try:
    from playwright.sync_api import Page
except ImportError:
    Page = None


class ReviewExtractor:
    """Extract detailed review data from Google Maps business listings."""

    def __init__(self):
        self.reviews_scraped = 0

    def extract_reviews(
        self,
        page: Page,
        max_reviews: int = 50,
        sort_by: str = "newest"
    ) -> List[Dict]:
        """
        Extract reviews from a Google Maps business listing.

        Args:
            page: Playwright page object (should be on business details page)
            max_reviews: Maximum number of reviews to extract
            sort_by: Sort order - "newest", "highest", "lowest", "relevant"

        Returns:
            List of review dictionaries
        """
        reviews = []

        try:
            # Check if on a business page
            if "/maps/place/" not in page.url:
                logger.warning("Not on a Google Maps place page")
                return reviews

            # Click on reviews tab/section to expand
            self._open_reviews_section(page)

            # Sort reviews if needed
            if sort_by != "relevant":
                self._sort_reviews(page, sort_by)

            # Scroll to load more reviews
            self._scroll_reviews(page, max_reviews)

            # Extract review elements
            reviews = self._extract_review_data(page, max_reviews)

            self.reviews_scraped += len(reviews)
            logger.info(f"Extracted {len(reviews)} reviews")

        except Exception as e:
            logger.error(f"Error extracting reviews: {e}")

        return reviews

    def _open_reviews_section(self, page: Page) -> bool:
        """Open the reviews section/tab."""
        try:
            import time
            # Try clicking on review count to open reviews
            review_selectors = [
                'button[aria-label*="review"]',
                'button[jsaction*="pane.rating.moreReviews"]',
                'span[aria-label*="review"]',
                'div[role="tablist"] button:has-text("Reviews")',
                '[data-tab-index="1"]',  # Reviews tab
            ]

            for selector in review_selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        element.click()
                        time.sleep(2)
                        logger.debug("Opened reviews section")
                        return True
                except:
                    continue

            # Try scrolling down to reviews section
            page.evaluate('''
                const reviewsSection = document.querySelector('[aria-label*="Review"]');
                if (reviewsSection) reviewsSection.scrollIntoView();
            ''')

            return True

        except Exception as e:
            logger.debug(f"Error opening reviews section: {e}")
            return False

    def _sort_reviews(self, page: Page, sort_by: str) -> bool:
        """Sort reviews by specified criteria."""
        try:
            import time
            # Find and click sort button
            sort_button = page.query_selector('button[aria-label*="Sort"]')
            if not sort_button:
                sort_button = page.query_selector('button[data-value="Sort"]')

            if sort_button:
                sort_button.click()
                time.sleep(1)

                # Select sort option
                sort_map = {
                    "newest": "Newest",
                    "highest": "Highest rating",
                    "lowest": "Lowest rating",
                    "relevant": "Most relevant"
                }

                sort_text = sort_map.get(sort_by, "Newest")
                sort_option = page.query_selector(f'div[role="menuitem"]:has-text("{sort_text}")')

                if sort_option:
                    sort_option.click()
                    time.sleep(2)
                    logger.debug(f"Sorted reviews by: {sort_by}")
                    return True

        except Exception as e:
            logger.debug(f"Error sorting reviews: {e}")

        return False

    def _scroll_reviews(self, page: Page, target_count: int) -> int:
        """Scroll the reviews panel to load more reviews."""
        try:
            import time
            # Find the scrollable reviews container
            scroll_container = page.query_selector(
                'div[role="main"] div[tabindex="-1"]'
            )

            if not scroll_container:
                scroll_container = page.query_selector(
                    'div.m6QErb[aria-label]'
                )

            current_count = 0
            scroll_attempts = 0
            max_attempts = min(target_count // 5 + 5, 30)  # Reasonable limit

            while current_count < target_count and scroll_attempts < max_attempts:
                # Scroll down
                page.evaluate('''
                    (container) => {
                        if (container) {
                            container.scrollTop = container.scrollHeight;
                        } else {
                            // Fallback to scrolling the main content
                            const main = document.querySelector('div[role="main"]');
                            if (main) main.scrollTop = main.scrollHeight;
                        }
                    }
                ''', scroll_container)

                time.sleep(1.5)

                # Count current reviews
                review_elements = page.query_selector_all(
                    'div[data-review-id], div[class*="review"], div[aria-label*="stars"]'
                )
                current_count = len(review_elements)

                scroll_attempts += 1

                # Check if we've reached the end
                end_message = page.query_selector('span:has-text("No more reviews")')
                if end_message:
                    break

            logger.debug(f"Loaded {current_count} reviews after {scroll_attempts} scrolls")
            return current_count

        except Exception as e:
            logger.debug(f"Error scrolling reviews: {e}")
            return 0

    def _extract_review_data(self, page: Page, max_reviews: int) -> List[Dict]:
        """Extract data from individual review elements."""
        reviews = []

        try:
            # Multiple selector strategies for different Google Maps versions
            review_selectors = [
                'div[data-review-id]',
                'div[jscontroller][class*="review"]',
                'div[class*="jftiEf"]',  # Common review container class
            ]

            review_elements = []
            for selector in review_selectors:
                review_elements = page.query_selector_all(selector)
                if review_elements:
                    break

            for i, element in enumerate(review_elements[:max_reviews]):
                try:
                    review = self._parse_single_review(element)
                    if review:
                        review["index"] = i + 1
                        reviews.append(review)
                except Exception as e:
                    logger.debug(f"Error parsing review {i + 1}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error extracting review data: {e}")

        return reviews

    def _parse_single_review(self, element) -> Optional[Dict]:
        """Parse a single review element - ENHANCED VERSION with all fields."""
        try:
            import time
            review = {
                # Reviewer info
                "reviewer_name": None,
                "reviewer_profile_url": None,
                "reviewer_photo": None,
                "reviewer_reviews_count": None,
                "reviewer_photos_count": None,
                "reviewer_level": None,  # Local Guide level
                "reviewer_is_local_guide": False,

                # Review content
                "rating": None,
                "review_text": None,
                "review_date": None,
                "review_date_relative": None,
                "review_language": None,
                "is_translated": False,

                # Owner response
                "owner_response": None,
                "owner_response_date": None,

                # Media & metadata
                "review_photos": [],
                "helpful_count": 0,
                "review_id": None,
            }

            # Get review ID
            review_id = element.get_attribute('data-review-id')
            if review_id:
                review["review_id"] = review_id

            # Extract reviewer name
            name_selectors = [
                'div[class*="d4r55"] span',
                'button[class*="al6Kxe"]',
                'a[aria-label]',
                'span[class*="reviewer"]'
            ]
            for selector in name_selectors:
                try:
                    name_elem = element.query_selector(selector)
                    if name_elem:
                        review["reviewer_name"] = name_elem.inner_text()
                        # Try to get profile URL
                        href = name_elem.get_attribute('href')
                        if href:
                            review["reviewer_profile_url"] = href
                        break
                except:
                    continue

            # Extract reviewer photo
            photo_selectors = [
                'button[class*="al6Kxe"] img',
                'img[class*="NBa7we"]',
                'a[href*="contrib"] img',
                'div[class*="avatar"] img',
            ]
            for selector in photo_selectors:
                try:
                    photo_elem = element.query_selector(selector)
                    if photo_elem:
                        src = photo_elem.get_attribute('src')
                        if src and 'googleusercontent' in src:
                            # Get higher resolution version
                            review["reviewer_photo"] = re.sub(r'=s\d+-', '=s100-', src)
                            break
                except:
                    continue

            # Extract Local Guide level
            guide_selectors = [
                'span[class*="RfnDt"]:has-text("Local Guide")',
                'div[class*="guide-level"]',
                'span:has-text("Level")',
            ]
            for selector in guide_selectors:
                try:
                    guide_elem = element.query_selector(selector)
                    if guide_elem:
                        text = guide_elem.inner_text()
                        review["reviewer_is_local_guide"] = True
                        level_match = re.search(r'Level\s*(\d+)', text, re.IGNORECASE)
                        if level_match:
                            review["reviewer_level"] = int(level_match.group(1))
                        break
                except:
                    continue

            # Extract rating (stars)
            rating_selectors = [
                'span[role="img"][aria-label*="star"]',
                'span[class*="kvMYJc"]',
                'div[aria-label*="stars"]'
            ]
            for selector in rating_selectors:
                try:
                    rating_elem = element.query_selector(selector)
                    if rating_elem:
                        aria_label = rating_elem.get_attribute('aria-label')
                        if aria_label:
                            # Extract number from "5 stars" or "4 star rating"
                            match = re.search(r'(\d+)', aria_label)
                            if match:
                                review["rating"] = int(match.group(1))
                                break
                except:
                    continue

            # Extract review text
            text_selectors = [
                'span[class*="wiI7pd"]',
                'div[class*="MyEned"]',
                'span[class*="review-text"]',
                'div[data-review-id] > div > span'
            ]
            for selector in text_selectors:
                try:
                    text_elem = element.query_selector(selector)
                    if text_elem:
                        text = text_elem.inner_text()
                        if text and len(text) > 5:
                            review["review_text"] = text.strip()
                            break
                except:
                    continue

            # Try expanding "More" button if review is truncated
            if review["review_text"] and "..." in review["review_text"]:
                try:
                    more_btn = element.query_selector('button:has-text("More")')
                    if more_btn:
                        more_btn.click()
                        time.sleep(0.5)
                        # Re-extract text
                        for selector in text_selectors:
                            text_elem = element.query_selector(selector)
                            if text_elem:
                                text = text_elem.inner_text()
                                if text:
                                    review["review_text"] = text.strip()
                                    break
                except:
                    pass

            # Check if review is translated
            try:
                translated_elem = element.query_selector('span:has-text("Translated")')
                if translated_elem:
                    review["is_translated"] = True
            except:
                pass

            # Extract original language indicator
            try:
                lang_elem = element.query_selector('span[lang]')
                if lang_elem:
                    lang = lang_elem.get_attribute('lang')
                    if lang:
                        review["review_language"] = lang[:10]
            except:
                pass

            # Extract review date
            date_selectors = [
                'span[class*="rsqaWe"]',
                'span[class*="review-date"]',
                'span:has-text("ago")',
                'span:has-text("month")',
                'span:has-text("year")'
            ]
            for selector in date_selectors:
                try:
                    date_elem = element.query_selector(selector)
                    if date_elem:
                        date_text = date_elem.inner_text()
                        if date_text:
                            review["review_date_relative"] = date_text.strip()
                            review["review_date"] = self._parse_relative_date(date_text)
                            break
                except:
                    continue

            # Extract owner response
            response_selectors = [
                'div[class*="CDe7pd"]',
                'div[class*="owner-response"]',
                'div:has-text("Response from")'
            ]
            for selector in response_selectors:
                try:
                    response_elem = element.query_selector(selector)
                    if response_elem:
                        response_text = response_elem.inner_text()
                        if "Response from" in response_text:
                            # Split to get actual response
                            parts = response_text.split('\n')
                            if len(parts) > 1:
                                review["owner_response"] = '\n'.join(parts[1:]).strip()

                            # Try to get response date
                            date_match = re.search(r'(\d+\s*(day|week|month|year)s?\s*ago)', response_text)
                            if date_match:
                                review["owner_response_date"] = self._parse_relative_date(date_match.group(1))
                            break
                except:
                    continue

            # Extract reviewer stats (total reviews/photos)
            stats_selectors = [
                'div[class*="RfnDt"]',
                'span:has-text("review")',
                'span:has-text("photo")'
            ]
            for selector in stats_selectors:
                try:
                    stats_elem = element.query_selector(selector)
                    if stats_elem:
                        stats_text = stats_elem.inner_text()
                        # Parse "15 reviews · 5 photos"
                        reviews_match = re.search(r'(\d+)\s*review', stats_text)
                        photos_match = re.search(r'(\d+)\s*photo', stats_text)
                        if reviews_match:
                            review["reviewer_reviews_count"] = int(reviews_match.group(1))
                        if photos_match:
                            review["reviewer_photos_count"] = int(photos_match.group(1))
                        break
                except:
                    continue

            # Extract review photos (with higher resolution)
            try:
                photo_elems = element.query_selector_all('button[aria-label*="Photo"] img, div[class*="review-photo"] img')
                for photo_elem in photo_elems[:5]:  # Limit to 5 photos
                    src = photo_elem.get_attribute('src')
                    if src and 'googleusercontent' in src:
                        # Get higher resolution version
                        high_res = re.sub(r'=s\d+-', '=s400-', src)
                        high_res = re.sub(r'=w\d+-h\d+', '=w400-h300', high_res)
                        review["review_photos"].append(high_res)
            except:
                pass

            # Extract helpful count (likes)
            try:
                helpful_selectors = [
                    'button[aria-label*="helpful"]',
                    'span:has-text("found this helpful")',
                ]
                for selector in helpful_selectors:
                    helpful_elem = element.query_selector(selector)
                    if helpful_elem:
                        text = helpful_elem.get_attribute('aria-label') or helpful_elem.inner_text()
                        match = re.search(r'(\d+)', text)
                        if match:
                            review["helpful_count"] = int(match.group(1))
                        break
            except:
                pass

            # Only return if we have at least some content
            if review["reviewer_name"] or review["review_text"] or review["rating"]:
                return review

            return None

        except Exception as e:
            logger.debug(f"Error parsing review: {e}")
            return None

    def _parse_relative_date(self, relative_date: str) -> Optional[str]:
        """Convert relative date string to ISO format."""
        try:
            now = datetime.now()
            relative_date = relative_date.lower().strip()

            if "just now" in relative_date or "moment" in relative_date:
                return now.strftime("%Y-%m-%d")

            # Parse patterns like "2 days ago", "3 weeks ago", etc.
            patterns = [
                (r'(\d+)\s*minute', 'minutes'),
                (r'(\d+)\s*hour', 'hours'),
                (r'(\d+)\s*day', 'days'),
                (r'(\d+)\s*week', 'weeks'),
                (r'(\d+)\s*month', 'months'),
                (r'(\d+)\s*year', 'years'),
                (r'a\s*day', 'days', 1),
                (r'a\s*week', 'weeks', 1),
                (r'a\s*month', 'months', 1),
                (r'a\s*year', 'years', 1),
            ]

            for pattern in patterns:
                if len(pattern) == 3:
                    regex, unit, value = pattern
                else:
                    regex, unit = pattern
                    value = None

                match = re.search(regex, relative_date)
                if match:
                    if value is None:
                        value = int(match.group(1))

                    if unit == 'minutes':
                        delta = timedelta(minutes=value)
                    elif unit == 'hours':
                        delta = timedelta(hours=value)
                    elif unit == 'days':
                        delta = timedelta(days=value)
                    elif unit == 'weeks':
                        delta = timedelta(weeks=value)
                    elif unit == 'months':
                        delta = timedelta(days=value * 30)  # Approximate
                    elif unit == 'years':
                        delta = timedelta(days=value * 365)  # Approximate
                    else:
                        continue

                    result_date = now - delta
                    return result_date.strftime("%Y-%m-%d")

        except Exception as e:
            logger.debug(f"Error parsing relative date '{relative_date}': {e}")

        return None

    def get_review_summary(self, page: Page) -> Dict:
        """
        Get review summary statistics from a business listing.

        Args:
            page: Playwright page object

        Returns:
            Dict with review statistics
        """
        summary = {
            "total_reviews": 0,
            "average_rating": 0.0,
            "rating_distribution": {
                5: 0, 4: 0, 3: 0, 2: 0, 1: 0
            },
            "recent_reviews_sentiment": None
        }

        try:
            # Extract total reviews
            review_count_selectors = [
                'span[aria-label*="review"]',
                'button[aria-label*="review"] span',
                'div[class*="F7nice"] span'
            ]

            for selector in review_count_selectors:
                try:
                    elem = page.query_selector(selector)
                    if elem:
                        text = elem.inner_text()
                        match = re.search(r'([\d,]+)', text.replace(',', ''))
                        if match:
                            summary["total_reviews"] = int(match.group(1))
                            break
                except:
                    continue

            # Extract average rating
            rating_selectors = [
                'div[class*="F7nice"] span[aria-hidden="true"]',
                'span[class*="ceNzKf"]',
                'div[aria-label*="stars"]'
            ]

            for selector in rating_selectors:
                try:
                    elem = page.query_selector(selector)
                    if elem:
                        text = elem.inner_text()
                        match = re.search(r'([\d.]+)', text)
                        if match:
                            summary["average_rating"] = float(match.group(1))
                            break
                except:
                    continue

            # Try to extract rating distribution (if visible)
            try:
                distribution_rows = page.query_selector_all('tr[aria-label*="star"]')
                for row in distribution_rows:
                    label = row.get_attribute('aria-label')
                    if label:
                        # Parse "5 stars, 234 reviews, 45%"
                        stars_match = re.search(r'(\d)\s*star', label)
                        count_match = re.search(r'(\d+)\s*review', label)
                        if stars_match and count_match:
                            stars = int(stars_match.group(1))
                            count = int(count_match.group(1))
                            summary["rating_distribution"][stars] = count
            except:
                pass

        except Exception as e:
            logger.error(f"Error getting review summary: {e}")

        return summary


# Singleton instance
_review_extractor = None

def get_review_extractor() -> ReviewExtractor:
    """Get or create the review extractor instance."""
    global _review_extractor
    if _review_extractor is None:
        _review_extractor = ReviewExtractor()
    return _review_extractor
