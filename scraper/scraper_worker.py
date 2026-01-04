"""Standalone scraper worker that runs in a separate process."""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import random
import re
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger

# Configure logger for this process
logger.remove()
logger.add(sys.stderr, level="INFO")


def run_scrape_job(job_id: int, search_query: str, location: str, max_results: int, extract_emails: bool = False):
    """
    Run a complete scrape job in isolation.
    This function runs in a separate process to avoid asyncio/greenlet conflicts.
    """
    from playwright.sync_api import sync_playwright
    from database import db_manager, BusinessLead, ScrapeJob

    results = []

    # Initialize database
    db_manager.initialize()

    # Update job status to running
    _update_job_status(job_id, 'running', 0)

    playwright = None
    browser = None

    try:
        # Construct search query
        if location:
            full_query = f"{search_query} in {location}"
        else:
            full_query = search_query

        logger.info(f"Starting scrape job {job_id}: '{full_query}' (max: {max_results})")

        # Start Playwright
        playwright = sync_playwright().start()

        # Launch browser with anti-detection
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        # Create context
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
        )

        # Add anti-detection script
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        page = context.new_page()
        page.set_default_timeout(60000)

        # Navigate to Google Maps
        logger.info("Navigating to Google Maps...")
        page.goto('https://www.google.com/maps', wait_until='networkidle')
        time.sleep(random.uniform(2, 4))

        # Perform search
        logger.info(f"Searching for: {full_query}")
        search_box = page.wait_for_selector('input#searchboxinput', timeout=15000)
        search_box.fill(full_query)
        time.sleep(0.5)

        # Submit search
        try:
            page.click('button#searchbox-searchbutton')
        except:
            page.press('input#searchboxinput', 'Enter')

        # Wait for results
        time.sleep(3)
        page.wait_for_selector('div[role="feed"]', timeout=20000)
        logger.info("Search results loaded")

        # Scroll to load more results
        _scroll_results(page, max_results)

        # Get listing links
        listings = _get_listings(page)
        logger.info(f"Found {len(listings)} listings")

        # Scrape each listing
        for i, listing in enumerate(listings[:max_results]):
            try:
                logger.info(f"Scraping {i + 1}/{min(len(listings), max_results)}: {listing['name']}")

                # Click listing
                try:
                    listing['element'].click(timeout=5000)
                except:
                    page.goto(listing['url'], wait_until='domcontentloaded')

                time.sleep(random.uniform(2, 4))

                # Extract data
                business_data = _extract_business_data(page, full_query)

                if business_data:
                    # Save to database
                    if _save_to_database(business_data):
                        results.append(business_data)
                        _update_job_progress(job_id, len(results))
                        logger.success(f"Saved: {business_data['business_name']}")

                # Rate limiting delay
                time.sleep(random.uniform(3, 6))

            except Exception as e:
                logger.error(f"Error scraping listing {i + 1}: {e}")
                continue

        # Update job as completed
        _update_job_status(job_id, 'completed', len(results))
        logger.success(f"Job {job_id} completed: {len(results)} leads scraped")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        _update_job_status(job_id, 'failed', len(results), str(e))

    finally:
        if browser:
            browser.close()
        if playwright:
            playwright.stop()

    return results


