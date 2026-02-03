"""Browser automation engine with anti-detection for Google Maps scraping."""

import random
import time
import asyncio
import re
from typing import Dict, List, Optional, Tuple
from loguru import logger

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
except ImportError:
    sync_playwright = None
    Browser = None
    BrowserContext = None
    Page = None

# Import proxy manager
try:
    from scraper.proxy_manager import proxy_manager
    HAS_PROXY_MANAGER = True
except ImportError:
    HAS_PROXY_MANAGER = False
    proxy_manager = None

# Import captcha solver
try:
    from scraper.captcha_solver import get_captcha_solver, CaptchaSolver
    HAS_CAPTCHA_SOLVER = True
except ImportError:
    HAS_CAPTCHA_SOLVER = False
    get_captcha_solver = None
    CaptchaSolver = None


class BrowserEngine:
    """Playwright browser with anti-detection for Google Maps scraping."""

    # Random viewport sizes to avoid fingerprinting
    VIEWPORT_SIZES = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1536, "height": 864},
        {"width": 1440, "height": 900},
        {"width": 1280, "height": 720},
        {"width": 1600, "height": 900},
        {"width": 1280, "height": 800},
        {"width": 1024, "height": 768},
        {"width": 1920, "height": 1200},
        {"width": 2560, "height": 1440},
    ]

    # Random user agents
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    ]

    # Google Maps URL
    MAPS_URL = "https://www.google.com/maps"

    def __init__(
        self,
        headless: bool = True,
        use_proxies: bool = False,
        proxy_list: Optional[List[str]] = None,
        use_proxy_manager: bool = False,
        captcha_enabled: bool = False,
        captcha_api_key: Optional[str] = None,
        slow_mo: int = 50,
        geolocation: Optional[Dict] = None
    ):
        """
        Initialize the browser engine.

        Args:
            headless: Run browser in headless mode
            use_proxies: Enable proxy rotation
            proxy_list: List of proxy URLs (format: http://user:pass@host:port)
            use_proxy_manager: Use the integrated ProxyManager for auto proxy rotation
            captcha_enabled: Enable CAPTCHA solving
            captcha_api_key: 2Captcha API key
            slow_mo: Slow down operations by this many ms
            geolocation: Custom geolocation {latitude, longitude}
        """
        self.headless = headless
        self.use_proxies = use_proxies
        self.proxy_list = proxy_list or []
        self.use_proxy_manager = use_proxy_manager
        self.captcha_enabled = captcha_enabled
        self.slow_mo = slow_mo
        self.geolocation = geolocation or {"latitude": 40.7128, "longitude": -74.0060}

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._current_proxy: Optional[Dict] = None
        self._captcha_solver: Optional[CaptchaSolver] = None

        # Initialize CAPTCHA solver if enabled
        if captcha_enabled and captcha_api_key and HAS_CAPTCHA_SOLVER:
            self._captcha_solver = get_captcha_solver(captcha_api_key)
            logger.info("CAPTCHA solver initialized")

        self._fingerprint = self._get_random_fingerprint()

    def _get_random_fingerprint(self) -> Dict:
        """Generate a random browser fingerprint."""
        return {
            "viewport": random.choice(self.VIEWPORT_SIZES),
            "user_agent": random.choice(self.USER_AGENTS),
            "locale": random.choice(["en-US", "en-GB", "en-AU", "en-CA"]),
            "timezone": random.choice([
                "America/New_York",
                "America/Los_Angeles",
                "America/Chicago",
                "Europe/London",
                "Asia/Tokyo",
            ]),
        }

    async def _init_proxy_manager(self):
        """Initialize proxy manager with working proxies."""
        if self.use_proxy_manager and HAS_PROXY_MANAGER and proxy_manager:
            await proxy_manager.initialize()
            self.proxy_list = [p['url'] for p in proxy_manager.working_proxies]
            logger.info(f"Loaded {len(self.proxy_list)} working proxies from ProxyManager")

    def launch(self) -> Page:
        """Launch browser with anti-detection measures."""
        if sync_playwright is None:
            raise RuntimeError("Playwright is not installed. Run: pip install playwright && playwright install")

        # Initialize proxy manager if enabled
        if self.use_proxy_manager and HAS_PROXY_MANAGER:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._init_proxy_manager())
                loop.close()
            except Exception as e:
                logger.warning(f"Failed to initialize proxy manager: {e}")

        self._playwright = sync_playwright().start()

        # Browser launch arguments for anti-detection
        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certificate-errors",
            "--ignore-certificate-errors-spki-list",
            f"--window-size={self._fingerprint['viewport']['width']},{self._fingerprint['viewport']['height']}",
        ]

        # Configure proxy if enabled
        proxy_config = None
        if self.use_proxies and self.proxy_list:
            if self.use_proxy_manager and HAS_PROXY_MANAGER and proxy_manager:
                # Get next proxy from rotation
                proxy = proxy_manager.get_next_proxy()
                if proxy:
                    proxy_config = {"server": proxy['url']}
                    self._current_proxy = proxy
                    logger.info(f"Using proxy from manager: {proxy['ip']}")
            else:
                proxy_url = random.choice(self.proxy_list)
                proxy_config = {"server": proxy_url}
                logger.info(f"Using proxy: {proxy_url.split('@')[-1] if '@' in proxy_url else proxy_url}")

        # Launch browser
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=browser_args,
            slow_mo=self.slow_mo,
            proxy=proxy_config,
        )

        # Create context with fingerprint
        self._context = self._browser.new_context(
            viewport=self._fingerprint["viewport"],
            user_agent=self._fingerprint["user_agent"],
            locale=self._fingerprint["locale"],
            timezone_id=self._fingerprint["timezone"],
            geolocation=self.geolocation,
            permissions=["geolocation"],
            java_script_enabled=True,
            ignore_https_errors=True,
        )

        # Create page and inject anti-detection scripts
        self._page = self._context.new_page()
        self._inject_anti_detection_scripts()

        logger.info(f"Browser launched with viewport {self._fingerprint['viewport']}")
        return self._page

    def _inject_anti_detection_scripts(self):
        """Inject scripts to evade bot detection."""
        if not self._page:
            return

        # Remove webdriver property
        self._page.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // Add chrome runtime
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {},
            };

            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Add plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: {type: "application/pdf", suffixes: "pdf", description: "PDF Viewer"},
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    },
                    {
                        0: {type: "application/pdf", suffixes: "pdf", description: "PDF Viewer"},
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Viewer"
                    },
                ],
            });

            // Add languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });

            // Fix hardware concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,
            });

            // Override headless detection
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32',
            });
        """)

    def mark_current_proxy_failed(self):
        """Mark current proxy as failed for rotation."""
        if self.use_proxy_manager and HAS_PROXY_MANAGER and proxy_manager and self._current_proxy:
            proxy_manager.mark_proxy_failed(self._current_proxy)
            logger.warning(f"Marked proxy as failed: {self._current_proxy.get('ip', 'unknown')}")

    def detect_captcha(self) -> Dict:
        """Detect if a CAPTCHA is present on the page."""
        result = {"detected": False, "type": None, "sitekey": None}

        if not self._page:
            return result

        try:
            # Check for reCAPTCHA v2
            recaptcha = self._page.query_selector('div.g-recaptcha')
            if recaptcha:
                result["detected"] = True
                result["type"] = "recaptcha_v2"
                result["sitekey"] = recaptcha.get_attribute('data-sitekey')
                logger.warning("reCAPTCHA v2 detected!")
                return result

            # Check for Google unusual traffic page
            unusual = self._page.query_selector('div#recaptcha')
            if unusual:
                result["detected"] = True
                result["type"] = "google_unusual_traffic"
                sitekey_elem = self._page.query_selector('[data-sitekey]')
                if sitekey_elem:
                    result["sitekey"] = sitekey_elem.get_attribute('data-sitekey')
                logger.warning("Google unusual traffic CAPTCHA detected!")
                return result

            # Check for reCAPTCHA in iframe
            recaptcha_iframe = self._page.query_selector('iframe[src*="recaptcha"]')
            if recaptcha_iframe:
                result["detected"] = True
                result["type"] = "recaptcha_iframe"
                logger.warning("reCAPTCHA iframe detected!")
                return result

            # Check for hCaptcha
            hcaptcha = self._page.query_selector('div.h-captcha')
            if hcaptcha:
                result["detected"] = True
                result["type"] = "hcaptcha"
                result["sitekey"] = hcaptcha.get_attribute('data-sitekey')
                logger.warning("hCaptcha detected!")
                return result

        except Exception as e:
            logger.debug(f"Error detecting CAPTCHA: {e}")

        return result

    def handle_captcha_if_present(self) -> bool:
        """Check for and solve CAPTCHA if present. Returns True if page is usable."""
        if not self._captcha_solver or not self._captcha_solver.enabled:
            # No solver available, just detect and report
            captcha_info = self.detect_captcha()
            if captcha_info["detected"]:
                logger.warning(f"CAPTCHA detected but solver not configured: {captcha_info['type']}")
                return False
            return True

        captcha_info = self.detect_captcha()

        if not captcha_info["detected"]:
            return True

        logger.warning(f"CAPTCHA detected: {captcha_info['type']}")

        if not captcha_info.get("sitekey"):
            logger.error("Could not extract CAPTCHA sitekey")
            return False

        # Solve using 2Captcha (sync wrapper)
        try:
            solution = self._solve_captcha_sync(
                captcha_info["type"],
                captcha_info["sitekey"]
            )

            if solution:
                self._inject_captcha_solution(solution, captcha_info["type"])
                time.sleep(3)  # Wait for page to process

                # Verify CAPTCHA is gone
                new_check = self.detect_captcha()
                if not new_check["detected"]:
                    logger.success("CAPTCHA solved successfully!")
                    return True
                else:
                    logger.warning("CAPTCHA still present after solution injection")
        except Exception as e:
            logger.error(f"CAPTCHA solving failed: {e}")

        return False

    def _solve_captcha_sync(self, captcha_type: str, sitekey: str) -> Optional[str]:
        """Synchronously solve CAPTCHA using 2Captcha."""
        if not self._captcha_solver or not self._captcha_solver.solver:
            return None

        try:
            if captcha_type in ["recaptcha_v2", "google_unusual_traffic", "recaptcha_iframe"]:
                result = self._captcha_solver.solver.recaptcha(
                    sitekey=sitekey,
                    url=self._page.url
                )
                return result.get("code") if isinstance(result, dict) else result
            elif captcha_type == "hcaptcha":
                result = self._captcha_solver.solver.hcaptcha(
                    sitekey=sitekey,
                    url=self._page.url
                )
                return result.get("code") if isinstance(result, dict) else result
        except Exception as e:
            logger.error(f"2Captcha solve error: {e}")
        return None

    def _inject_captcha_solution(self, token: str, captcha_type: str):
        """Inject CAPTCHA solution into page."""
        try:
            if captcha_type in ["recaptcha_v2", "recaptcha_v3", "google_unusual_traffic", "recaptcha_iframe"]:
                self._page.evaluate('''
                    (token) => {
                        // Set the response textarea
                        const textarea = document.getElementById('g-recaptcha-response');
                        if (textarea) {
                            textarea.innerHTML = token;
                            textarea.style.display = 'block';
                        }

                        // Also try alternative locations
                        const textareas = document.querySelectorAll('[name="g-recaptcha-response"]');
                        textareas.forEach(t => {
                            t.innerHTML = token;
                            t.value = token;
                        });

                        // Trigger callback if available
                        if (typeof ___grecaptcha_cfg !== 'undefined') {
                            const clients = ___grecaptcha_cfg.clients;
                            if (clients) {
                                Object.keys(clients).forEach(key => {
                                    const client = clients[key];
                                    if (client && client.callback) {
                                        client.callback(token);
                                    }
                                });
                            }
                        }

                        // Try window callback
                        if (window.captchaCallback) {
                            window.captchaCallback(token);
                        }
                    }
                ''', token)

                # Try to find and click submit button
                submit_selectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    '#submit',
                    '.submit-button',
                ]

                for selector in submit_selectors:
                    try:
                        submit_btn = self._page.query_selector(selector)
                        if submit_btn:
                            submit_btn.click()
                            time.sleep(2)
                            break
                    except:
                        continue

            elif captcha_type == "hcaptcha":
                self._page.evaluate('''
                    (token) => {
                        const textarea = document.querySelector('[name="h-captcha-response"]');
                        if (textarea) {
                            textarea.innerHTML = token;
                            textarea.value = token;
                        }
                    }
                ''', token)

        except Exception as e:
            logger.error(f"Error injecting CAPTCHA solution: {e}")

    def navigate_to_maps(self, retries: int = 3) -> bool:
        """
        Navigate to Google Maps.

        Args:
            retries: Number of retry attempts

        Returns:
            True if navigation successful
        """
        if not self._page:
            raise RuntimeError("Browser not launched. Call launch() first.")

        for attempt in range(retries):
            try:
                # Use domcontentloaded instead of networkidle for faster navigation
                self._page.goto(self.MAPS_URL, wait_until="domcontentloaded", timeout=60000)

                # Wait for the page to be interactive
                time.sleep(2)

                # Check for CAPTCHA
                if self.captcha_enabled:
                    if not self.handle_captcha_if_present():
                        logger.warning("CAPTCHA blocking access, retrying...")
                        if self.use_proxy_manager:
                            self.mark_current_proxy_failed()
                        continue

                # Try multiple selectors for search box (Google Maps changes layouts)
                search_selectors = [
                    '#searchboxinput',
                    'input[name="q"]',
                    'input[aria-label*="Search"]',
                    'input[placeholder*="Search"]',
                    '#searchbox input',
                ]

                search_found = False
                for selector in search_selectors:
                    try:
                        self._page.wait_for_selector(selector, timeout=10000)
                        search_found = True
                        logger.info(f"Search box found with selector: {selector}")
                        break
                    except Exception:
                        continue

                if not search_found:
                    # Try waiting for any input element on the page
                    try:
                        self._page.wait_for_selector('input', timeout=5000)
                        search_found = True
                    except Exception:
                        pass

                if not search_found:
                    raise Exception("Search box not found on Google Maps")

                # Accept cookies if dialog appears (common in EU)
                try:
                    cookie_buttons = [
                        'button:has-text("Accept all")',
                        'button:has-text("Accept")',
                        'button:has-text("I agree")',
                        'button[aria-label*="Accept"]',
                    ]
                    for btn_selector in cookie_buttons:
                        accept_button = self._page.query_selector(btn_selector)
                        if accept_button:
                            accept_button.click()
                            time.sleep(1)
                            break
                except Exception:
                    pass

                logger.info("Successfully navigated to Google Maps")
                return True

            except Exception as e:
                logger.warning(f"Navigation attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(3)
                    # Refresh fingerprint on retry
                    self._fingerprint = self._get_random_fingerprint()
                    # Mark proxy as failed if using proxy manager
                    if self.use_proxy_manager:
                        self.mark_current_proxy_failed()

        return False

    def search(self, query: str, location: Optional[str] = None) -> bool:
        """
        Perform a search on Google Maps.

        Args:
            query: Search query (e.g., "restaurants", "plumbers")
            location: Optional location to append to query

        Returns:
            True if search successful
        """
        if not self._page:
            raise RuntimeError("Browser not launched. Call launch() first.")

        try:
            # Build full query
            full_query = f"{query} in {location}" if location else query

            # Try multiple selectors for search box
            search_selectors = [
                '#searchboxinput',
                'input[name="q"]',
                'input[aria-label*="Search"]',
                'input[placeholder*="Search"]',
            ]

            search_box = None
            for selector in search_selectors:
                search_box = self._page.query_selector(selector)
                if search_box:
                    break

            if not search_box:
                logger.error("Search box not found")
                return False

            # Clear and type with human-like delay
            search_box.click()
            time.sleep(0.3)
            search_box.fill("")
            time.sleep(0.3)

            # Type the query (faster but still human-like)
            search_box.type(full_query, delay=random.randint(30, 80))

            time.sleep(0.5)

            # Press Enter to search
            search_box.press("Enter")

            # Wait for results to load (use domcontentloaded for speed)
            time.sleep(2)

            # Check for CAPTCHA after search
            if self.captcha_enabled:
                self.handle_captcha_if_present()

            # Wait for results panel to appear
            try:
                self._page.wait_for_selector(
                    'div[role="feed"], div[aria-label*="Results"], div[class*="result"]',
                    timeout=15000
                )
            except Exception:
                # Even if selector not found, the page might have loaded
                pass

            # Additional wait for content to render
            time.sleep(2)

            logger.info(f"Search completed for: {full_query}")
            return True

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return False

    def search_by_coordinates(
        self,
        query: str,
        latitude: float,
        longitude: float,
        zoom: int = 15
    ) -> bool:
        """
        Search Google Maps at specific coordinates.

        Args:
            query: Search query
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            zoom: Zoom level (default 15)

        Returns:
            True if search successful
        """
        if not self._page:
            raise RuntimeError("Browser not launched. Call launch() first.")

        try:
            # Navigate directly to coordinate-based search URL
            encoded_query = query.replace(' ', '+')
            url = f"https://www.google.com/maps/search/{encoded_query}/@{latitude},{longitude},{zoom}z"

            self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            # Check for CAPTCHA
            if self.captcha_enabled:
                self.handle_captcha_if_present()

            # Wait for results
            try:
                self._page.wait_for_selector(
                    'div[role="feed"], div[aria-label*="Results"]',
                    timeout=15000
                )
            except Exception:
                pass

            time.sleep(2)

            logger.info(f"Geo search at ({latitude}, {longitude}): {query}")
            return True

        except Exception as e:
            logger.error(f"Geo search failed: {e}")
            return False

    def scroll_results(self, target_count: int, max_scrolls: int = 100, fast_mode: bool = False) -> int:
        """
        Scroll through results to load more listings.

        Args:
            target_count: Target number of results to load
            max_scrolls: Maximum scroll attempts
            fast_mode: Use faster scroll delays (less human-like but quicker)

        Returns:
            Number of listings found
        """
        if not self._page:
            raise RuntimeError("Browser not launched. Call launch() first.")

        try:
            # Find the results container
            results_container = self._page.query_selector(
                'div[role="feed"], div[aria-label*="Results"]'
            )

            if not results_container:
                logger.warning("Results container not found")
                return 0

            scroll_count = 0
            last_count = 0
            no_new_results_count = 0

            while scroll_count < max_scrolls:
                # Get current listing count
                listings = self.get_listings()
                current_count = len(listings)

                logger.debug(f"Scroll {scroll_count + 1}: Found {current_count} listings")

                if current_count >= target_count:
                    logger.info(f"Reached target count: {current_count} listings")
                    break

                # Check if we're getting new results
                if current_count == last_count:
                    no_new_results_count += 1
                    if no_new_results_count >= 5:
                        logger.info(f"No new results after 5 scrolls. Total: {current_count}")
                        break
                else:
                    no_new_results_count = 0

                last_count = current_count

                # Scroll the container
                self._page.evaluate("""
                    (container) => {
                        const feed = document.querySelector('div[role="feed"]');
                        if (feed) {
                            feed.scrollTop = feed.scrollHeight;
                        }
                    }
                """, results_container)

                # Random delay to appear human (faster in fast_mode)
                if fast_mode:
                    time.sleep(random.uniform(0.5, 1.0))
                else:
                    time.sleep(random.uniform(1.5, 3.0))

                # Every N results, take a longer break
                break_interval = 25 if fast_mode else 10
                if current_count > 0 and current_count % break_interval == 0:
                    if fast_mode:
                        time.sleep(random.uniform(1.0, 2.0))
                    else:
                        time.sleep(random.uniform(2.0, 4.0))

                scroll_count += 1

            return len(self.get_listings())

        except Exception as e:
            logger.error(f"Error scrolling results: {e}")
            return 0

    def get_listings(self) -> List[Dict]:
        """
        Get all visible business listings.

        Returns:
            List of listing dictionaries with basic info
        """
        if not self._page:
            return []

        try:
            # Multiple selectors for different Maps layouts
            listing_selectors = [
                'div[role="feed"] > div > div[jsaction]',
                'div[role="feed"] a[href*="/maps/place/"]',
                'a[href*="/maps/place/"]',
            ]

            listings = []
            seen_urls = set()

            for selector in listing_selectors:
                elements = self._page.query_selector_all(selector)

                for element in elements:
                    try:
                        # Get the link (either the element itself or a child link)
                        link = element if element.get_attribute("href") else element.query_selector('a[href*="/maps/place/"]')

                        if not link:
                            continue

                        href = link.get_attribute("href")
                        if not href or href in seen_urls:
                            continue

                        seen_urls.add(href)

                        # Extract basic info from the listing
                        listing = {
                            "url": href,
                            "element": element,
                        }

                        # Try to get name from aria-label or text
                        aria_label = element.get_attribute("aria-label")
                        if aria_label:
                            listing["name"] = aria_label.split("·")[0].strip()
                        else:
                            text_element = element.query_selector('div[class*="fontHeadlineSmall"]')
                            if text_element:
                                listing["name"] = text_element.inner_text().strip()

                        listings.append(listing)

                    except Exception:
                        continue

                if listings:
                    break

            return listings

        except Exception as e:
            logger.error(f"Error getting listings: {e}")
            return []

    def click_listing(self, listing: Dict) -> bool:
        """
        Click on a listing to open its details.

        Args:
            listing: Listing dictionary from get_listings()

        Returns:
            True if click successful
        """
        if not self._page:
            return False

        try:
            # First try: Navigate directly to URL (most reliable)
            url = listing.get("url")
            if url:
                try:
                    logger.debug(f"Navigating to listing URL: {url[:80]}...")
                    self._page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(2)

                    # Verify we're on a place detail page
                    if "/maps/place/" in self._page.url:
                        logger.debug("Successfully navigated to listing details")
                        return True
                except Exception as nav_err:
                    logger.debug(f"URL navigation failed: {nav_err}")

            # Second try: Click the element directly
            element = listing.get("element")
            if element:
                try:
                    logger.debug("Attempting direct element click")
                    element.click()
                    time.sleep(random.uniform(2.5, 4.0))

                    # Just wait a moment for content to load
                    return True

                except Exception as click_err:
                    logger.debug(f"Direct click failed: {click_err}")

            return False

        except Exception as e:
            logger.error(f"Error clicking listing: {e}")
            return False

    def go_back_to_results(self) -> bool:
        """Go back to the search results from a listing detail page."""
        if not self._page:
            return False

        try:
            # Click back button if available
            back_button = self._page.query_selector('button[aria-label="Back"], button[jsaction*="back"]')
            if back_button:
                back_button.click()
                time.sleep(1.5)
                return True

            # Fallback: use browser back
            self._page.go_back()
            time.sleep(1.5)
            return True

        except Exception as e:
            logger.error(f"Error going back: {e}")
            return False

    def get_page(self) -> Optional[Page]:
        """Get the current page object."""
        return self._page

    def get_current_url(self) -> str:
        """Get the current page URL."""
        return self._page.url if self._page else ""

    def take_screenshot(self, path: str) -> bool:
        """Take a screenshot of the current page."""
        if not self._page:
            return False

        try:
            self._page.screenshot(path=path)
            return True
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return False

    def random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Add a random delay to appear more human-like."""
        time.sleep(random.uniform(min_sec, max_sec))

    def get_proxy_stats(self) -> Dict:
        """Get proxy manager statistics."""
        if HAS_PROXY_MANAGER and proxy_manager:
            return proxy_manager.get_stats()
        return {"message": "Proxy manager not available"}

    def get_captcha_stats(self) -> Dict:
        """Get CAPTCHA solver statistics."""
        if self._captcha_solver:
            return self._captcha_solver.get_stats()
        return {"message": "CAPTCHA solver not configured"}

    def close(self):
        """Close the browser and cleanup resources."""
        try:
            if self._page:
                self._page.close()
                self._page = None

            if self._context:
                self._context.close()
                self._context = None

            if self._browser:
                self._browser.close()
                self._browser = None

            if self._playwright:
                self._playwright.stop()
                self._playwright = None

            logger.info("Browser closed successfully")

        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    def __enter__(self):
        """Context manager entry."""
        self.launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
