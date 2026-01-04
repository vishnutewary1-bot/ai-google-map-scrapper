"""Browser management for Playwright automation - Windows compatible version."""
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from typing import Optional
import random
import asyncio
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from config.settings import settings

# Thread pool for running sync Playwright in async context
_executor = ThreadPoolExecutor(max_workers=3)


class BrowserManager:
    """Manages Playwright browser instances with anti-detection features.

    Uses sync Playwright API with thread pool for Windows compatibility.
    """

    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._initialized = False

    def _init_sync(self):
        """Initialize Playwright synchronously (runs in thread pool)."""
        try:
            self.playwright = sync_playwright().start()
            logger.info("Playwright initialized successfully")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise

    async def initialize(self):
        """Initialize Playwright and browser (async wrapper)."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._init_sync)

    def _launch_browser_sync(self):
        """Launch browser synchronously (runs in thread pool)."""
        try:
            # Random viewport sizes (common resolutions)
            viewports = [
                {"width": 1920, "height": 1080},
                {"width": 1366, "height": 768},
                {"width": 1536, "height": 864},
                {"width": 1440, "height": 900},
            ]
            viewport = random.choice(viewports)

            # User agents (real Chrome user agents)
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ]
            user_agent = random.choice(user_agents)

            # Launch browser
            self.browser = self.playwright.chromium.launch(
                headless=settings.headless_mode,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            )

            # Create context with randomized fingerprint
            self.context = self.browser.new_context(
                viewport=viewport,
                user_agent=user_agent,
                locale='en-US',
                timezone_id='Asia/Kolkata',
                permissions=['geolocation'],
                geolocation={'latitude': 19.0760, 'longitude': 72.8777},  # Mumbai
            )

            # Add init script to prevent detection
            self.context.add_init_script("""
                // Override navigator.webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Override chrome object
                window.chrome = {
                    runtime: {}
                };

                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

            logger.info(f"Browser launched successfully (viewport: {viewport['width']}x{viewport['height']})")
            return self.context

        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            raise

    async def launch_browser(self):
        """Launch browser with anti-detection settings (async wrapper)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._launch_browser_sync)

    def _new_page_sync(self) -> Page:
        """Create a new page synchronously."""
        if not self.context:
            self._launch_browser_sync()

        page = self.context.new_page()
        page.set_default_timeout(settings.browser_timeout)
        return page

    async def new_page(self) -> Page:
        """Create a new page in the browser context (async wrapper)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._new_page_sync)

    def _close_sync(self):
        """Close browser synchronously."""
        try:
            if self.context:
                self.context.close()
                self.context = None
            if self.browser:
                self.browser.close()
                self.browser = None
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    async def close(self):
        """Close browser and cleanup resources (async wrapper)."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._close_sync)

    async def random_delay(self, min_seconds: Optional[int] = None, max_seconds: Optional[int] = None):
        """Add random delay to mimic human behavior."""
        min_sec = min_seconds or settings.delay_between_requests_min
        max_sec = max_seconds or settings.delay_between_requests_max
        delay = random.uniform(min_sec, max_sec)

        logger.debug(f"Waiting {delay:.2f} seconds...")
        await asyncio.sleep(delay)

    def _human_scroll_sync(self, page: Page):
        """Scroll the page synchronously."""
        try:
            scroll_distance = random.randint(300, 800)
            page.evaluate(f"""
                window.scrollBy({{
                    top: {scroll_distance},
                    left: 0,
                    behavior: 'smooth'
                }});
            """)
            import time
            time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            logger.debug(f"Scroll error (non-critical): {e}")

    async def human_like_scroll(self, page: Page):
        """Scroll the page in a human-like manner (async wrapper)."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._human_scroll_sync, page)

    def _human_click_sync(self, page: Page, selector: str, timeout: int = 30000):
        """Click element synchronously."""
        try:
            element = page.wait_for_selector(selector, timeout=timeout)

            box = element.bounding_box()

            if box:
                x = box['x'] + random.uniform(5, box['width'] - 5)
                y = box['y'] + random.uniform(5, box['height'] - 5)

                page.mouse.move(x, y)
                import time
                time.sleep(random.uniform(0.1, 0.3))
                page.mouse.click(x, y)
            else:
                element.click()

        except Exception as e:
            logger.debug(f"Click error: {e}")
            raise

    async def human_like_click(self, page: Page, selector: str, timeout: int = 30000):
        """Click element with human-like behavior (async wrapper)."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._human_click_sync, page, selector, timeout)
