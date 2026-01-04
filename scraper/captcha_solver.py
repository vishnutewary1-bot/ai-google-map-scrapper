"""CAPTCHA solving integration for Google Maps scraper."""
import asyncio
import time
from typing import Optional, Dict
from loguru import logger

try:
    from twocaptcha import TwoCaptcha
    TWOCAPTCHA_AVAILABLE = True
except ImportError:
    TWOCAPTCHA_AVAILABLE = False

try:
    from playwright.async_api import Page
except ImportError:
    Page = None


class CaptchaSolver:
    """
    CAPTCHA solving service integration.
    Supports 2Captcha for reCAPTCHA v2/v3 solving.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize CAPTCHA solver.

        Args:
            api_key: 2Captcha API key
        """
        self.api_key = api_key
        self.solver = None
        self.enabled = False
        self.stats = {
            "captchas_detected": 0,
            "captchas_solved": 0,
            "captchas_failed": 0,
            "total_cost": 0.0
        }

        if api_key and TWOCAPTCHA_AVAILABLE:
            self.solver = TwoCaptcha(api_key)
            self.enabled = True
            logger.info("CAPTCHA solver initialized with 2Captcha")
        elif not TWOCAPTCHA_AVAILABLE:
            logger.warning("2captcha-python not installed. CAPTCHA solving disabled.")
        else:
            logger.info("No CAPTCHA API key provided. CAPTCHA solving disabled.")

    async def detect_captcha(self, page: Page) -> Dict:
        """
        Detect if a CAPTCHA is present on the page.

        Args:
            page: Playwright page object

        Returns:
            Dict with detection results
        """
        result = {
            "detected": False,
            "type": None,
            "sitekey": None,
            "data_s": None
        }

        try:
            # Check for reCAPTCHA v2
            recaptcha_v2 = await page.query_selector('div.g-recaptcha')
            if recaptcha_v2:
                result["detected"] = True
                result["type"] = "recaptcha_v2"
                result["sitekey"] = await recaptcha_v2.get_attribute('data-sitekey')
                self.stats["captchas_detected"] += 1
                logger.warning("reCAPTCHA v2 detected!")
                return result

            # Check for reCAPTCHA v3 (invisible)
            recaptcha_v3 = await page.query_selector('script[src*="recaptcha/api.js"]')
            if recaptcha_v3:
                # Try to extract sitekey from page
                sitekey = await page.evaluate('''
                    () => {
                        const scripts = document.querySelectorAll('script');
                        for (const script of scripts) {
                            const match = script.innerHTML.match(/sitekey['"\\s:]+(['"](\\w+)['""])/);
                            if (match) return match[2];
                        }
                        return null;
                    }
                ''')
                if sitekey:
                    result["detected"] = True
                    result["type"] = "recaptcha_v3"
                    result["sitekey"] = sitekey
                    self.stats["captchas_detected"] += 1
                    logger.warning("reCAPTCHA v3 detected!")
                    return result

            # Check for hCaptcha
            hcaptcha = await page.query_selector('div.h-captcha')
            if hcaptcha:
                result["detected"] = True
                result["type"] = "hcaptcha"
                result["sitekey"] = await hcaptcha.get_attribute('data-sitekey')
                self.stats["captchas_detected"] += 1
                logger.warning("hCaptcha detected!")
                return result

            # Check for Google consent/unusual traffic page
            unusual_traffic = await page.query_selector('div#recaptcha')
            if unusual_traffic:
                result["detected"] = True
                result["type"] = "google_unusual_traffic"
                # Try to get sitekey
                sitekey_elem = await page.query_selector('[data-sitekey]')
                if sitekey_elem:
                    result["sitekey"] = await sitekey_elem.get_attribute('data-sitekey')
                self.stats["captchas_detected"] += 1
                logger.warning("Google unusual traffic CAPTCHA detected!")
                return result

        except Exception as e:
            logger.error(f"Error detecting CAPTCHA: {e}")

        return result

    async def solve_captcha(
        self,
        page: Page,
        captcha_info: Optional[Dict] = None,
        timeout: int = 120
    ) -> bool:
        """
        Solve a CAPTCHA on the page.

        Args:
            page: Playwright page object
            captcha_info: CAPTCHA detection info (if None, will detect)
            timeout: Maximum time to wait for solution

        Returns:
            True if CAPTCHA was solved successfully
        """
        if not self.enabled:
            logger.warning("CAPTCHA solving is disabled. Enable by providing API key.")
            return False

        try:
            # Detect CAPTCHA if not provided
            if captcha_info is None:
                captcha_info = await self.detect_captcha(page)

            if not captcha_info.get("detected"):
                logger.info("No CAPTCHA detected")
                return True

            captcha_type = captcha_info.get("type")
            sitekey = captcha_info.get("sitekey")
            page_url = page.url

            if not sitekey:
                logger.error("Could not extract CAPTCHA sitekey")
                self.stats["captchas_failed"] += 1
                return False

            logger.info(f"Solving {captcha_type} CAPTCHA...")

            # Solve based on type
            if captcha_type in ["recaptcha_v2", "google_unusual_traffic"]:
                result = await self._solve_recaptcha_v2(sitekey, page_url, timeout)
            elif captcha_type == "recaptcha_v3":
                result = await self._solve_recaptcha_v3(sitekey, page_url, timeout)
            elif captcha_type == "hcaptcha":
                result = await self._solve_hcaptcha(sitekey, page_url, timeout)
            else:
                logger.error(f"Unsupported CAPTCHA type: {captcha_type}")
                self.stats["captchas_failed"] += 1
                return False

            if result and result.get("code"):
                # Inject the solution
                injected = await self._inject_solution(page, result["code"], captcha_type)

                if injected:
                    self.stats["captchas_solved"] += 1
                    self.stats["total_cost"] += 0.003  # Approximate cost per solve
                    logger.success("CAPTCHA solved successfully!")
                    return True

            self.stats["captchas_failed"] += 1
            return False

        except Exception as e:
            logger.error(f"Error solving CAPTCHA: {e}")
            self.stats["captchas_failed"] += 1
            return False

    async def _solve_recaptcha_v2(
        self,
        sitekey: str,
        page_url: str,
        timeout: int
    ) -> Optional[Dict]:
        """Solve reCAPTCHA v2 using 2Captcha."""
        try:
            def solve():
                return self.solver.recaptcha(
                    sitekey=sitekey,
                    url=page_url
                )

            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, solve),
                timeout=timeout
            )

            return {"code": result.get("code")}

        except asyncio.TimeoutError:
            logger.error("CAPTCHA solving timed out")
            return None
        except Exception as e:
            logger.error(f"Error solving reCAPTCHA v2: {e}")
            return None

    async def _solve_recaptcha_v3(
        self,
        sitekey: str,
        page_url: str,
        timeout: int,
        action: str = "verify",
        min_score: float = 0.7
    ) -> Optional[Dict]:
        """Solve reCAPTCHA v3 using 2Captcha."""
        try:
            def solve():
                return self.solver.recaptcha(
                    sitekey=sitekey,
                    url=page_url,
                    version='v3',
                    action=action,
                    score=min_score
                )

            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, solve),
                timeout=timeout
            )

            return {"code": result.get("code")}

        except asyncio.TimeoutError:
            logger.error("CAPTCHA solving timed out")
            return None
        except Exception as e:
            logger.error(f"Error solving reCAPTCHA v3: {e}")
            return None

    async def _solve_hcaptcha(
        self,
        sitekey: str,
        page_url: str,
        timeout: int
    ) -> Optional[Dict]:
        """Solve hCaptcha using 2Captcha."""
        try:
            def solve():
                return self.solver.hcaptcha(
                    sitekey=sitekey,
                    url=page_url
                )

            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, solve),
                timeout=timeout
            )

            return {"code": result.get("code")}

        except asyncio.TimeoutError:
            logger.error("CAPTCHA solving timed out")
            return None
        except Exception as e:
            logger.error(f"Error solving hCaptcha: {e}")
            return None

    async def _inject_solution(
        self,
        page: Page,
        token: str,
        captcha_type: str
    ) -> bool:
        """Inject the CAPTCHA solution into the page."""
        try:
            if captcha_type in ["recaptcha_v2", "recaptcha_v3", "google_unusual_traffic"]:
                # Inject reCAPTCHA token
                await page.evaluate(f'''
                    (token) => {{
                        // Set the response textarea
                        const textarea = document.getElementById('g-recaptcha-response');
                        if (textarea) {{
                            textarea.innerHTML = token;
                            textarea.style.display = 'block';
                        }}

                        // Also try alternative locations
                        const textareas = document.querySelectorAll('[name="g-recaptcha-response"]');
                        textareas.forEach(t => t.innerHTML = token);

                        // Trigger callback if available
                        if (typeof ___grecaptcha_cfg !== 'undefined') {{
                            const clients = ___grecaptcha_cfg.clients;
                            if (clients) {{
                                Object.keys(clients).forEach(key => {{
                                    const client = clients[key];
                                    if (client.callback) {{
                                        client.callback(token);
                                    }}
                                }});
                            }}
                        }}

                        // Try window callback
                        if (window.captchaCallback) {{
                            window.captchaCallback(token);
                        }}
                    }}
                ''', token)

                # Try to find and click submit button
                submit_selectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    '#submit',
                    '.submit-button',
                    'button:has-text("Submit")',
                    'button:has-text("Continue")'
                ]

                for selector in submit_selectors:
                    try:
                        submit_btn = await page.query_selector(selector)
                        if submit_btn:
                            await submit_btn.click()
                            await asyncio.sleep(2)
                            break
                    except:
                        continue

                return True

            elif captcha_type == "hcaptcha":
                # Inject hCaptcha token
                await page.evaluate(f'''
                    (token) => {{
                        const textarea = document.querySelector('[name="h-captcha-response"]');
                        if (textarea) {{
                            textarea.innerHTML = token;
                        }}

                        // Set on all iframes
                        const iframes = document.querySelectorAll('iframe[src*="hcaptcha"]');
                        iframes.forEach(iframe => {{
                            try {{
                                iframe.contentDocument.querySelector('[name="h-captcha-response"]').innerHTML = token;
                            }} catch(e) {{}}
                        }});
                    }}
                ''', token)

                return True

        except Exception as e:
            logger.error(f"Error injecting CAPTCHA solution: {e}")
            return False

        return False

    async def handle_captcha_with_retry(
        self,
        page: Page,
        max_retries: int = 3,
        cooldown: int = 60
    ) -> bool:
        """
        Handle CAPTCHA with retries and cooldown.

        Args:
            page: Playwright page object
            max_retries: Maximum number of solve attempts
            cooldown: Seconds to wait between retries

        Returns:
            True if CAPTCHA was handled successfully
        """
        for attempt in range(max_retries):
            logger.info(f"CAPTCHA solve attempt {attempt + 1}/{max_retries}")

            captcha_info = await self.detect_captcha(page)

            if not captcha_info.get("detected"):
                logger.info("No CAPTCHA present")
                return True

            if await self.solve_captcha(page, captcha_info):
                # Wait and verify CAPTCHA is gone
                await asyncio.sleep(3)
                new_check = await self.detect_captcha(page)
                if not new_check.get("detected"):
                    return True

            # Cooldown before retry
            if attempt < max_retries - 1:
                logger.info(f"Waiting {cooldown}s before retry...")
                await asyncio.sleep(cooldown)

        logger.error("Failed to solve CAPTCHA after all retries")
        return False

    def get_stats(self) -> Dict:
        """Get CAPTCHA solving statistics."""
        return {
            **self.stats,
            "success_rate": (
                self.stats["captchas_solved"] / self.stats["captchas_detected"] * 100
                if self.stats["captchas_detected"] > 0 else 0
            )
        }

    def get_balance(self) -> Optional[float]:
        """Get remaining 2Captcha balance."""
        if not self.enabled:
            return None

        try:
            balance = self.solver.balance()
            return float(balance)
        except Exception as e:
            logger.error(f"Error getting CAPTCHA balance: {e}")
            return None


# Singleton instance
_captcha_solver = None

def get_captcha_solver(api_key: Optional[str] = None) -> CaptchaSolver:
    """Get or create the CAPTCHA solver instance."""
    global _captcha_solver
    if _captcha_solver is None or (api_key and not _captcha_solver.enabled):
        _captcha_solver = CaptchaSolver(api_key)
    return _captcha_solver
