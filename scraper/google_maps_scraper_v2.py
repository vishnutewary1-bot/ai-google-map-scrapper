"""Enhanced Google Maps scraper with Windows compatibility (sync Playwright with thread pool)."""
from typing import List, Dict, Optional
import asyncio
import random
import time
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from scraper.browser_manager import BrowserManager
from scraper.extractor import DataExtractor
from scraper.proxy_manager import ProxyManager
from scraper.session_manager import SessionManager
from scraper.rate_limiter import RateLimiter
from scraper.error_handler import retry_async, error_recovery, FatalError
from scraper.website_enricher import WebsiteEnricher
from database import db_manager, BusinessLead, ScrapeJob
from config.settings import settings

# Thread pool for sync operations
_executor = ThreadPoolExecutor(max_workers=2)


class EnhancedGoogleMapsScraper:
    """
    Enhanced Google Maps scraper with:
    - Windows compatibility (sync Playwright)
    - Proxy rotation
    - Session management
    - Advanced rate limiting
    - Error recovery
    """

    def __init__(self, use_proxies: bool = False, extract_emails: bool = False):
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
        self.website_enricher = WebsiteEnricher() if extract_emails else None

        self.request_count = 0
        self.results_scraped = 0
        self.use_proxies = use_proxies
        self.extract_emails = extract_emails
        self.page = None

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

        # Log email extraction status
        if self.extract_emails:
            logger.info("Email extraction enabled - will enrich leads from websites")

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
        """
        try:
            # Construct search query
            if location:
                full_query = f"{search_query} in {location}"
            else:
                full_query = search_query

            logger.info(f"Starting enhanced search: '{full_query}' (max results: {max_results})")

            # Update job to running status
            if job_id:
                self._update_job_status_sync(job_id, 'running', 0)

            # Get page and perform search
            self.page = await self.browser_manager.new_page()
            await self._perform_search(full_query)

            # Wait for results
            await asyncio.sleep(3)

            # Scrape listings
            results = await self._scrape_listings(full_query, max_results, job_id)

            # Update job status
            self._update_job_status_sync(job_id, 'completed', len(results))

            logger.success(f"Search completed: {len(results)} businesses scraped")

            return results

        except Exception as e:
            logger.error(f"Error during search and scrape: {e}")
            if job_id:
                self._update_job_status_sync(job_id, 'failed', 0, str(e))
            raise

    def _perform_search_sync(self, query: str):
        """Perform search synchronously."""
        try:
            logger.info("Navigating to Google Maps...")
            self.page.goto('https://www.google.com/maps', wait_until='networkidle', timeout=60000)

            # Random delay
            time.sleep(random.uniform(2, 4))

            # Find and fill search box
            search_box = 'input#searchboxinput'
            self.page.wait_for_selector(search_box, timeout=15000)
            self.page.fill(search_box, query)
            time.sleep(0.5)

            # Submit search
            search_button = 'button#searchbox-searchbutton'
            try:
                self.page.click(search_button)
            except:
                self.page.press(search_box, 'Enter')

            # Wait for results
            time.sleep(3)
            results_selector = 'div[role="feed"]'
            self.page.wait_for_selector(results_selector, timeout=20000)

            logger.success("Search results loaded")
            self.rate_limiter.record_success()

        except Exception as e:
            logger.error(f"Search failed: {e}")
            self.rate_limiter.record_error()
            raise

    async def _perform_search(self, query: str):
        """Perform search (async wrapper)."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._perform_search_sync, query)

    def _scroll_results_sync(self, target_count: int):
        """Scroll results panel synchronously."""
        try:
            results_panel = 'div[role="feed"]'
            scroll_attempts = min(target_count // 20 + 1, 10)

            for i in range(scroll_attempts):
                self.page.evaluate(f'''
                    const feed = document.querySelector('{results_panel}');
                    if (feed) {{
                        feed.scrollTop = feed.scrollHeight;
                    }}
                ''')

                time.sleep(2)

                # Check for end of results
                try:
                    end_message = self.page.query_selector('span:has-text("You\'ve reached the end")')
                    if end_message:
                        logger.info("Reached end of results")
                        break
                except:
                    pass

        except Exception as e:
            logger.debug(f"Error scrolling: {e}")

    def _get_listings_sync(self) -> List[Dict]:
        """Get listing links synchronously."""
        try:
            time.sleep(2)

            listing_selector = 'div[role="feed"] a[href*="/maps/place/"]'
            elements = self.page.query_selector_all(listing_selector)

            links = []
            seen_urls = set()

            for element in elements:
                try:
                    href = element.get_attribute('href')
                    aria_label = element.get_attribute('aria-label')

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

    def _click_listing_sync(self, link_data: Dict):
        """Click on a listing synchronously."""
        try:
            try:
                link_data['element'].click(timeout=5000)
                time.sleep(1)
            except:
                self.page.goto(link_data['url'], wait_until='domcontentloaded')
                time.sleep(2)
        except Exception as e:
            logger.debug(f"Error clicking listing: {e}")
            raise

    def _extract_business_data_sync(self, search_query: str) -> Optional[Dict]:
        """Extract business data synchronously."""
        try:
            return self.extractor.extract_business_data_sync(self.page, search_query)
        except Exception as e:
            logger.error(f"Error extracting data: {e}")
            return None

    async def _scrape_listings(
        self,
        search_query: str,
        max_results: int,
        job_id: int
    ) -> List[Dict]:
        """Scrape listings."""
        results = []
        scraped_urls = set()
        consecutive_failures = 0
        max_consecutive_failures = 5

        try:
            # Scroll to load more results
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(_executor, self._scroll_results_sync, max_results)

            # Get listing links
            listing_links = await loop.run_in_executor(_executor, self._get_listings_sync)
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

                    # Click listing
                    await loop.run_in_executor(_executor, self._click_listing_sync, link_data)
                    await asyncio.sleep(2)

                    # Extract data
                    business_data = await loop.run_in_executor(
                        _executor,
                        self._extract_business_data_sync,
                        search_query
                    )

                    if business_data:
                        # Save to database
                        saved = self._save_to_database_sync(business_data)
                        if saved:
                            results.append(business_data)
                            scraped_urls.add(link_data['url'])
                            self.results_scraped += 1
                            consecutive_failures = 0

                            # Update job progress
                            if job_id:
                                self._update_job_progress_sync(job_id, len(results))

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
                    continue

        except Exception as e:
            logger.error(f"Fatal error during listing scrape: {e}")
            self.rate_limiter.record_error()

        return results

    def _save_to_database_sync(self, business_data: Dict) -> bool:
        """Save business data to database."""
        try:
            # Enrich with website data if enabled
            if self.extract_emails and self.website_enricher and business_data.get('website'):
                try:
                    logger.info(f"Enriching from website: {business_data['website']}")
                    enrichment = self.website_enricher.enrich_from_website_sync(business_data['website'])

                    if enrichment.get('email') and not business_data.get('email'):
                        business_data['email'] = enrichment['email']
                    if enrichment.get('social_facebook') and not business_data.get('social_facebook'):
                        business_data['social_facebook'] = enrichment['social_facebook']
                    if enrichment.get('social_instagram') and not business_data.get('social_instagram'):
                        business_data['social_instagram'] = enrichment['social_instagram']
                    if enrichment.get('social_twitter') and not business_data.get('social_twitter'):
                        business_data['social_twitter'] = enrichment['social_twitter']
                    if enrichment.get('social_linkedin') and not business_data.get('social_linkedin'):
                        business_data['social_linkedin'] = enrichment['social_linkedin']

                except Exception as e:
                    logger.warning(f"Website enrichment failed: {e}")

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

    def _update_job_progress_sync(self, job_id: int, leads_scraped: int):
        """Update job progress."""
        try:
            with db_manager.get_session() as session:
                job = session.query(ScrapeJob).filter_by(id=job_id).first()
                if job:
                    job.leads_scraped = leads_scraped
                    session.commit()
        except Exception as e:
            logger.debug(f"Error updating progress: {e}")

    def _update_job_status_sync(
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
