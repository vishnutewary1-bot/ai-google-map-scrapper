"""Browser management for Playwright automation."""
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from typing import Optional
import random
from loguru import logger
from config.settings import settings


class BrowserManager:
    """Manages Playwright browser instances with anti-detection features."""

    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def initialize(self):
        """Initialize Playwright and browser."""
        try:
            self.playwright = await async_playwright().start()
            logger.info("Playwright initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise

    async def launch_browser(self):
        """Launch browser with anti-detection settings."""
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
            self.browser = await self.playwright.chromium.launch(
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
            self.context = await self.browser.new_context(
                viewport=viewport,
                user_agent=user_agent,
                locale='en-US',
                timezone_id='Asia/Kolkata',
                permissions=['geolocation'],
                geolocation={'latitude': 19.0760, 'longitude': 72.8777},  # Mumbai
            )

            # Add init script to prevent detection
            await self.context.add_init_script("""
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

    async def new_page(self) -> Page:
        """Create a new page in the browser context."""
        if not self.context:
            await self.launch_browser()

        page = await self.context.new_page()

        # Set default timeout
        page.set_default_timeout(settings.browser_timeout)

        return page

    async def close(self):
        """Close browser and cleanup resources."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    async def random_delay(self, min_seconds: Optional[int] = None, max_seconds: Optional[int] = None):
        """Add random delay to mimic human behavior."""
        import asyncio

        min_sec = min_seconds or settings.delay_between_requests_min
        max_sec = max_seconds or settings.delay_between_requests_max
        delay = random.uniform(min_sec, max_sec)

        logger.debug(f"Waiting {delay:.2f} seconds...")
        await asyncio.sleep(delay)

    async def human_like_scroll(self, page: Page):
        """Scroll the page in a human-like manner."""
        try:
            # Random scroll distance
            scroll_distance = random.randint(300, 800)

            # Scroll with random speed
            await page.evaluate(f"""
                window.scrollBy({{
                    top: {scroll_distance},
                    left: 0,
                    behavior: 'smooth'
                }});
            """)

            # Small random delay after scroll
            import asyncio
            await asyncio.sleep(random.uniform(0.5, 1.5))

        except Exception as e:
            logger.debug(f"Scroll error (non-critical): {e}")

    async def human_like_click(self, page: Page, selector: str, timeout: int = 30000):
        """Click element with human-like behavior."""
        try:
            element = await page.wait_for_selector(selector, timeout=timeout)

            # Get element bounding box
            box = await element.bounding_box()

            if box:
                # Random offset within element
                x = box['x'] + random.uniform(5, box['width'] - 5)
                y = box['y'] + random.uniform(5, box['height'] - 5)

                # Move mouse and click
                await page.mouse.move(x, y)
                import asyncio
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await page.mouse.click(x, y)
            else:
                await element.click()

        except Exception as e:
            logger.debug(f"Click error: {e}")
            raise
