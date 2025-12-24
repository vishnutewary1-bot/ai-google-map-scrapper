"""Main Google Maps scraper implementation."""
from typing import List, Dict, Optional
import asyncio
from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from scraper.browser_manager import BrowserManager
from scraper.extractor import DataExtractor
from database import db_manager, BusinessLead, ScrapeJob
from config.settings import settings


class GoogleMapsScraper:
    """Main scraper class for Google Maps."""

    def __init__(self):
        self.browser_manager = BrowserManager()
        self.extractor = DataExtractor()
        self.request_count = 0
        self.results_scraped = 0

    async def initialize(self):
        """Initialize scraper and browser."""
        await self.browser_manager.initialize()
        await self.browser_manager.launch_browser()
        logger.info("Google Maps Scraper initialized")

    async def search_and_scrape(
        self,
        search_query: str,
        location: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict]:
        """
        Search Google Maps and scrape business listings.

        Args:
            search_query: The search term (e.g., "restaurants", "doctors")
            location: Location to search in (e.g., "Mumbai", "Delhi NCR")
            max_results: Maximum number of results to scrape

        Returns:
            List of scraped business data dictionaries
        """
        try:
            # Construct search query
            if location:
                full_query = f"{search_query} in {location}"
            else:
                full_query = search_query

            logger.info(f"Starting search: '{full_query}' (max results: {max_results})")

            # Create scrape job in database
            job = await self._create_scrape_job(full_query, max_results)

            # Perform search
            page = await self.browser_manager.new_page()
            await self._perform_search(page, full_query)

            # Wait for results to load
            await asyncio.sleep(3)

            # Scrape listings
            results = await self._scrape_listings(page, full_query, max_results, job.id)

            # Update job status
            await self._update_job_status(job.id, 'completed', len(results))

            logger.info(f"Search completed: {len(results)} businesses scraped")

            await page.close()
            return results

        except Exception as e:
            logger.error(f"Error during search and scrape: {e}")
            if 'job' in locals():
                await self._update_job_status(job.id, 'failed', 0, str(e))
            raise

    async def _perform_search(self, page: Page, query: str):
        """Perform search on Google Maps."""
        try:
            # Navigate to Google Maps
            logger.info("Navigating to Google Maps...")
            await page.goto('https://www.google.com/maps', wait_until='networkidle')

            # Random delay to appear human-like
            await self.browser_manager.random_delay(2, 4)

            # Find search box and enter query
            search_box_selector = 'input#searchboxinput'
            await page.wait_for_selector(search_box_selector, timeout=10000)

            # Type search query with human-like delays
            await page.fill(search_box_selector, query)
            await asyncio.sleep(0.5)

            # Click search button or press Enter
            search_button = 'button#searchbox-searchbutton'
            try:
                await page.click(search_button)
            except:
                await page.press(search_box_selector, 'Enter')

            # Wait for results to load
            logger.info("Waiting for search results...")
            await asyncio.sleep(3)

            # Check if results appeared
            results_selector = 'div[role="feed"]'
            await page.wait_for_selector(results_selector, timeout=15000)

            logger.info("Search results loaded successfully")

        except Exception as e:
            logger.error(f"Error performing search: {e}")
            raise

    async def _scrape_listings(
        self,
        page: Page,
        search_query: str,
        max_results: int,
        job_id: int
    ) -> List[Dict]:
        """Scrape business listings from search results."""
        results = []
        scraped_urls = set()

        try:
            # Scroll and load more results
            await self._scroll_results_panel(page, max_results)

            # Get all business listing links
            listing_links = await self._get_listing_links(page)
            logger.info(f"Found {len(listing_links)} listings to scrape")

            # Scrape each listing
            for i, link_data in enumerate(listing_links[:max_results]):
                try:
                    # Skip if already scraped
                    if link_data['url'] in scraped_urls:
                        continue

                    logger.info(f"Scraping listing {i + 1}/{min(len(listing_links), max_results)}: {link_data['name']}")

                    # Click on the listing
                    await self._click_listing(page, link_data)

                    # Wait for details to load
                    await asyncio.sleep(2)

                    # Extract business data
                    business_data = await self.extractor.extract_business_data(page, search_query)

                    if business_data:
                        # Save to database
                        saved = await self._save_to_database(business_data)
                        if saved:
                            results.append(business_data)
                            scraped_urls.add(link_data['url'])
                            self.results_scraped += 1

                            # Update job progress
                            await self._update_job_progress(job_id, len(results))

                    # Rate limiting - random delay between requests
                    await self.browser_manager.random_delay()

                    # Longer delay after every 10 results
                    if (i + 1) % 10 == 0:
                        logger.info("Taking a longer break after 10 results...")
                        await asyncio.sleep(30)

                except Exception as e:
                    logger.error(f"Error scraping listing {i + 1}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping listings: {e}")

        return results

    async def _scroll_results_panel(self, page: Page, target_count: int):
        """Scroll the results panel to load more listings."""
        try:
            results_panel = 'div[role="feed"]'

            # Scroll multiple times to load more results
            scroll_attempts = min(target_count // 20 + 1, 10)  # Max 10 scrolls

            for i in range(scroll_attempts):
                # Scroll to bottom of results panel
                await page.evaluate(f'''
                    const feed = document.querySelector('{results_panel}');
                    if (feed) {{
                        feed.scrollTop = feed.scrollHeight;
                    }}
                ''')

                await asyncio.sleep(2)

                # Check if "You've reached the end" message appears
                try:
                    end_message = await page.query_selector('span:has-text("You\'ve reached the end")')
                    if end_message:
                        logger.info("Reached end of results")
                        break
                except:
                    pass

            logger.info(f"Completed {i + 1} scroll attempts")

        except Exception as e:
            logger.debug(f"Error scrolling results: {e}")

    async def _get_listing_links(self, page: Page) -> List[Dict]:
        """Get all listing links from the results panel."""
        try:
            # Wait a bit for all results to render
            await asyncio.sleep(2)

            # Get all listing elements
            listing_selector = 'div[role="feed"] a[href*="/maps/place/"]'
            elements = await page.query_selector_all(listing_selector)

            links = []
            seen_urls = set()

            for element in elements:
                try:
                    href = await element.get_attribute('href')
                    aria_label = await element.get_attribute('aria-label')

                    if href and href not in seen_urls:
                        # Extract business name from aria-label if available
                        name = aria_label if aria_label else f"Business {len(links) + 1}"

                        links.append({
                            'url': href,
                            'name': name,
                            'element': element
                        })
                        seen_urls.add(href)

                except Exception as e:
                    logger.debug(f"Error extracting link: {e}")
                    continue

            return links

        except Exception as e:
            logger.error(f"Error getting listing links: {e}")
            return []

    async def _click_listing(self, page: Page, link_data: Dict):
        """Click on a listing to open its details."""
        try:
            # Try clicking the element directly
            try:
                await link_data['element'].click(timeout=5000)
                await asyncio.sleep(1)
                return
            except:
                pass

            # Fallback: navigate to URL directly
            await page.goto(link_data['url'], wait_until='domcontentloaded')
            await asyncio.sleep(2)

        except Exception as e:
            logger.debug(f"Error clicking listing: {e}")
            raise

    async def _save_to_database(self, business_data: Dict) -> bool:
        """Save business data to database."""
        try:
            with db_manager.get_session() as session:
                # Check if already exists by place_id
                if business_data.get('place_id'):
                    existing = session.query(BusinessLead).filter_by(
                        place_id=business_data['place_id']
                    ).first()

                    if existing:
                        logger.info(f"Business already exists: {business_data['business_name']}")
                        return False

                # Create new lead
                lead = BusinessLead(**business_data)
                lead.calculate_quality_score()

                session.add(lead)
                session.commit()

                logger.info(f"Saved to database: {business_data['business_name']} (ID: {lead.id})")
                return True

        except Exception as e:
            logger.error(f"Error saving to database: {e}")
            return False

    async def _create_scrape_job(self, search_query: str, max_results: int) -> ScrapeJob:
        """Create a new scrape job in the database."""
        try:
            with db_manager.get_session() as session:
                job = ScrapeJob(
                    search_query=search_query,
                    max_results=max_results,
                    leads_target=max_results,
                    status='running',
                    started_at=asyncio.get_event_loop().time()
                )
                session.add(job)
                session.commit()
                session.refresh(job)

                logger.info(f"Created scrape job: {job.id}")
                return job

        except Exception as e:
            logger.error(f"Error creating scrape job: {e}")
            raise

    async def _update_job_progress(self, job_id: int, leads_scraped: int):
        """Update job progress in database."""
        try:
            with db_manager.get_session() as session:
                job = session.query(ScrapeJob).filter_by(id=job_id).first()
                if job:
                    job.leads_scraped = leads_scraped
                    session.commit()

        except Exception as e:
            logger.debug(f"Error updating job progress: {e}")

    async def _update_job_status(
        self,
        job_id: int,
        status: str,
        leads_scraped: int,
        error: Optional[str] = None
    ):
        """Update job status in database."""
        try:
            with db_manager.get_session() as session:
                job = session.query(ScrapeJob).filter_by(id=job_id).first()
                if job:
                    job.status = status
                    job.leads_scraped = leads_scraped

                    if status == 'completed':
                        job.completed_at = asyncio.get_event_loop().time()

                    if error:
                        job.last_error = error
                        job.error_count += 1

                    session.commit()
                    logger.info(f"Updated job {job_id} status to: {status}")

        except Exception as e:
            logger.error(f"Error updating job status: {e}")

    async def close(self):
        """Close browser and cleanup."""
        await self.browser_manager.close()
        logger.info("Scraper closed")