def _scroll_results(page, target_count: int):
    """Scroll results panel to load more listings."""
    try:
        scroll_attempts = min(target_count // 20 + 1, 10)

        for i in range(scroll_attempts):
            page.evaluate('''
                const feed = document.querySelector('div[role="feed"]');
                if (feed) { feed.scrollTop = feed.scrollHeight; }
            ''')
            time.sleep(2)

            # Check for end
            try:
                end = page.query_selector('span:has-text("You\'ve reached the end")')
                if end:
                    break
            except:
                pass
    except Exception as e:
        logger.debug(f"Scroll error: {e}")


def _get_listings(page) -> List[Dict]:
    """Get listing links from results."""
    listings = []
    seen_urls = set()

    try:
        elements = page.query_selector_all('div[role="feed"] a[href*="/maps/place/"]')

        for element in elements:
            try:
                href = element.get_attribute('href')
                name = element.get_attribute('aria-label') or f"Business {len(listings) + 1}"

                if href and href not in seen_urls:
                    listings.append({'url': href, 'name': name, 'element': element})
                    seen_urls.add(href)
            except:
                continue

    except Exception as e:
        logger.error(f"Error getting listings: {e}")

    return listings


def _extract_business_data(page, search_query: str) -> Optional[Dict]:
    """Extract business data from listing page."""
    try:
        data = {
            'search_query': search_query,
            'scraped_at': datetime.now(),
        }

        # Business name
        for selector in ['h1.DUwDvf', 'h1[class*="fontHeadline"]', 'div[role="main"] h1']:
            try:
                el = page.query_selector(selector)
                if el:
                    data['business_name'] = el.inner_text().strip()
                    break
            except:
                continue

        if not data.get('business_name'):
            return None

        # Address
        for selector in ['button[data-item-id="address"]', 'button[aria-label*="Address"]']:
            try:
                el = page.query_selector(selector)
                if el:
                    aria = el.get_attribute('aria-label')
                    if aria and 'Address:' in aria:
                        data['full_address'] = aria.replace('Address:', '').strip()
                    else:
                        data['full_address'] = el.inner_text().strip()
                    break
            except:
                continue

        # Parse address components
        if data.get('full_address'):
            # Pin code
            pin_match = re.search(r'\b(\d{6})\b', data['full_address'])
            if pin_match:
                data['pin_code'] = pin_match.group(1)

            # State
            states = ['Maharashtra', 'Delhi', 'Karnataka', 'Tamil Nadu', 'Gujarat', 'Rajasthan',
                     'Uttar Pradesh', 'West Bengal', 'Madhya Pradesh', 'Kerala', 'Telangana']
            for state in states:
                if state in data['full_address']:
                    data['state'] = state
                    break

        # Phone
        for selector in ['button[data-item-id*="phone"]', 'a[href^="tel:"]']:
            try:
                el = page.query_selector(selector)
                if el:
                    aria = el.get_attribute('aria-label') or ''
                    href = el.get_attribute('href') or ''
                    text = el.inner_text() or ''

                    for source in [aria, href.replace('tel:', ''), text]:
                        phone_match = re.search(r'[\d\s\-\+\(\)]+', source)
                        if phone_match:
                            phone = re.sub(r'[^\d\+]', '', phone_match.group())
                            if len(phone) >= 10:
                                data['phone'] = phone
                                break
                    if data.get('phone'):
                        break
            except:
                continue

        # Website
        for selector in ['a[data-item-id="authority"]', 'a[aria-label*="Website"]']:
            try:
                el = page.query_selector(selector)
                if el:
                    href = el.get_attribute('href')
                    if href and href.startswith('http'):
                        data['website'] = href
                        break
            except:
                continue

        # Category
        for selector in ['button[jsaction*="category"]', 'button.DkEaL']:
            try:
                el = page.query_selector(selector)
                if el:
                    data['category'] = el.inner_text().strip()
                    break
            except:
                continue

        # Rating
        try:
            el = page.query_selector('div.F7nice span[aria-hidden="true"]')
            if el:
                text = el.inner_text()
                match = re.search(r'(\d+\.?\d*)', text)
                if match:
                    data['rating'] = float(match.group(1))
        except:
            pass

        # Maps URL and Place ID
        data['maps_url'] = page.url
        place_match = re.search(r'!1s(ChIJ[a-zA-Z0-9_-]+)', page.url)
        if place_match:
            data['place_id'] = place_match.group(1)

        # Coordinates
        coords_match = re.search(r'@(-?\d+\.?\d*),(-?\d+\.?\d*),', page.url)
        if coords_match:
            data['latitude'] = float(coords_match.group(1))
            data['longitude'] = float(coords_match.group(2))

        # Calculate quality score
        important = ['business_name', 'full_address', 'phone', 'website', 'category', 'place_id']
        filled = sum(1 for f in important if data.get(f))
        data['data_quality_score'] = int((filled / len(important)) * 100)

        return data

    except Exception as e:
        logger.error(f"Error extracting data: {e}")
        return None


def _save_to_database(business_data: Dict) -> bool:
    """Save business data to database."""
    from database import db_manager, BusinessLead

    try:
        with db_manager.get_session() as session:
            # Check for duplicates
            if business_data.get('place_id'):
                existing = session.query(BusinessLead).filter_by(
                    place_id=business_data['place_id']
                ).first()
                if existing:
                    logger.info(f"Duplicate: {business_data['business_name']}")
                    return False

            # Create and save
            lead = BusinessLead(**business_data)
            lead.calculate_quality_score()
            session.add(lead)
            session.commit()
            return True

    except Exception as e:
        logger.error(f"Database error: {e}")
        return False


def _update_job_status(job_id: int, status: str, leads_scraped: int, error: str = None):
    """Update job status in database."""
    from database import db_manager, ScrapeJob

    try:
        with db_manager.get_session() as session:
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
    except Exception as e:
        logger.error(f"Error updating job status: {e}")


def _update_job_progress(job_id: int, leads_scraped: int):
    """Update job progress."""
    from database import db_manager, ScrapeJob

    try:
        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter_by(id=job_id).first()
            if job:
                job.leads_scraped = leads_scraped
                session.commit()
    except:
        pass


if __name__ == '__main__':
    # Parse command line arguments
    if len(sys.argv) >= 5:
        job_id = int(sys.argv[1])
        search_query = sys.argv[2]
        location = sys.argv[3]
        max_results = int(sys.argv[4])
        extract_emails = sys.argv[5].lower() == 'true' if len(sys.argv) > 5 else False

        run_scrape_job(job_id, search_query, location, max_results, extract_emails)
    else:
        print("Usage: python scraper_worker.py <job_id> <search_query> <location> <max_results> [extract_emails]")
