"""Enhanced Google Maps scraper with Phase 2 features (proxy, session management, rate limiting)."""
from typing import List, Dict, Optional
import asyncio
from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from scraper.browser_manager import BrowserManager
from scraper.extractor import DataExtractor
from scraper.proxy_manager import ProxyManager
from scraper.session_manager import SessionManager
from scraper.rate_limiter import RateLimiter
from scraper.error_handler import retry_async, error_recovery, FatalError
from database import db_manager, BusinessLead, ScrapeJob
from config.settings import settings


class EnhancedGoogleMapsScraper:
    """
    Enhanced Google Maps scraper with:
    - Proxy rotation
    - Session management
    - Advanced rate limiting
    - Error recovery
    """

    def __init__(self, use_proxies: bool = False):
        self.browser_manager = BrowserManager()
        self.extractor = DataExtractor()
        self.proxy_manager = ProxyManager() if use_proxies else None
        self.session_manager = SessionManager(
            max_requests_per_session=50,
            session_lifetime_minutes=30
        )
        self.rate_limiter = RateLimiter(
            max_requests_per_hour=settings.max_requests_per_hour,
            max_requests_per_minute=20,
            base_delay_min=settings.delay_between_requests_min,
            base_delay_max=settings.delay_between_requests_max
        )

        self.request_count = 0
        self.results_scraped = 0
        self.use_proxies = use_proxies

    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Enhanced Google Maps Scraper...")

        # Initialize browser
        await self.browser_manager.initialize()

        # Initialize proxy manager if enabled
        if self.use_proxies and self.proxy_manager:
            await self.proxy_manager.initialize()
            logger.info(f"Proxy manager initialized with {len(self.proxy_manager.working_proxies)} proxies")

        # Initialize session manager
        await self.session_manager.initialize(self.browser_manager)

        logger.success("Enhanced Google Maps Scraper initialized successfully")

    async def search_and_scrape(
        self,
        search_query: str,
        location: Optional[str] = None,
        max_results: int = 100,
        job_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Search Google Maps and scrape business listings with enhanced features.

        Args:
            search_query: The search term
            location: Location to search in
            max_results: Maximum number of results
            job_id: Optional scrape job ID for tracking

        Returns:
            List of scraped business data
        """
        try:
            # Construct search query
            if location:
                full_query = f"{search_query} in {location}"
            else:
                full_query = search_query

            logger.info(f"Starting enhanced search: '{full_query}' (max results: {max_results})")

            # Create scrape job if not provided
            if not job_id:
                job = await self._create_scrape_job(full_query, max_results)
                job_id = job.id

            # Perform search with retry
            page = await self._get_page_with_retry()
            await self._perform_search_with_retry(page, full_query)

            # Wait for results
            await asyncio.sleep(3)

            # Scrape listings with enhanced features
            results = await self._scrape_listings_enhanced(page, full_query, max_results, job_id)

            # Update job status
            await self._update_job_status(job_id, 'completed', len(results))

            logger.success(f"Search completed: {len(results)} businesses scraped")

            return results

        except Exception as e:
            logger.error(f"Error during search and scrape: {e}")
            if job_id:
                await self._update_job_status(job_id, 'failed', 0, str(e))
            raise

    async def _get_page_with_retry(self) -> Page:
        """Get a page from session manager with retry logic."""
        async def get_page():
            context = await self.session_manager.get_session()
            return await context.new_page()

        return await retry_async(get_page, max_retries=3, base_delay=5.0)

    async def _perform_search_with_retry(self, page: Page, query: str):
        """Perform search with retry logic."""
        async def perform_search():
            # Apply rate limiting
            await self.rate_limiter.wait_if_needed()

            # Navigate to Google Maps
            logger.info("Navigating to Google Maps...")
            await page.goto('https://www.google.com/maps', wait_until='networkidle', timeout=60000)

            # Random delay
            await asyncio.sleep(random.uniform(2, 4))

            # Find and fill search box
            search_box = 'input#searchboxinput'
            await page.wait_for_selector(search_box, timeout=15000)
            await page.fill(search_box, query)
            await asyncio.sleep(0.5)

            # Submit search
            search_button = 'button#searchbox-searchbutton'
            try:
                await page.click(search_button)
            except:
                await page.press(search_box, 'Enter')

            # Wait for results
            await asyncio.sleep(3)
            results_selector = 'div[role="feed"]'
            await page.wait_for_selector(results_selector, timeout=20000)

            logger.success("Search results loaded")
            self.rate_limiter.record_success()

        import random
        try:
            await retry_async(perform_search, max_retries=3, base_delay=10.0)
        except Exception as e:
            self.rate_limiter.record_error()
            raise

    async def _scrape_listings_enhanced(
        self,
        page: Page,
        search_query: str,
        max_results: int,
        job_id: int
    ) -> List[Dict]:
        """Scrape listings with enhanced error handling and rate limiting."""
        results = []
        scraped_urls = set()
        consecutive_failures = 0
        max_consecutive_failures = 5

        try:
            # Scroll to load more results
            await self._scroll_results_panel(page, max_results)

            # Get listing links
            listing_links = await self._get_listing_links(page)
            logger.info(f"Found {len(listing_links)} listings")

            for i, link_data in enumerate(listing_links[:max_results]):
                try:
                    # Check rate limiter health
                    if not self.rate_limiter.is_healthy():
                        logger.warning("Rate limiter unhealthy, entering recovery mode")
                        await self.rate_limiter.enter_cooldown()

                    # Skip if already scraped
                    if link_data['url'] in scraped_urls:
                        continue

                    logger.info(f"Scraping {i + 1}/{min(len(listing_links), max_results)}: {link_data['name']}")

                    # Apply rate limiting
                    await self.rate_limiter.wait_if_needed()

                    # Scrape single listing with retry
                    business_data = await self._scrape_single_listing(
                        page,
                        link_data,
                        search_query
                    )

                    if business_data:
                        # Save to database
                        saved = await self._save_to_database(business_data)
                        if saved:
                            results.append(business_data)
                            scraped_urls.add(link_data['url'])
                            self.results_scraped += 1
                            consecutive_failures = 0  # Reset on success

                            # Update job progress
                            await self._update_job_progress(job_id, len(results))

                        self.rate_limiter.record_success()
                    else:
                        consecutive_failures += 1

                    # Batch delay
                    if (i + 1) % 10 == 0:
                        await self.rate_limiter.wait_after_batch(10)

                    # Check if too many consecutive failures
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(f"Too many consecutive failures ({consecutive_failures}), stopping")
                        break

                except Exception as e:
                    logger.error(f"Error scraping listing {i + 1}: {e}")
                    self.rate_limiter.record_error(trigger_cooldown=False)
                    consecutive_failures += 1

                    # Try to recover
                    recovered = await error_recovery.handle_error(e, {'listing': link_data})
                    if not recovered:
                        logger.warning("Recovery failed, continuing to next listing")

                    continue

        except Exception as e:
            logger.error(f"Fatal error during listing scrape: {e}")
            self.rate_limiter.record_error()

        return results

    async def _scrape_single_listing(
        self,
        page: Page,
        link_data: Dict,
        search_query: str
    ) -> Optional[Dict]:
        """Scrape a single listing with retry logic."""
        async def scrape():
            # Click listing
            await self._click_listing(page, link_data)
            await asyncio.sleep(2)

            # Extract data
            business_data = await self.extractor.extract_business_data(page, search_query)

            if not business_data:
                raise Exception("Failed to extract business data")

            return business_data

        try:
            return await retry_async(scrape, max_retries=2, base_delay=3.0)
        except Exception as e:
            logger.error(f"Failed to scrape listing after retries: {e}")
            return None

    async def _scroll_results_panel(self, page: Page, target_count: int):
        """Scroll results panel to load more listings."""
        try:
            results_panel = 'div[role="feed"]'
            scroll_attempts = min(target_count // 20 + 1, 10)

            for i in range(scroll_attempts):
                await page.evaluate(f'''
                    const feed = document.querySelector('{results_panel}');
                    if (feed) {{
                        feed.scrollTop = feed.scrollHeight;
                    }}
                ''')

                await asyncio.sleep(2)

                # Check for end of results
                try:
                    end_message = await page.query_selector('span:has-text("You\'ve reached the end")')
                    if end_message:
                        logger.info("Reached end of results")
                        break
                except:
                    pass

        except Exception as e:
            logger.debug(f"Error scrolling: {e}")

    async def _get_listing_links(self, page: Page) -> List[Dict]:
        """Get all listing links from results panel."""
        try:
            await asyncio.sleep(2)

            listing_selector = 'div[role="feed"] a[href*="/maps/place/"]'
            elements = await page.query_selector_all(listing_selector)

            links = []
            seen_urls = set()

            for element in elements:
                try:
                    href = await element.get_attribute('href')
                    aria_label = await element.get_attribute('aria-label')

                    if href and href not in seen_urls:
                        name = aria_label if aria_label else f"Business {len(links) + 1}"
                        links.append({
                            'url': href,
                            'name': name,
                            'element': element
                        })
                        seen_urls.add(href)
                except Exception as e:
                    logger.debug(f"Error extracting link: {e}")

            return links

        except Exception as e:
            logger.error(f"Error getting listing links: {e}")
            return []

    async def _click_listing(self, page: Page, link_data: Dict):
        """Click on a listing."""
        try:
            try:
                await link_data['element'].click(timeout=5000)
                await asyncio.sleep(1)
            except:
                await page.goto(link_data['url'], wait_until='domcontentloaded')
                await asyncio.sleep(2)
        except Exception as e:
            logger.debug(f"Error clicking listing: {e}")
            raise

    async def _save_to_database(self, business_data: Dict) -> bool:
        """Save business data to database."""
        try:
            with db_manager.get_session() as session:
                # Check for duplicates
                if business_data.get('place_id'):
                    existing = session.query(BusinessLead).filter_by(
                        place_id=business_data['place_id']
                    ).first()

                    if existing:
                        logger.info(f"Duplicate found: {business_data['business_name']}")
                        return False

                # Create and save
                lead = BusinessLead(**business_data)
                lead.calculate_quality_score()
                session.add(lead)
                session.commit()

                logger.success(f"Saved: {business_data['business_name']} (Quality: {lead.data_quality_score}%)")
                return True

        except Exception as e:
            logger.error(f"Database error: {e}")
            return False

    async def _create_scrape_job(self, search_query: str, max_results: int) -> ScrapeJob:
        """Create scrape job in database."""
        try:
            with db_manager.get_session() as session:
                from datetime import datetime
                job = ScrapeJob(
                    search_query=search_query,
                    max_results=max_results,
                    leads_target=max_results,
                    status='running',
                    started_at=datetime.now()
                )
                session.add(job)
                session.commit()
                session.refresh(job)

                logger.info(f"Created job: {job.id}")
                return job
        except Exception as e:
            logger.error(f"Error creating job: {e}")
            raise

    async def _update_job_progress(self, job_id: int, leads_scraped: int):
        """Update job progress."""
        try:
            with db_manager.get_session() as session:
                job = session.query(ScrapeJob).filter_by(id=job_id).first()
                if job:
                    job.leads_scraped = leads_scraped
                    session.commit()
        except Exception as e:
            logger.debug(f"Error updating progress: {e}")

    async def _update_job_status(
        self,
        job_id: int,
        status: str,
        leads_scraped: int,
        error: Optional[str] = None
    ):
        """Update job status."""
        try:
            with db_manager.get_session() as session:
                from datetime import datetime
                job = session.query(ScrapeJob).filter_by(id=job_id).first()
                if job:
                    job.status = status
                    job.leads_scraped = leads_scraped

                    if status == 'completed':
                        job.completed_at = datetime.now()

                    if error:
                        job.last_error = error
                        job.error_count += 1

                    session.commit()
                    logger.info(f"Job {job_id} updated: {status}")
        except Exception as e:
            logger.error(f"Error updating job: {e}")

    async def get_stats(self) -> Dict:
        """Get scraper statistics."""
        stats = {
            'requests': self.request_count,
            'results_scraped': self.results_scraped,
            'rate_limiter': self.rate_limiter.get_stats(),
            'session_manager': self.session_manager.get_stats(),
            'error_recovery': error_recovery.get_error_stats()
        }

        if self.use_proxies and self.proxy_manager:
            stats['proxy_manager'] = self.proxy_manager.get_stats()

        return stats

    async def close(self):
        """Close all components."""
        await self.session_manager.close()
        await self.browser_manager.close()
        logger.info("Enhanced scraper closed")
