# MapLeads Pro - Complete Implementation Plan

## Executive Summary

This plan outlines the implementation of 16 features across 5 priority levels for MapLeads Pro. The existing codebase is well-architected with clear patterns to follow. All new features will be implemented as separate modules that plug into the existing architecture.

---

## Current Architecture Overview

```
ai-google-map-scrapper/
├── api/                    # FastAPI REST API
│   ├── routes/            # Endpoint definitions
│   ├── schemas/           # Pydantic models
│   └── services/          # Business logic
├── scraper/               # Core scraping engine
│   ├── browser_engine.py  # Playwright automation
│   ├── proxy_manager.py   # Proxy rotation (EXISTS - NOT INTEGRATED)
│   ├── captcha_solver.py  # 2Captcha integration (EXISTS - NOT INTEGRATED)
│   └── extractors/        # Data extraction modules
├── config/settings.py     # Pydantic settings
├── database/models.py     # SQLAlchemy models
└── utils/                 # Export & integration utilities
```

---

## Priority 1: Integration of Existing Code

### 1.1 Wire `proxy_manager.py` into `browser_engine.py`

**Current State:**
- `proxy_manager.py` exists with async proxy fetching from 2 sources
- `browser_engine.py` accepts `proxy_list` but doesn't use ProxyManager

**Implementation:**

**File: `scraper/browser_engine.py`**

```python
# Add imports at top
from scraper.proxy_manager import proxy_manager
import asyncio

# Modify __init__ to add proxy_manager option
def __init__(
    self,
    headless: bool = True,
    use_proxies: bool = False,
    proxy_list: Optional[List[str]] = None,
    use_proxy_manager: bool = False,  # NEW: Use the ProxyManager
    slow_mo: int = 50
):
    self.use_proxy_manager = use_proxy_manager
    # ... existing code ...

# Add new method to initialize proxies
async def _init_proxy_manager(self):
    """Initialize proxy manager with working proxies."""
    if self.use_proxy_manager:
        await proxy_manager.initialize()
        self.proxy_list = [p['url'] for p in proxy_manager.working_proxies]
        logger.info(f"Loaded {len(self.proxy_list)} working proxies from ProxyManager")

# Modify launch() to use ProxyManager
def launch(self) -> Page:
    # If using proxy manager, initialize it first
    if self.use_proxy_manager and not self.proxy_list:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._init_proxy_manager())
        loop.close()

    # ... existing launch code ...

    # Configure proxy with rotation support
    proxy_config = None
    if self.use_proxies and self.proxy_list:
        if self.use_proxy_manager:
            # Get next proxy from rotation
            proxy = proxy_manager.get_next_proxy()
            if proxy:
                proxy_config = {"server": proxy['url']}
                self._current_proxy = proxy
        else:
            proxy_url = random.choice(self.proxy_list)
            proxy_config = {"server": proxy_url}
    # ... rest of launch code ...

# Add method to handle proxy failures
def mark_current_proxy_failed(self):
    """Mark current proxy as failed for rotation."""
    if self.use_proxy_manager and hasattr(self, '_current_proxy'):
        proxy_manager.mark_proxy_failed(self._current_proxy)
        logger.warning(f"Marked proxy as failed: {self._current_proxy['ip']}")
```

**File: `config/settings.py`** - Add settings:

```python
# Proxy Configuration
use_proxy_manager: bool = False
proxy_refresh_interval: int = 3600  # Refresh proxies every hour
proxy_test_count: int = 20  # Number of proxies to test
```

---

### 1.2 Wire `captcha_solver.py` into `browser_engine.py`

**Current State:**
- `captcha_solver.py` has full 2Captcha integration (async)
- Uses Playwright async API but browser_engine uses sync API

**Implementation:**

**File: `scraper/browser_engine.py`**

```python
# Add imports
from scraper.captcha_solver import get_captcha_solver, CaptchaSolver
from config.settings import settings

# Add to __init__
def __init__(self, ..., captcha_enabled: bool = False):
    self.captcha_enabled = captcha_enabled
    self._captcha_solver: Optional[CaptchaSolver] = None

    if captcha_enabled and settings.captcha_api_key:
        self._captcha_solver = get_captcha_solver(settings.captcha_api_key)

# Add sync wrapper for captcha detection
def detect_captcha_sync(self) -> Dict:
    """Synchronous wrapper for captcha detection."""
    if not self._captcha_solver or not self._page:
        return {"detected": False}

    # Run async detection in sync context
    loop = asyncio.new_event_loop()
    try:
        # Convert sync page to async-compatible check
        result = loop.run_until_complete(
            self._detect_captcha_indicators()
        )
        return result
    finally:
        loop.close()

def _detect_captcha_indicators(self) -> Dict:
    """Check for CAPTCHA indicators on page."""
    result = {"detected": False, "type": None, "sitekey": None}

    # Check for reCAPTCHA v2
    recaptcha = self._page.query_selector('div.g-recaptcha')
    if recaptcha:
        result["detected"] = True
        result["type"] = "recaptcha_v2"
        result["sitekey"] = recaptcha.get_attribute('data-sitekey')
        return result

    # Check for unusual traffic page
    unusual = self._page.query_selector('div#recaptcha')
    if unusual:
        result["detected"] = True
        result["type"] = "google_unusual_traffic"
        sitekey_elem = self._page.query_selector('[data-sitekey]')
        if sitekey_elem:
            result["sitekey"] = sitekey_elem.get_attribute('data-sitekey')

    return result

def handle_captcha_if_present(self) -> bool:
    """Check for and solve CAPTCHA if present. Returns True if page is usable."""
    if not self._captcha_solver:
        return True

    captcha_info = self._detect_captcha_indicators()

    if not captcha_info["detected"]:
        return True

    logger.warning(f"CAPTCHA detected: {captcha_info['type']}")

    if not captcha_info["sitekey"]:
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
            new_check = self._detect_captcha_indicators()
            return not new_check["detected"]
    except Exception as e:
        logger.error(f"CAPTCHA solving failed: {e}")

    return False

def _solve_captcha_sync(self, captcha_type: str, sitekey: str) -> Optional[str]:
    """Synchronously solve CAPTCHA using 2Captcha."""
    try:
        if captcha_type in ["recaptcha_v2", "google_unusual_traffic"]:
            result = self._captcha_solver.solver.recaptcha(
                sitekey=sitekey,
                url=self._page.url
            )
            return result.get("code")
    except Exception as e:
        logger.error(f"2Captcha solve error: {e}")
    return None

def _inject_captcha_solution(self, token: str, captcha_type: str):
    """Inject CAPTCHA solution into page."""
    self._page.evaluate(f'''
        (token) => {{
            const textarea = document.getElementById('g-recaptcha-response');
            if (textarea) {{
                textarea.innerHTML = token;
                textarea.style.display = 'block';
            }}

            // Trigger callback
            if (typeof ___grecaptcha_cfg !== 'undefined') {{
                const clients = ___grecaptcha_cfg.clients;
                if (clients) {{
                    Object.keys(clients).forEach(key => {{
                        const client = clients[key];
                        if (client.callback) client.callback(token);
                    }});
                }}
            }}
        }}
    ''', token)

    # Try to submit
    submit_btn = self._page.query_selector('button[type="submit"], input[type="submit"]')
    if submit_btn:
        submit_btn.click()
```

**Integrate into navigation methods:**

```python
def navigate_to_maps(self, retries: int = 3) -> bool:
    # ... existing navigation code ...

    # After navigation, check for CAPTCHA
    if self.captcha_enabled:
        if not self.handle_captcha_if_present():
            logger.warning("CAPTCHA blocking access")
            return False

    # ... rest of method ...
```

---

### 1.3 Complete Review Text Extraction in `review_extractor.py`

**Current State:**
- ReviewExtractor exists with basic structure
- `_parse_single_review()` has placeholders but works
- Missing: reviewer_photo extraction

**Implementation:**

**File: `scraper/extractors/review_extractor.py`** - Enhance `_parse_single_review()`:

```python
def _parse_single_review(self, element) -> Optional[Dict]:
    """Parse a single review element - ENHANCED VERSION."""
    try:
        review = {
            "reviewer_name": None,
            "reviewer_profile_url": None,
            "reviewer_photo": None,  # NEW
            "reviewer_reviews_count": None,
            "reviewer_photos_count": None,
            "reviewer_level": None,  # NEW: Local Guide level
            "rating": None,
            "review_text": None,
            "review_date": None,
            "review_date_relative": None,
            "owner_response": None,
            "owner_response_date": None,
            "review_photos": [],
            "helpful_count": 0,
            "review_id": None,
            "review_language": None,  # NEW
            "is_translated": False,  # NEW
        }

        # ... existing extraction code ...

        # NEW: Extract reviewer photo
        photo_selectors = [
            'button[class*="al6Kxe"] img',
            'img[class*="NBa7we"]',
            'a[href*="contrib"] img',
        ]
        for selector in photo_selectors:
            try:
                photo_elem = element.query_selector(selector)
                if photo_elem:
                    src = photo_elem.get_attribute('src')
                    if src and 'googleusercontent' in src:
                        # Get higher resolution version
                        review["reviewer_photo"] = src.replace('=s40-', '=s100-')
                        break
            except:
                continue

        # NEW: Extract Local Guide level
        guide_selectors = [
            'span[class*="RfnDt"]:has-text("Local Guide")',
            'div[class*="guide-level"]',
        ]
        for selector in guide_selectors:
            try:
                guide_elem = element.query_selector(selector)
                if guide_elem:
                    text = guide_elem.inner_text()
                    level_match = re.search(r'Level\s*(\d+)', text, re.IGNORECASE)
                    if level_match:
                        review["reviewer_level"] = int(level_match.group(1))
                    break
            except:
                continue

        # NEW: Check if review is translated
        translated_elem = element.query_selector('span:has-text("Translated")')
        if translated_elem:
            review["is_translated"] = True

        # NEW: Extract original language indicator
        lang_elem = element.query_selector('span[class*="lang"]')
        if lang_elem:
            lang_text = lang_elem.get_attribute('lang') or lang_elem.inner_text()
            if lang_text:
                review["review_language"] = lang_text[:10]

        return review if (review["reviewer_name"] or review["review_text"] or review["rating"]) else None

    except Exception as e:
        logger.debug(f"Error parsing review: {e}")
        return None
```

---

### 1.4 Integrate `popular_times_extractor.py` into Scraping Pipeline

**Current State:**
- PopularTimesExtractor exists and is complete
- Already imported in unified_scraper.py
- Already conditionally called when `extract_popular_times=True`

**Implementation:** Already integrated! Just needs to be enabled via `ScrapeConfig.extract_popular_times = True`

**Add to database model** `database/models.py`:

```python
# Add to BusinessLead model
popular_times = Column(JSON, nullable=True)  # Store full popular times data
busiest_day = Column(String(20), nullable=True)
busiest_hour = Column(String(20), nullable=True)
typical_time_spent = Column(String(50), nullable=True)
live_busyness = Column(Integer, nullable=True)
```

**Update unified_scraper.py** to save popular times:

```python
# In _scrape_listing(), update the popular times section:
if config.extract_popular_times:
    try:
        popular_times = self.popular_times_extractor.extract_popular_times(page)
        lead_data["popular_times"] = popular_times.get("popular_times")
        lead_data["busiest_day"] = popular_times.get("busiest_day")
        lead_data["busiest_hour"] = popular_times.get("busiest_hour")
        lead_data["typical_time_spent"] = popular_times.get("typical_time_spent")
        lead_data["live_busyness"] = popular_times.get("live_busyness")
    except Exception as e:
        logger.debug(f"Popular times extraction failed: {e}")
```

---

## Priority 2: New Core Features

### 2.1 Geo-Coordinate Based Search

**New File: `scraper/geo_search.py`**

```python
"""Geo-coordinate based search for Google Maps."""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import math
from loguru import logger


@dataclass
class GeoSearchConfig:
    """Configuration for geo-based search."""
    latitude: float
    longitude: float
    radius_km: float = 5.0
    search_query: str = ""
    grid_size: int = 3  # 3x3 grid for coverage


class GeoSearchManager:
    """Manage geo-coordinate based searches."""

    EARTH_RADIUS_KM = 6371.0

    def __init__(self):
        self.searched_areas: List[Tuple[float, float]] = []

    def generate_search_url(
        self,
        query: str,
        lat: float,
        lng: float,
        zoom: int = 15
    ) -> str:
        """Generate Google Maps search URL with coordinates."""
        # Format: https://www.google.com/maps/search/restaurants/@lat,lng,zoomz
        encoded_query = query.replace(' ', '+')
        return f"https://www.google.com/maps/search/{encoded_query}/@{lat},{lng},{zoom}z"

    def generate_grid_points(
        self,
        center_lat: float,
        center_lng: float,
        radius_km: float,
        grid_size: int = 3
    ) -> List[Dict]:
        """Generate grid of search points to cover area."""
        points = []

        # Calculate the distance between grid points
        step = (radius_km * 2) / grid_size

        for i in range(grid_size):
            for j in range(grid_size):
                # Calculate offset from center
                offset_km_lat = (i - grid_size // 2) * step
                offset_km_lng = (j - grid_size // 2) * step

                # Convert km offset to lat/lng offset
                lat_offset = offset_km_lat / 111.0  # ~111km per degree latitude
                lng_offset = offset_km_lng / (111.0 * math.cos(math.radians(center_lat)))

                new_lat = center_lat + lat_offset
                new_lng = center_lng + lng_offset

                points.append({
                    "latitude": round(new_lat, 6),
                    "longitude": round(new_lng, 6),
                    "grid_position": f"{i},{j}"
                })

        return points

    def calculate_distance(
        self,
        lat1: float, lng1: float,
        lat2: float, lng2: float
    ) -> float:
        """Calculate distance between two coordinates in km (Haversine)."""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        a = (math.sin(delta_lat/2)**2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return self.EARTH_RADIUS_KM * c

    def filter_by_radius(
        self,
        leads: List[Dict],
        center_lat: float,
        center_lng: float,
        radius_km: float
    ) -> List[Dict]:
        """Filter leads to only include those within radius."""
        filtered = []

        for lead in leads:
            lead_lat = lead.get("latitude")
            lead_lng = lead.get("longitude")

            if lead_lat and lead_lng:
                distance = self.calculate_distance(
                    center_lat, center_lng, lead_lat, lead_lng
                )
                if distance <= radius_km:
                    lead["distance_km"] = round(distance, 2)
                    filtered.append(lead)
            else:
                # Include leads without coordinates (can't verify distance)
                filtered.append(lead)

        return filtered


# Singleton instance
geo_search_manager = GeoSearchManager()
```

**Add to `browser_engine.py`:**

```python
def search_by_coordinates(
    self,
    query: str,
    latitude: float,
    longitude: float,
    zoom: int = 15
) -> bool:
    """Search Google Maps at specific coordinates."""
    if not self._page:
        raise RuntimeError("Browser not launched")

    try:
        # Navigate directly to coordinate-based search URL
        url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}/@{latitude},{longitude},{zoom}z"

        self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        # Wait for results
        self._page.wait_for_selector(
            'div[role="feed"], div[aria-label*="Results"]',
            timeout=15000
        )

        logger.info(f"Geo search at ({latitude}, {longitude}): {query}")
        return True

    except Exception as e:
        logger.error(f"Geo search failed: {e}")
        return False
```

**New API endpoint in `api/routes/scraping.py`:**

```python
@router.post("/scrape/geo", response_model=JobResponse)
async def geo_scrape(request: GeoScrapeRequest, background_tasks: BackgroundTasks):
    """
    Start a geo-coordinate based scrape job.
    Searches within a radius of the specified coordinates.
    """
    try:
        job = scrape_service.create_geo_job(request)

        background_tasks.add_task(
            scrape_service.run_geo_scrape,
            job.job_id,
            request
        )

        return JobResponse(
            job_id=job.job_id,
            status="started",
            search_query=f"Geo: {request.search_query} @ ({request.latitude}, {request.longitude})"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**New schema in `api/schemas/requests.py`:**

```python
class GeoScrapeRequest(BaseModel):
    """Request for geo-coordinate based scraping."""
    search_query: str = Field(..., min_length=1, max_length=500)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(5.0, ge=0.1, le=50)
    max_results: int = Field(100, ge=1, le=500)
    use_grid_search: bool = Field(False, description="Search multiple points in grid")
    grid_size: int = Field(3, ge=2, le=5)

    # Standard extraction options
    extract_emails: bool = True
    extract_social: bool = True
    enrich_from_website: bool = True
```

---

### 2.2 Bulk URL Import Endpoint

**New File: `api/routes/bulk_import.py`**

```python
"""Bulk URL import endpoint for Google Maps URLs."""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import List
from pydantic import BaseModel, Field, field_validator
from loguru import logger
import re

router = APIRouter()


class BulkURLImportRequest(BaseModel):
    """Request to import multiple Google Maps URLs."""
    urls: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of Google Maps place URLs"
    )
    extract_emails: bool = True
    extract_social: bool = True
    enrich_from_website: bool = True

    @field_validator('urls')
    @classmethod
    def validate_urls(cls, urls: List[str]) -> List[str]:
        """Validate that URLs are Google Maps place URLs."""
        validated = []
        for url in urls:
            url = url.strip()
            if not url:
                continue

            # Check if it's a valid Google Maps URL
            if 'google.com/maps' in url or 'maps.google.com' in url:
                validated.append(url)
            elif url.startswith('ChI'):  # Place ID format
                validated.append(f"https://www.google.com/maps/place/?q=place_id:{url}")
            else:
                logger.warning(f"Invalid Google Maps URL skipped: {url[:50]}...")

        if not validated:
            raise ValueError("No valid Google Maps URLs provided")

        return validated


class BulkURLImportResponse(BaseModel):
    """Response from bulk URL import."""
    job_id: int
    status: str
    total_urls: int
    valid_urls: int
    message: str


@router.post("/import/urls", response_model=BulkURLImportResponse)
async def bulk_import_urls(
    request: BulkURLImportRequest,
    background_tasks: BackgroundTasks
):
    """
    Import leads from a list of Google Maps URLs.

    Accepts:
    - Full Google Maps place URLs
    - Google Place IDs (starting with 'ChI')
    - Short URLs (will be resolved)
    """
    try:
        from api.services.scrape_service import scrape_service

        # Create import job
        job = scrape_service.create_url_import_job(request)

        # Run import in background
        background_tasks.add_task(
            scrape_service.run_url_import,
            job.job_id,
            request.urls,
            request
        )

        return BulkURLImportResponse(
            job_id=job.job_id,
            status="started",
            total_urls=len(request.urls),
            valid_urls=len(request.urls),
            message=f"Importing {len(request.urls)} URLs"
        )

    except Exception as e:
        logger.error(f"Bulk import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/place-ids", response_model=BulkURLImportResponse)
async def bulk_import_place_ids(
    place_ids: List[str],
    background_tasks: BackgroundTasks
):
    """Import leads from a list of Google Place IDs."""
    # Convert place IDs to URLs
    urls = [
        f"https://www.google.com/maps/place/?q=place_id:{pid}"
        for pid in place_ids if pid.startswith('ChI')
    ]

    request = BulkURLImportRequest(urls=urls)
    return await bulk_import_urls(request, background_tasks)
```

**Add to scrape_service.py:**

```python
def create_url_import_job(self, request) -> ScrapeJob:
    """Create a job for URL import."""
    with db_manager.get_session() as session:
        job = ScrapeJob(
            search_query=f"URL Import ({len(request.urls)} URLs)",
            max_results=len(request.urls),
            leads_target=len(request.urls),
            status="pending"
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

async def run_url_import(
    self,
    job_id: int,
    urls: List[str],
    config
):
    """Run URL import job."""
    from scraper.browser_engine import BrowserEngine
    from scraper.extractors import MapsExtractor, ContactExtractor, SocialMediaExtractor

    browser = None
    try:
        self._update_job_status(job_id, "running")

        browser = BrowserEngine(headless=True)
        page = browser.launch()

        maps_extractor = MapsExtractor()
        leads_saved = 0

        for i, url in enumerate(urls):
            try:
                # Navigate to URL
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(2)

                # Extract data
                lead_data = maps_extractor.extract(page, "URL Import")

                if lead_data.get("business_name"):
                    # Enrich if enabled
                    if config.enrich_from_website and lead_data.get("website"):
                        # ... enrichment code ...
                        pass

                    # Save to database
                    self._save_lead(lead_data, job_id)
                    leads_saved += 1

                # Progress update
                self._update_job_progress(job_id, i + 1, len(urls))

                time.sleep(random.uniform(2, 4))

            except Exception as e:
                logger.error(f"URL import error for {url[:50]}: {e}")

        self._update_job_status(job_id, "completed", {"leads_saved": leads_saved})

    except Exception as e:
        self._update_job_status(job_id, "failed", {"error": str(e)})
    finally:
        if browser:
            browser.close()
```

---

### 2.3 Image/Photo URL Extraction

**Update `scraper/extractors/maps_extractor.py`:**

```python
def extract(self, page: Page, search_query: str = "") -> Dict:
    """Extract business data including photos."""
    data = {
        # ... existing fields ...
        "photos": [],  # NEW: List of photo URLs
        "photo_count": 0,  # NEW
        "main_photo": None,  # NEW: Primary business photo
    }

    # ... existing extraction code ...

    # NEW: Extract photos
    data["photos"], data["photo_count"] = self._extract_photos(page)
    if data["photos"]:
        data["main_photo"] = data["photos"][0]

    return data

def _extract_photos(self, page: Page, max_photos: int = 10) -> Tuple[List[str], int]:
    """Extract photo URLs from business listing."""
    photos = []
    total_count = 0

    try:
        # Get photo count from "See all photos" button
        photo_count_selectors = [
            'button[aria-label*="photo"]',
            'button:has-text("photos")',
            'button:has-text("See all")',
        ]

        for selector in photo_count_selectors:
            elem = page.query_selector(selector)
            if elem:
                text = elem.get_attribute('aria-label') or elem.inner_text()
                match = re.search(r'(\d+)\s*photo', text, re.IGNORECASE)
                if match:
                    total_count = int(match.group(1))
                    break

        # Extract visible photo URLs
        photo_selectors = [
            'button[aria-label*="Photo"] img',
            'div[role="img"] img',
            'img[src*="googleusercontent"][src*="place"]',
            'img[class*="gallery"]',
        ]

        seen_urls = set()

        for selector in photo_selectors:
            img_elements = page.query_selector_all(selector)
            for img in img_elements[:max_photos]:
                src = img.get_attribute('src')
                if src and 'googleusercontent' in src:
                    # Get higher resolution version
                    # Original: =s100-c → =s800-c for larger image
                    high_res = re.sub(r'=s\d+-', '=s800-', src)
                    high_res = re.sub(r'=w\d+-h\d+', '=w800-h600', high_res)

                    if high_res not in seen_urls:
                        seen_urls.add(high_res)
                        photos.append(high_res)

                        if len(photos) >= max_photos:
                            break

            if photos:
                break

        if not total_count:
            total_count = len(photos)

    except Exception as e:
        logger.debug(f"Photo extraction error: {e}")

    return photos, total_count
```

**Update database model:**

```python
# In BusinessLead model
photos = Column(JSON, nullable=True)  # List of photo URLs
photo_count = Column(Integer, nullable=True)
main_photo = Column(String(1000), nullable=True)
```

---

### 2.4 Webhook Notifications

**New File: `utils/webhooks.py`**

```python
"""Generic webhook notifications for Zapier/Make/n8n compatibility."""
import aiohttp
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
import json
import hashlib
import hmac


@dataclass
class WebhookConfig:
    """Webhook configuration."""
    url: str
    secret: Optional[str] = None  # For HMAC signing
    headers: Optional[Dict[str, str]] = None
    retry_count: int = 3
    timeout: int = 30


class WebhookManager:
    """Manage webhook notifications."""

    def __init__(self):
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.event_history: List[Dict] = []

    def register_webhook(self, name: str, config: WebhookConfig):
        """Register a webhook endpoint."""
        self.webhooks[name] = config
        logger.info(f"Registered webhook: {name}")

    def _sign_payload(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for payload."""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

    async def send_webhook(
        self,
        webhook_name: str,
        event_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """Send webhook notification."""
        if webhook_name not in self.webhooks:
            logger.error(f"Webhook not registered: {webhook_name}")
            return False

        config = self.webhooks[webhook_name]

        # Build payload (Zapier/Make compatible format)
        payload = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }

        payload_json = json.dumps(payload)

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MapLeads-Pro/2.0",
            **(config.headers or {})
        }

        # Add signature if secret is configured
        if config.secret:
            signature = self._sign_payload(payload_json, config.secret)
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        # Send with retries
        for attempt in range(config.retry_count):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        config.url,
                        data=payload_json,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=config.timeout)
                    ) as response:
                        if response.status in (200, 201, 202, 204):
                            logger.info(f"Webhook sent: {webhook_name} - {event_type}")
                            self._record_event(webhook_name, event_type, True)
                            return True
                        else:
                            logger.warning(f"Webhook returned {response.status}")

            except Exception as e:
                logger.error(f"Webhook attempt {attempt + 1} failed: {e}")
                if attempt < config.retry_count - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        self._record_event(webhook_name, event_type, False)
        return False

    def _record_event(self, webhook: str, event: str, success: bool):
        """Record webhook event for history."""
        self.event_history.append({
            "webhook": webhook,
            "event": event,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        })
        # Keep only last 100 events
        if len(self.event_history) > 100:
            self.event_history = self.event_history[-100:]

    async def send_lead_notification(self, lead: Dict, webhook_name: str = "default"):
        """Send notification when new lead is found."""
        await self.send_webhook(
            webhook_name,
            "lead.created",
            {
                "lead": {
                    "name": lead.get("business_name"),
                    "phone": lead.get("phone"),
                    "email": lead.get("email"),
                    "website": lead.get("website"),
                    "address": lead.get("full_address"),
                    "rating": lead.get("rating"),
                    "category": lead.get("category"),
                    "quality_score": lead.get("quality_score"),
                    "place_id": lead.get("place_id"),
                }
            }
        )

    async def send_job_notification(self, job_id: int, status: str, stats: Dict):
        """Send notification when job status changes."""
        await self.send_webhook(
            "default",
            f"job.{status}",
            {
                "job_id": job_id,
                "status": status,
                "stats": stats
            }
        )


# Global webhook manager
webhook_manager = WebhookManager()


# Helper functions for sync code
def send_webhook_sync(webhook_name: str, event_type: str, data: Dict) -> bool:
    """Synchronous wrapper for sending webhooks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            webhook_manager.send_webhook(webhook_name, event_type, data)
        )
    finally:
        loop.close()
```

**Add settings in `config/settings.py`:**

```python
# Webhook Configuration
webhook_url: Optional[str] = None  # Generic webhook URL
webhook_secret: Optional[str] = None  # HMAC secret for signing
webhook_enabled: bool = False
webhook_events: List[str] = ["job.completed", "lead.created"]  # Events to send
```

**Add API endpoint for webhook management:**

```python
# In api/routes/webhooks.py (NEW FILE)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from utils.webhooks import webhook_manager, WebhookConfig

router = APIRouter()


class WebhookRegistration(BaseModel):
    """Register a webhook endpoint."""
    name: str
    url: HttpUrl
    secret: Optional[str] = None
    events: List[str] = ["job.completed", "lead.created"]


@router.post("/webhooks/register")
async def register_webhook(request: WebhookRegistration):
    """Register a new webhook endpoint."""
    webhook_manager.register_webhook(
        request.name,
        WebhookConfig(
            url=str(request.url),
            secret=request.secret
        )
    )
    return {"status": "registered", "name": request.name}


@router.post("/webhooks/test/{name}")
async def test_webhook(name: str):
    """Send a test event to a webhook."""
    success = await webhook_manager.send_webhook(
        name,
        "test",
        {"message": "Test webhook from MapLeads Pro"}
    )
    return {"status": "sent" if success else "failed"}


@router.get("/webhooks/history")
async def get_webhook_history():
    """Get recent webhook event history."""
    return {"events": webhook_manager.event_history}
```

---

## Priority 3: Chrome Extension

### 3.1 Chrome Extension Structure

**Create new directory: `chrome-extension/`**

```
chrome-extension/
├── manifest.json
├── popup/
│   ├── popup.html
│   ├── popup.css
│   └── popup.js
├── content/
│   └── content.js
├── background/
│   └── service-worker.js
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── utils/
    └── api.js
```

**File: `chrome-extension/manifest.json`**

```json
{
  "manifest_version": 3,
  "name": "MapLeads Pro - Google Maps Extractor",
  "version": "1.0.0",
  "description": "Extract business leads from Google Maps and send to MapLeads Pro",
  "permissions": [
    "activeTab",
    "storage",
    "scripting"
  ],
  "host_permissions": [
    "https://www.google.com/maps/*",
    "https://maps.google.com/*",
    "http://localhost:9000/*"
  ],
  "action": {
    "default_popup": "popup/popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "content_scripts": [
    {
      "matches": ["https://www.google.com/maps/*", "https://maps.google.com/*"],
      "js": ["content/content.js"],
      "css": []
    }
  ],
  "background": {
    "service_worker": "background/service-worker.js"
  },
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

**File: `chrome-extension/popup/popup.html`**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {
      width: 350px;
      padding: 15px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f5f5f5;
    }
    .header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 15px;
      padding-bottom: 10px;
      border-bottom: 1px solid #ddd;
    }
    .header img { width: 32px; height: 32px; }
    .header h1 { font-size: 16px; margin: 0; color: #333; }
    .status {
      padding: 10px;
      border-radius: 6px;
      margin-bottom: 15px;
      font-size: 13px;
    }
    .status.connected { background: #e8f5e9; color: #2e7d32; }
    .status.disconnected { background: #ffebee; color: #c62828; }
    .status.extracting { background: #e3f2fd; color: #1565c0; }
    .btn {
      width: 100%;
      padding: 12px;
      border: none;
      border-radius: 6px;
      font-size: 14px;
      cursor: pointer;
      margin-bottom: 10px;
      transition: all 0.2s;
    }
    .btn-primary {
      background: #4285f4;
      color: white;
    }
    .btn-primary:hover { background: #3367d6; }
    .btn-primary:disabled { background: #ccc; cursor: not-allowed; }
    .btn-secondary {
      background: #fff;
      color: #333;
      border: 1px solid #ddd;
    }
    .btn-secondary:hover { background: #f5f5f5; }
    .stats {
      background: white;
      padding: 12px;
      border-radius: 6px;
      margin-bottom: 15px;
    }
    .stat-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 5px;
      font-size: 13px;
    }
    .stat-label { color: #666; }
    .stat-value { font-weight: 600; color: #333; }
    .results {
      max-height: 200px;
      overflow-y: auto;
      background: white;
      border-radius: 6px;
    }
    .result-item {
      padding: 10px;
      border-bottom: 1px solid #eee;
      font-size: 12px;
    }
    .result-item:last-child { border-bottom: none; }
    .result-name { font-weight: 600; color: #333; }
    .result-details { color: #666; margin-top: 3px; }
    .settings {
      margin-top: 10px;
      font-size: 12px;
    }
    .settings label {
      display: flex;
      align-items: center;
      gap: 5px;
      margin-bottom: 5px;
    }
  </style>
</head>
<body>
  <div class="header">
    <img src="../icons/icon48.png" alt="Logo">
    <h1>MapLeads Pro</h1>
  </div>

  <div id="status" class="status disconnected">
    Checking connection...
  </div>

  <button id="extractBtn" class="btn btn-primary" disabled>
    Extract Current Page
  </button>

  <button id="extractAllBtn" class="btn btn-secondary" disabled>
    Extract All Visible (0)
  </button>

  <div class="stats">
    <div class="stat-row">
      <span class="stat-label">Extracted this session:</span>
      <span class="stat-value" id="sessionCount">0</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Sent to API:</span>
      <span class="stat-value" id="sentCount">0</span>
    </div>
  </div>

  <div class="settings">
    <label>
      <input type="checkbox" id="autoSend" checked>
      Auto-send to API
    </label>
    <label>
      <input type="text" id="apiUrl" value="http://localhost:9000" style="flex:1">
    </label>
  </div>

  <div id="results" class="results"></div>

  <script src="popup.js"></script>
</body>
</html>
```

**File: `chrome-extension/popup/popup.js`**

```javascript
// MapLeads Pro Chrome Extension - Popup Script

const API_URL_KEY = 'mapleads_api_url';
const DEFAULT_API = 'http://localhost:9000';

// State
let isConnected = false;
let visibleListings = 0;
let sessionCount = 0;
let sentCount = 0;

// Elements
const statusEl = document.getElementById('status');
const extractBtn = document.getElementById('extractBtn');
const extractAllBtn = document.getElementById('extractAllBtn');
const sessionCountEl = document.getElementById('sessionCount');
const sentCountEl = document.getElementById('sentCount');
const resultsEl = document.getElementById('results');
const apiUrlInput = document.getElementById('apiUrl');
const autoSendCheckbox = document.getElementById('autoSend');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  // Load saved settings
  const stored = await chrome.storage.local.get([API_URL_KEY, 'sessionCount', 'sentCount']);
  apiUrlInput.value = stored[API_URL_KEY] || DEFAULT_API;
  sessionCount = stored.sessionCount || 0;
  sentCount = stored.sentCount || 0;
  updateStats();

  // Check API connection
  await checkConnection();

  // Check if on Google Maps
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab.url && tab.url.includes('google.com/maps')) {
    // Get count of visible listings
    await countVisibleListings(tab.id);
  } else {
    statusEl.textContent = 'Open Google Maps to extract leads';
    statusEl.className = 'status disconnected';
  }
});

// Save API URL on change
apiUrlInput.addEventListener('change', async () => {
  await chrome.storage.local.set({ [API_URL_KEY]: apiUrlInput.value });
  await checkConnection();
});

// Check API connection
async function checkConnection() {
  try {
    const response = await fetch(`${apiUrlInput.value}/api/health`);
    if (response.ok) {
      isConnected = true;
      statusEl.textContent = 'Connected to MapLeads Pro';
      statusEl.className = 'status connected';
      extractBtn.disabled = false;
      extractAllBtn.disabled = false;
    } else {
      throw new Error('API not responding');
    }
  } catch (e) {
    isConnected = false;
    statusEl.textContent = 'Cannot connect to API. Is the server running?';
    statusEl.className = 'status disconnected';
    extractBtn.disabled = true;
    extractAllBtn.disabled = true;
  }
}

// Count visible listings on page
async function countVisibleListings(tabId) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const listings = document.querySelectorAll('a[href*="/maps/place/"]');
        return listings.length;
      }
    });
    visibleListings = results[0].result || 0;
    extractAllBtn.textContent = `Extract All Visible (${visibleListings})`;
  } catch (e) {
    console.error('Count error:', e);
  }
}

// Extract current business
extractBtn.addEventListener('click', async () => {
  extractBtn.disabled = true;
  extractBtn.textContent = 'Extracting...';
  statusEl.textContent = 'Extracting business data...';
  statusEl.className = 'status extracting';

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractCurrentBusiness
    });

    const businessData = results[0].result;

    if (businessData && businessData.business_name) {
      sessionCount++;
      updateStats();
      addResultToList(businessData);

      if (autoSendCheckbox.checked && isConnected) {
        await sendToAPI(businessData);
      }

      statusEl.textContent = `Extracted: ${businessData.business_name}`;
      statusEl.className = 'status connected';
    } else {
      statusEl.textContent = 'Could not extract business data. Make sure you are viewing a business listing.';
      statusEl.className = 'status disconnected';
    }
  } catch (e) {
    console.error('Extraction error:', e);
    statusEl.textContent = `Error: ${e.message}`;
    statusEl.className = 'status disconnected';
  }

  extractBtn.disabled = false;
  extractBtn.textContent = 'Extract Current Page';
});

// Extract all visible listings
extractAllBtn.addEventListener('click', async () => {
  extractAllBtn.disabled = true;
  extractAllBtn.textContent = 'Extracting...';

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractAllListings
    });

    const listings = results[0].result || [];

    for (const business of listings) {
      if (business.business_name) {
        sessionCount++;
        addResultToList(business);

        if (autoSendCheckbox.checked && isConnected) {
          await sendToAPI(business);
        }
      }
    }

    updateStats();
    statusEl.textContent = `Extracted ${listings.length} businesses`;
    statusEl.className = 'status connected';

  } catch (e) {
    console.error('Bulk extraction error:', e);
    statusEl.textContent = `Error: ${e.message}`;
    statusEl.className = 'status disconnected';
  }

  extractAllBtn.disabled = false;
  extractAllBtn.textContent = `Extract All Visible (${visibleListings})`;
});

// Send data to API
async function sendToAPI(businessData) {
  try {
    const response = await fetch(`${apiUrlInput.value}/api/leads/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ leads: [businessData] })
    });

    if (response.ok) {
      sentCount++;
      updateStats();
      await chrome.storage.local.set({ sentCount });
    }
  } catch (e) {
    console.error('API send error:', e);
  }
}

// Update stats display
function updateStats() {
  sessionCountEl.textContent = sessionCount;
  sentCountEl.textContent = sentCount;
  chrome.storage.local.set({ sessionCount, sentCount });
}

// Add result to list
function addResultToList(business) {
  const item = document.createElement('div');
  item.className = 'result-item';
  item.innerHTML = `
    <div class="result-name">${business.business_name}</div>
    <div class="result-details">
      ${business.phone || 'No phone'} | ${business.email || 'No email'}
    </div>
  `;
  resultsEl.insertBefore(item, resultsEl.firstChild);
}

// Content script function: Extract current business
function extractCurrentBusiness() {
  const data = {
    business_name: null,
    phone: null,
    website: null,
    address: null,
    rating: null,
    review_count: null,
    category: null,
    maps_url: window.location.href,
    latitude: null,
    longitude: null
  };

  // Extract business name
  const nameEl = document.querySelector('h1[class*="header"]') ||
                 document.querySelector('h1') ||
                 document.querySelector('[data-item-id="title"]');
  if (nameEl) data.business_name = nameEl.textContent.trim();

  // Extract phone
  const phoneEl = document.querySelector('button[data-item-id*="phone"]') ||
                  document.querySelector('a[href^="tel:"]');
  if (phoneEl) {
    const phoneText = phoneEl.getAttribute('aria-label') ||
                      phoneEl.textContent ||
                      phoneEl.href?.replace('tel:', '');
    if (phoneText) {
      const phoneMatch = phoneText.match(/[\d\s\-\+\(\)]{10,}/);
      if (phoneMatch) data.phone = phoneMatch[0].trim();
    }
  }

  // Extract website
  const websiteEl = document.querySelector('a[data-item-id*="authority"]') ||
                    document.querySelector('a[aria-label*="website"]');
  if (websiteEl) data.website = websiteEl.href;

  // Extract address
  const addressEl = document.querySelector('button[data-item-id*="address"]') ||
                    document.querySelector('[data-item-id="address"]');
  if (addressEl) {
    data.address = addressEl.getAttribute('aria-label')?.replace('Address: ', '') ||
                   addressEl.textContent.trim();
  }

  // Extract rating
  const ratingEl = document.querySelector('span[role="img"][aria-label*="star"]') ||
                   document.querySelector('[class*="rating"]');
  if (ratingEl) {
    const ratingText = ratingEl.getAttribute('aria-label') || ratingEl.textContent;
    const ratingMatch = ratingText.match(/([\d.]+)/);
    if (ratingMatch) data.rating = parseFloat(ratingMatch[1]);
  }

  // Extract review count
  const reviewEl = document.querySelector('span[aria-label*="review"]') ||
                   document.querySelector('button[aria-label*="review"]');
  if (reviewEl) {
    const reviewText = reviewEl.getAttribute('aria-label') || reviewEl.textContent;
    const reviewMatch = reviewText.match(/([\d,]+)/);
    if (reviewMatch) data.review_count = parseInt(reviewMatch[1].replace(/,/g, ''));
  }

  // Extract category
  const categoryEl = document.querySelector('button[jsaction*="category"]') ||
                     document.querySelector('[class*="category"]');
  if (categoryEl) data.category = categoryEl.textContent.trim();

  // Extract coordinates from URL
  const urlMatch = window.location.href.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
  if (urlMatch) {
    data.latitude = parseFloat(urlMatch[1]);
    data.longitude = parseFloat(urlMatch[2]);
  }

  return data;
}

// Content script function: Extract all listings
function extractAllListings() {
  const listings = [];
  const linkElements = document.querySelectorAll('a[href*="/maps/place/"]');

  linkElements.forEach(link => {
    const container = link.closest('div[jsaction]');
    if (!container) return;

    const data = {
      business_name: null,
      maps_url: link.href,
      rating: null,
      review_count: null,
      category: null
    };

    // Get name from aria-label or text
    const ariaLabel = link.getAttribute('aria-label') || container.getAttribute('aria-label');
    if (ariaLabel) {
      data.business_name = ariaLabel.split('·')[0].trim();
    } else {
      const nameEl = container.querySelector('[class*="fontHeadlineSmall"]');
      if (nameEl) data.business_name = nameEl.textContent.trim();
    }

    // Get rating
    const ratingEl = container.querySelector('span[role="img"]');
    if (ratingEl) {
      const ratingText = ratingEl.getAttribute('aria-label');
      const match = ratingText?.match(/([\d.]+)/);
      if (match) data.rating = parseFloat(match[1]);
    }

    if (data.business_name) {
      listings.push(data);
    }
  });

  return listings;
}
```

**File: `chrome-extension/background/service-worker.js`**

```javascript
// MapLeads Pro Chrome Extension - Background Service Worker

// Listen for installation
chrome.runtime.onInstalled.addListener(() => {
  console.log('MapLeads Pro Extension installed');

  // Initialize storage
  chrome.storage.local.set({
    sessionCount: 0,
    sentCount: 0,
    mapleads_api_url: 'http://localhost:9000'
  });
});

// Listen for messages from content script or popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'EXTRACT_COMPLETE') {
    // Handle extraction complete notification
    console.log('Extraction complete:', message.data);
  }

  if (message.type === 'API_STATUS') {
    // Check API status
    checkAPIStatus().then(sendResponse);
    return true; // Keep channel open for async response
  }
});

async function checkAPIStatus() {
  try {
    const stored = await chrome.storage.local.get(['mapleads_api_url']);
    const apiUrl = stored.mapleads_api_url || 'http://localhost:9000';

    const response = await fetch(`${apiUrl}/api/health`);
    return { connected: response.ok };
  } catch (e) {
    return { connected: false, error: e.message };
  }
}
```

**Add API endpoint for Chrome extension imports:**

```python
# In api/routes/leads.py - Add this endpoint

@router.post("/leads/import")
async def import_leads(request: LeadImportRequest):
    """
    Import leads from external sources (Chrome extension, etc.)
    """
    try:
        imported = 0
        for lead_data in request.leads:
            # Save to database
            with db_manager.get_session() as session:
                # Check for duplicate by maps_url or place_id
                existing = None
                if lead_data.get('place_id'):
                    existing = session.query(BusinessLead).filter(
                        BusinessLead.place_id == lead_data['place_id']
                    ).first()

                if not existing and lead_data.get('maps_url'):
                    existing = session.query(BusinessLead).filter(
                        BusinessLead.maps_url == lead_data['maps_url']
                    ).first()

                if existing:
                    # Update existing
                    for key, value in lead_data.items():
                        if value is not None and hasattr(existing, key):
                            setattr(existing, key, value)
                else:
                    # Create new
                    lead = BusinessLead(
                        business_name=lead_data.get('business_name'),
                        phone=lead_data.get('phone'),
                        website=lead_data.get('website'),
                        full_address=lead_data.get('address'),
                        rating=lead_data.get('rating'),
                        review_count=lead_data.get('review_count'),
                        category=lead_data.get('category'),
                        maps_url=lead_data.get('maps_url'),
                        latitude=lead_data.get('latitude'),
                        longitude=lead_data.get('longitude'),
                        data_source='chrome_extension'
                    )
                    session.add(lead)
                    imported += 1

                session.commit()

        return {"success": True, "imported": imported}

    except Exception as e:
        logger.error(f"Lead import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Priority 4: Analytics & Differentiators

### 4.1 Review Sentiment Analysis

**New File: `utils/sentiment_analyzer.py`**

```python
"""Review sentiment analysis using TextBlob."""
from typing import Dict, List, Optional
from dataclasses import dataclass
from loguru import logger

try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False
    logger.warning("TextBlob not installed. Run: pip install textblob")


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    polarity: float  # -1.0 to 1.0 (negative to positive)
    subjectivity: float  # 0.0 to 1.0 (objective to subjective)
    sentiment: str  # "positive", "negative", "neutral"
    confidence: float  # Confidence score


class SentimentAnalyzer:
    """Analyze sentiment of reviews."""

    def __init__(self):
        if not HAS_TEXTBLOB:
            logger.error("TextBlob is required for sentiment analysis")

    def analyze_text(self, text: str) -> Optional[SentimentResult]:
        """Analyze sentiment of a single text."""
        if not HAS_TEXTBLOB or not text:
            return None

        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity

            # Determine sentiment label
            if polarity > 0.1:
                sentiment = "positive"
            elif polarity < -0.1:
                sentiment = "negative"
            else:
                sentiment = "neutral"

            # Calculate confidence based on polarity strength and subjectivity
            confidence = abs(polarity) * (1 - subjectivity * 0.5)

            return SentimentResult(
                polarity=round(polarity, 3),
                subjectivity=round(subjectivity, 3),
                sentiment=sentiment,
                confidence=round(confidence, 3)
            )
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return None

    def analyze_reviews(self, reviews: List[Dict]) -> Dict:
        """Analyze sentiment of multiple reviews."""
        if not HAS_TEXTBLOB:
            return {"error": "TextBlob not installed"}

        results = {
            "total_analyzed": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "average_polarity": 0.0,
            "average_subjectivity": 0.0,
            "sentiment_breakdown": [],
            "key_phrases": {
                "positive": [],
                "negative": []
            },
            "overall_sentiment": "neutral"
        }

        polarities = []
        subjectivities = []

        for review in reviews:
            text = review.get("review_text", "")
            if not text:
                continue

            sentiment_result = self.analyze_text(text)
            if not sentiment_result:
                continue

            results["total_analyzed"] += 1
            polarities.append(sentiment_result.polarity)
            subjectivities.append(sentiment_result.subjectivity)

            if sentiment_result.sentiment == "positive":
                results["positive_count"] += 1
            elif sentiment_result.sentiment == "negative":
                results["negative_count"] += 1
            else:
                results["neutral_count"] += 1

            # Extract key phrases
            self._extract_key_phrases(text, sentiment_result, results)

            results["sentiment_breakdown"].append({
                "review_id": review.get("review_id"),
                "rating": review.get("rating"),
                "polarity": sentiment_result.polarity,
                "sentiment": sentiment_result.sentiment
            })

        if polarities:
            results["average_polarity"] = round(sum(polarities) / len(polarities), 3)
            results["average_subjectivity"] = round(sum(subjectivities) / len(subjectivities), 3)

            # Determine overall sentiment
            if results["average_polarity"] > 0.2:
                results["overall_sentiment"] = "positive"
            elif results["average_polarity"] < -0.2:
                results["overall_sentiment"] = "negative"
            else:
                results["overall_sentiment"] = "mixed"

        return results

    def _extract_key_phrases(self, text: str, sentiment: SentimentResult, results: Dict):
        """Extract key phrases from text."""
        try:
            blob = TextBlob(text)
            noun_phrases = blob.noun_phrases[:5]  # Top 5 phrases

            category = "positive" if sentiment.sentiment == "positive" else "negative"

            for phrase in noun_phrases:
                if phrase and len(phrase) > 2:
                    if phrase not in results["key_phrases"][category]:
                        results["key_phrases"][category].append(phrase)

                        # Keep only top 10 per category
                        if len(results["key_phrases"][category]) > 10:
                            results["key_phrases"][category] = results["key_phrases"][category][:10]
        except:
            pass

    def get_sentiment_score(self, reviews: List[Dict]) -> int:
        """Get a simple 0-100 sentiment score for reviews."""
        analysis = self.analyze_reviews(reviews)

        if analysis.get("error") or analysis["total_analyzed"] == 0:
            return 50  # Default neutral

        # Convert polarity (-1 to 1) to score (0 to 100)
        score = int((analysis["average_polarity"] + 1) * 50)
        return max(0, min(100, score))


# Singleton instance
sentiment_analyzer = SentimentAnalyzer()
```

**Add API endpoint:**

```python
# In api/routes/analytics.py

@router.post("/analytics/sentiment/{lead_id}")
async def analyze_lead_sentiment(lead_id: int):
    """Analyze sentiment of reviews for a specific lead."""
    from utils.sentiment_analyzer import sentiment_analyzer

    with db_manager.get_session() as session:
        lead = session.query(BusinessLead).filter(BusinessLead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Get reviews (if stored)
        reviews = lead.reviews if hasattr(lead, 'reviews') and lead.reviews else []

        if not reviews:
            return {"error": "No reviews available for analysis"}

        analysis = sentiment_analyzer.analyze_reviews(reviews)
        return analysis
```

---

### 4.2 Competitor Comparison Feature

**New File: `utils/competitor_comparison.py`**

```python
"""Competitor comparison analysis."""
from typing import List, Dict, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class ComparisonMetric:
    """Single comparison metric."""
    name: str
    values: Dict[str, any]  # business_name -> value
    winner: Optional[str] = None
    insight: Optional[str] = None


class CompetitorComparator:
    """Compare multiple businesses side-by-side."""

    COMPARISON_FIELDS = [
        ("rating", "Rating", "higher_better"),
        ("review_count", "Reviews", "higher_better"),
        ("data_quality_score", "Data Quality", "higher_better"),
        ("employees_min", "Employees", "info_only"),
        ("founded_year", "Founded", "info_only"),
    ]

    def compare_businesses(self, leads: List[Dict]) -> Dict:
        """Compare multiple businesses."""
        if len(leads) < 2:
            return {"error": "Need at least 2 businesses to compare"}

        comparison = {
            "businesses": [l.get("business_name") for l in leads],
            "metrics": [],
            "winner_summary": {},
            "insights": []
        }

        winner_counts = {l.get("business_name"): 0 for l in leads}

        for field, label, comparison_type in self.COMPARISON_FIELDS:
            values = {}
            for lead in leads:
                name = lead.get("business_name")
                value = lead.get(field)
                values[name] = value

            metric = ComparisonMetric(name=label, values=values)

            # Determine winner if applicable
            if comparison_type == "higher_better":
                valid_values = {k: v for k, v in values.items() if v is not None}
                if valid_values:
                    winner = max(valid_values, key=valid_values.get)
                    metric.winner = winner
                    winner_counts[winner] += 1

                    # Generate insight
                    best_val = valid_values[winner]
                    others = [v for k, v in valid_values.items() if k != winner]
                    if others:
                        avg_others = sum(others) / len(others)
                        if avg_others > 0:
                            pct_better = ((best_val - avg_others) / avg_others) * 100
                            metric.insight = f"{winner} has {pct_better:.0f}% higher {label.lower()}"

            comparison["metrics"].append({
                "name": metric.name,
                "values": metric.values,
                "winner": metric.winner,
                "insight": metric.insight
            })

        # Social media comparison
        social_fields = ["social_facebook", "social_instagram", "social_linkedin", "social_twitter"]
        social_counts = {}
        for lead in leads:
            name = lead.get("business_name")
            count = sum(1 for f in social_fields if lead.get(f))
            social_counts[name] = count

        comparison["metrics"].append({
            "name": "Social Media Presence",
            "values": social_counts,
            "winner": max(social_counts, key=social_counts.get) if social_counts else None
        })

        # Contact info comparison
        contact_scores = {}
        for lead in leads:
            name = lead.get("business_name")
            score = 0
            if lead.get("email"): score += 1
            if lead.get("phone"): score += 1
            if lead.get("website"): score += 1
            if lead.get("contact_name_1"): score += 1
            contact_scores[name] = score

        comparison["metrics"].append({
            "name": "Contact Completeness",
            "values": contact_scores,
            "winner": max(contact_scores, key=contact_scores.get) if contact_scores else None
        })

        # Determine overall winner
        comparison["winner_summary"] = dict(sorted(
            winner_counts.items(),
            key=lambda x: x[1],
            reverse=True
        ))

        overall_winner = max(winner_counts, key=winner_counts.get)
        comparison["overall_winner"] = overall_winner
        comparison["insights"].append(
            f"{overall_winner} wins in the most categories ({winner_counts[overall_winner]})"
        )

        return comparison


# Singleton
competitor_comparator = CompetitorComparator()
```

**Add API endpoint:**

```python
# In api/routes/analytics.py

@router.post("/analytics/compare")
async def compare_competitors(lead_ids: List[int]):
    """Compare multiple businesses side-by-side."""
    from utils.competitor_comparison import competitor_comparator

    if len(lead_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 leads to compare")

    if len(lead_ids) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 leads for comparison")

    with db_manager.get_session() as session:
        leads = session.query(BusinessLead).filter(
            BusinessLead.id.in_(lead_ids)
        ).all()

        if len(leads) < 2:
            raise HTTPException(status_code=404, detail="Not enough leads found")

        lead_dicts = [lead.to_dict() for lead in leads]
        comparison = competitor_comparator.compare_businesses(lead_dicts)
        return comparison
```

---

### 4.3 Data Freshness Tracking

**Update database model:**

```python
# In database/models.py - Add to BusinessLead

# Data Freshness
last_verified_at = Column(DateTime, nullable=True)
verification_count = Column(Integer, default=0)
data_changed = Column(Boolean, default=False)  # Changed since last scrape
change_history = Column(JSON, nullable=True)  # Track what changed
```

**New File: `utils/data_freshness.py`**

```python
"""Data freshness tracking and verification."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger


class DataFreshnessTracker:
    """Track data freshness and verification status."""

    FRESHNESS_THRESHOLDS = {
        "fresh": timedelta(days=7),
        "recent": timedelta(days=30),
        "stale": timedelta(days=90),
    }

    def get_freshness_status(self, lead: Dict) -> Dict:
        """Get freshness status for a lead."""
        scraped_at = lead.get("scraped_at")
        last_verified = lead.get("last_verified_at")

        if not scraped_at:
            return {"status": "unknown", "days_old": None}

        # Parse datetime if string
        if isinstance(scraped_at, str):
            scraped_at = datetime.fromisoformat(scraped_at.replace('Z', '+00:00'))

        age = datetime.utcnow() - scraped_at

        if age <= self.FRESHNESS_THRESHOLDS["fresh"]:
            status = "fresh"
        elif age <= self.FRESHNESS_THRESHOLDS["recent"]:
            status = "recent"
        elif age <= self.FRESHNESS_THRESHOLDS["stale"]:
            status = "stale"
        else:
            status = "outdated"

        return {
            "status": status,
            "days_old": age.days,
            "scraped_at": scraped_at.isoformat() if scraped_at else None,
            "last_verified_at": last_verified.isoformat() if last_verified else None,
            "needs_refresh": status in ("stale", "outdated")
        }

    def compare_and_track_changes(
        self,
        old_data: Dict,
        new_data: Dict,
        tracked_fields: List[str] = None
    ) -> Dict:
        """Compare old and new data, track changes."""
        if tracked_fields is None:
            tracked_fields = [
                "phone", "email", "website", "rating", "review_count",
                "full_address", "category", "is_open_now"
            ]

        changes = {
            "has_changes": False,
            "changed_fields": [],
            "field_changes": {}
        }

        for field in tracked_fields:
            old_val = old_data.get(field)
            new_val = new_data.get(field)

            if old_val != new_val:
                changes["has_changes"] = True
                changes["changed_fields"].append(field)
                changes["field_changes"][field] = {
                    "old": old_val,
                    "new": new_val
                }

        return changes

    def get_batch_freshness_stats(self, leads: List[Dict]) -> Dict:
        """Get freshness statistics for a batch of leads."""
        stats = {
            "total": len(leads),
            "fresh": 0,
            "recent": 0,
            "stale": 0,
            "outdated": 0,
            "unknown": 0,
            "needs_refresh_count": 0,
            "average_age_days": 0
        }

        ages = []

        for lead in leads:
            freshness = self.get_freshness_status(lead)
            status = freshness["status"]
            stats[status] += 1

            if freshness.get("needs_refresh"):
                stats["needs_refresh_count"] += 1

            if freshness.get("days_old") is not None:
                ages.append(freshness["days_old"])

        if ages:
            stats["average_age_days"] = sum(ages) / len(ages)

        return stats


# Singleton
freshness_tracker = DataFreshnessTracker()
```

---

### 4.4 Cold Email Template Generator

**New File: `utils/email_templates.py`**

```python
"""Cold email template generator using scraped data."""
from typing import Dict, List, Optional
from dataclasses import dataclass
import re


@dataclass
class EmailTemplate:
    """Generated email template."""
    subject: str
    body: str
    personalization_score: int  # 0-100


class ColdEmailGenerator:
    """Generate personalized cold email templates."""

    TEMPLATES = {
        "introduction": {
            "subject": "Quick question for {business_name}",
            "body": """Hi{contact_name_greeting},

I came across {business_name} while researching {category_lower} in {city_state} and was impressed by your {rating_text}.

{personalization_line}

I help businesses like yours {value_prop}. Would you be open to a quick 15-minute call this week to see if we might be a fit?

Best regards,
[Your Name]

P.S. {ps_line}"""
        },
        "value_focused": {
            "subject": "Idea for {business_name}",
            "body": """Hi{contact_name_greeting},

I noticed {business_name} has {review_count_text} on Google Maps - that's great social proof!

{personalization_line}

Many {category_lower} businesses I work with have found that {value_prop}. I'd love to share some specific ideas for {business_name}.

Do you have 15 minutes this week for a quick chat?

Best,
[Your Name]"""
        },
        "local_focused": {
            "subject": "Fellow {city} business owner here",
            "body": """Hi{contact_name_greeting},

As a fellow {city} business, I wanted to reach out to {business_name} about {value_prop}.

{personalization_line}

I've helped several local businesses in the {category_lower} space, and I think there's a great opportunity for collaboration.

Would you be interested in grabbing a coffee or having a quick call?

Cheers,
[Your Name]"""
        }
    }

    VALUE_PROPS = {
        "default": "improve their online presence and get more customers",
        "restaurant": "increase reservations and foot traffic",
        "hotel": "boost direct bookings and reduce OTA dependency",
        "retail": "drive more in-store visits and online sales",
        "service": "generate more qualified leads and appointments",
        "medical": "attract more patients while maintaining compliance",
    }

    def generate_email(
        self,
        lead: Dict,
        template_name: str = "introduction",
        value_prop: Optional[str] = None
    ) -> EmailTemplate:
        """Generate a cold email template from lead data."""
        template = self.TEMPLATES.get(template_name, self.TEMPLATES["introduction"])

        # Extract and format data
        business_name = lead.get("business_name", "your business")
        category = lead.get("category", "business")
        city = lead.get("city", "your area")
        state = lead.get("state", "")
        rating = lead.get("rating")
        review_count = lead.get("review_count", 0)
        contact_name = lead.get("contact_name_1")

        # Build replacements
        replacements = {
            "business_name": business_name,
            "category_lower": category.lower() if category else "business",
            "city": city,
            "city_state": f"{city}, {state}" if state else city,
            "contact_name_greeting": f" {contact_name.split()[0]}" if contact_name else "",
        }

        # Rating text
        if rating and rating >= 4.5:
            replacements["rating_text"] = f"stellar {rating}-star rating"
        elif rating and rating >= 4.0:
            replacements["rating_text"] = f"strong {rating}-star rating"
        else:
            replacements["rating_text"] = "reputation in the area"

        # Review count text
        if review_count and review_count >= 100:
            replacements["review_count_text"] = f"over {review_count} reviews"
        elif review_count and review_count >= 50:
            replacements["review_count_text"] = f"{review_count} positive reviews"
        else:
            replacements["review_count_text"] = "great reviews"

        # Value proposition
        if value_prop:
            replacements["value_prop"] = value_prop
        else:
            # Try to match category to value prop
            category_lower = category.lower() if category else ""
            for key, prop in self.VALUE_PROPS.items():
                if key in category_lower:
                    replacements["value_prop"] = prop
                    break
            else:
                replacements["value_prop"] = self.VALUE_PROPS["default"]

        # Personalization line based on available data
        personalization_lines = []
        if lead.get("founded_year"):
            years = 2025 - lead["founded_year"]
            if years > 10:
                personalization_lines.append(
                    f"I see you've been serving {city} for over {years} years - that's impressive longevity!"
                )
        if lead.get("social_instagram"):
            personalization_lines.append(
                "I checked out your Instagram and love the content you're putting out."
            )
        if lead.get("employees") and "50" in str(lead.get("employees")):
            personalization_lines.append(
                "As a growing team, you're probably always looking for ways to scale efficiently."
            )

        replacements["personalization_line"] = (
            personalization_lines[0] if personalization_lines
            else f"Based on what I see, {business_name} is doing great work in the community."
        )

        # PS line
        ps_lines = [
            "Feel free to check out my work at [your website]",
            "I'm happy to share case studies from similar businesses",
            "Even if the timing isn't right now, I'd love to connect"
        ]
        replacements["ps_line"] = ps_lines[hash(business_name) % len(ps_lines)]

        # Apply replacements
        subject = template["subject"]
        body = template["body"]

        for key, value in replacements.items():
            placeholder = "{" + key + "}"
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))

        # Calculate personalization score
        score = self._calculate_personalization_score(lead, replacements)

        return EmailTemplate(
            subject=subject,
            body=body,
            personalization_score=score
        )

    def _calculate_personalization_score(self, lead: Dict, replacements: Dict) -> int:
        """Calculate how personalized the email is."""
        score = 30  # Base score

        # Contact name available
        if lead.get("contact_name_1"):
            score += 20

        # Has rating
        if lead.get("rating"):
            score += 10

        # Has review count
        if lead.get("review_count"):
            score += 10

        # Has founded year
        if lead.get("founded_year"):
            score += 10

        # Has social media
        if any(lead.get(f"social_{s}") for s in ["instagram", "facebook", "linkedin"]):
            score += 10

        # Has city/location
        if lead.get("city"):
            score += 10

        return min(100, score)

    def generate_batch(
        self,
        leads: List[Dict],
        template_name: str = "introduction"
    ) -> List[Dict]:
        """Generate emails for multiple leads."""
        results = []

        for lead in leads:
            email = self.generate_email(lead, template_name)
            results.append({
                "business_name": lead.get("business_name"),
                "email_address": lead.get("email"),
                "subject": email.subject,
                "body": email.body,
                "personalization_score": email.personalization_score
            })

        return results


# Singleton
email_generator = ColdEmailGenerator()
```

**Add API endpoint:**

```python
# In api/routes/export.py

@router.post("/export/email-templates")
async def generate_email_templates(
    lead_ids: List[int],
    template_name: str = "introduction",
    value_prop: Optional[str] = None
):
    """Generate cold email templates for specified leads."""
    from utils.email_templates import email_generator

    with db_manager.get_session() as session:
        leads = session.query(BusinessLead).filter(
            BusinessLead.id.in_(lead_ids)
        ).all()

        if not leads:
            raise HTTPException(status_code=404, detail="No leads found")

        lead_dicts = [lead.to_dict() for lead in leads]
        templates = email_generator.generate_batch(lead_dicts, template_name)

        return {
            "templates": templates,
            "total": len(templates)
        }
```

---

## Priority 5: Export Enhancements

### 5.1 Cloud Storage Upload (S3/GCS)

**New File: `utils/cloud_storage.py`**

```python
"""Cloud storage upload for S3 and Google Cloud Storage."""
import os
from typing import Optional
from dataclasses import dataclass
from loguru import logger

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    from google.cloud import storage as gcs
    HAS_GCS = True
except ImportError:
    HAS_GCS = False


@dataclass
class UploadResult:
    """Result of cloud upload."""
    success: bool
    url: Optional[str] = None
    error: Optional[str] = None


class CloudStorageManager:
    """Manage uploads to cloud storage services."""

    def __init__(self):
        self.s3_client = None
        self.gcs_client = None

    def init_s3(
        self,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1"
    ):
        """Initialize S3 client."""
        if not HAS_BOTO3:
            raise ImportError("boto3 is required for S3 uploads. Run: pip install boto3")

        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

    def init_gcs(self, credentials_path: str):
        """Initialize Google Cloud Storage client."""
        if not HAS_GCS:
            raise ImportError("google-cloud-storage is required. Run: pip install google-cloud-storage")

        self.gcs_client = gcs.Client.from_service_account_json(credentials_path)

    def upload_to_s3(
        self,
        file_path: str,
        bucket: str,
        key: Optional[str] = None,
        make_public: bool = False
    ) -> UploadResult:
        """Upload file to S3."""
        if not self.s3_client:
            return UploadResult(success=False, error="S3 client not initialized")

        try:
            if key is None:
                key = os.path.basename(file_path)

            extra_args = {}
            if make_public:
                extra_args['ACL'] = 'public-read'

            # Determine content type
            if file_path.endswith('.csv'):
                extra_args['ContentType'] = 'text/csv'
            elif file_path.endswith('.xlsx'):
                extra_args['ContentType'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif file_path.endswith('.json'):
                extra_args['ContentType'] = 'application/json'

            self.s3_client.upload_file(
                file_path,
                bucket,
                key,
                ExtraArgs=extra_args if extra_args else None
            )

            # Generate URL
            if make_public:
                url = f"https://{bucket}.s3.amazonaws.com/{key}"
            else:
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': key},
                    ExpiresIn=86400  # 24 hours
                )

            logger.info(f"Uploaded to S3: {key}")
            return UploadResult(success=True, url=url)

        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            return UploadResult(success=False, error=str(e))

    def upload_to_gcs(
        self,
        file_path: str,
        bucket: str,
        blob_name: Optional[str] = None,
        make_public: bool = False
    ) -> UploadResult:
        """Upload file to Google Cloud Storage."""
        if not self.gcs_client:
            return UploadResult(success=False, error="GCS client not initialized")

        try:
            if blob_name is None:
                blob_name = os.path.basename(file_path)

            bucket_obj = self.gcs_client.bucket(bucket)
            blob = bucket_obj.blob(blob_name)

            # Upload
            blob.upload_from_filename(file_path)

            if make_public:
                blob.make_public()
                url = blob.public_url
            else:
                # Generate signed URL
                from datetime import timedelta
                url = blob.generate_signed_url(expiration=timedelta(hours=24))

            logger.info(f"Uploaded to GCS: {blob_name}")
            return UploadResult(success=True, url=url)

        except Exception as e:
            logger.error(f"GCS upload failed: {e}")
            return UploadResult(success=False, error=str(e))


# Singleton
cloud_storage = CloudStorageManager()
```

**Add settings:**

```python
# In config/settings.py

# AWS S3
aws_access_key: Optional[str] = None
aws_secret_key: Optional[str] = None
aws_region: str = "us-east-1"
s3_bucket: Optional[str] = None

# Google Cloud Storage
gcs_credentials_path: Optional[str] = None
gcs_bucket: Optional[str] = None
```

---

### 5.2 Optimized Export Formats

**Update `utils/exporter.py`:**

```python
def export_cold_calling_csv(leads: List[Dict], filepath: str) -> str:
    """Export in optimized format for cold calling campaigns."""
    import csv

    # Cold calling prioritizes: name, phone, best time to call, notes
    columns = [
        "company_name",
        "primary_phone",
        "secondary_phone",
        "contact_name",
        "contact_title",
        "city",
        "state",
        "category",
        "rating",
        "best_call_time",  # Derived from popular_times if available
        "call_notes",  # Generated notes
    ]

    rows = []
    for lead in leads:
        # Generate call notes
        notes = []
        if lead.get("rating"):
            notes.append(f"{lead['rating']}* rating")
        if lead.get("review_count"):
            notes.append(f"{lead['review_count']} reviews")
        if lead.get("founded_year"):
            notes.append(f"Est. {lead['founded_year']}")

        # Determine best call time from popular_times
        best_time = "Business hours"
        popular_times = lead.get("popular_times")
        if popular_times and popular_times.get("quietest_hour"):
            best_time = f"{popular_times['quietest_day']} {popular_times['quietest_hour']} (typically quieter)"

        rows.append({
            "company_name": lead.get("business_name"),
            "primary_phone": lead.get("phone"),
            "secondary_phone": lead.get("phone_2"),
            "contact_name": lead.get("contact_name_1"),
            "contact_title": lead.get("contact_title_1"),
            "city": lead.get("city"),
            "state": lead.get("state"),
            "category": lead.get("category"),
            "rating": lead.get("rating"),
            "best_call_time": best_time,
            "call_notes": " | ".join(notes)
        })

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    return filepath


def export_email_campaign_csv(leads: List[Dict], filepath: str) -> str:
    """Export in optimized format for email campaigns."""
    import csv

    # Email campaign prioritizes: email, personalization fields
    columns = [
        "email",
        "first_name",
        "last_name",
        "company",
        "title",
        "city",
        "state",
        "industry",
        "company_size",
        "rating",
        "website",
        "linkedin",
        "personalization_note",
    ]

    rows = []
    for lead in leads:
        # Get best email
        email = (lead.get("contact_email_1") or
                 lead.get("email") or
                 lead.get("email_1"))

        if not email:
            continue  # Skip leads without email for email campaigns

        # Parse contact name
        contact_name = lead.get("contact_name_1", "")
        parts = contact_name.split() if contact_name else []
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        # Generate personalization note
        pers_notes = []
        if lead.get("rating") and lead["rating"] >= 4.5:
            pers_notes.append(f"Excellent {lead['rating']}* rating")
        if lead.get("founded_year") and (2025 - lead["founded_year"]) > 10:
            pers_notes.append(f"Established business ({lead['founded_year']})")
        if lead.get("review_count") and lead["review_count"] > 100:
            pers_notes.append(f"Well-reviewed ({lead['review_count']}+ reviews)")

        rows.append({
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "company": lead.get("business_name"),
            "title": lead.get("contact_title_1", ""),
            "city": lead.get("city"),
            "state": lead.get("state"),
            "industry": lead.get("category"),
            "company_size": lead.get("employees", ""),
            "rating": lead.get("rating"),
            "website": lead.get("website"),
            "linkedin": lead.get("social_linkedin"),
            "personalization_note": " | ".join(pers_notes)
        })

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    return filepath
```

---

## Configuration Updates

**Complete `config/settings.py` additions:**

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # ==================== NEW FEATURE TOGGLES ====================

    # Proxy Manager Integration
    use_proxy_manager: bool = False
    proxy_refresh_interval: int = 3600
    proxy_test_count: int = 20

    # Webhook Notifications
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    webhook_enabled: bool = False
    webhook_events: str = "job.completed,lead.created"  # Comma-separated

    # Cloud Storage
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_region: str = "us-east-1"
    s3_bucket: Optional[str] = None
    gcs_credentials_path: Optional[str] = None
    gcs_bucket: Optional[str] = None

    # Sentiment Analysis
    sentiment_analysis_enabled: bool = False

    # Data Freshness
    data_freshness_threshold_days: int = 30
    auto_refresh_stale_data: bool = False

    # Chrome Extension
    chrome_extension_enabled: bool = True
    chrome_extension_api_key: Optional[str] = None  # For authentication

    @property
    def webhook_events_list(self) -> List[str]:
        """Get webhook events as list."""
        return [e.strip() for e in self.webhook_events.split(",")]

    def get_new_features_status(self) -> dict:
        """Get status of all new features."""
        return {
            "proxy_manager": {
                "enabled": self.use_proxy_manager
            },
            "captcha_solver": {
                "enabled": self.captcha_enabled,
                "configured": bool(self.captcha_api_key)
            },
            "webhooks": {
                "enabled": self.webhook_enabled,
                "configured": bool(self.webhook_url)
            },
            "cloud_storage": {
                "s3_configured": bool(self.aws_access_key and self.s3_bucket),
                "gcs_configured": bool(self.gcs_credentials_path and self.gcs_bucket)
            },
            "sentiment_analysis": {
                "enabled": self.sentiment_analysis_enabled
            },
            "chrome_extension": {
                "enabled": self.chrome_extension_enabled
            }
        }
```

---

## Database Migrations

**Add migration for new fields:**

```python
# File: database/migrations/add_new_features.py

"""Add columns for new features."""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Popular times columns
    op.add_column('business_leads', sa.Column('popular_times', sa.JSON, nullable=True))
    op.add_column('business_leads', sa.Column('busiest_day', sa.String(20), nullable=True))
    op.add_column('business_leads', sa.Column('busiest_hour', sa.String(20), nullable=True))
    op.add_column('business_leads', sa.Column('typical_time_spent', sa.String(50), nullable=True))
    op.add_column('business_leads', sa.Column('live_busyness', sa.Integer, nullable=True))

    # Photo columns
    op.add_column('business_leads', sa.Column('photos', sa.JSON, nullable=True))
    op.add_column('business_leads', sa.Column('photo_count', sa.Integer, nullable=True))
    op.add_column('business_leads', sa.Column('main_photo', sa.String(1000), nullable=True))

    # Data freshness columns
    op.add_column('business_leads', sa.Column('last_verified_at', sa.DateTime, nullable=True))
    op.add_column('business_leads', sa.Column('verification_count', sa.Integer, default=0))
    op.add_column('business_leads', sa.Column('data_changed', sa.Boolean, default=False))
    op.add_column('business_leads', sa.Column('change_history', sa.JSON, nullable=True))

    # Sentiment analysis columns
    op.add_column('business_leads', sa.Column('sentiment_score', sa.Integer, nullable=True))
    op.add_column('business_leads', sa.Column('sentiment_analysis', sa.JSON, nullable=True))


def downgrade():
    # Remove all added columns
    columns = [
        'popular_times', 'busiest_day', 'busiest_hour', 'typical_time_spent',
        'live_busyness', 'photos', 'photo_count', 'main_photo',
        'last_verified_at', 'verification_count', 'data_changed', 'change_history',
        'sentiment_score', 'sentiment_analysis'
    ]
    for col in columns:
        op.drop_column('business_leads', col)
```

---

## API Router Updates

**Update `api/app.py` to include new routers:**

```python
from api.routes.bulk_import import router as bulk_import_router
from api.routes.webhooks import router as webhooks_router

def create_app() -> FastAPI:
    # ... existing code ...

    # Include new routers
    app.include_router(bulk_import_router, prefix="/api", tags=["Import"])
    app.include_router(webhooks_router, prefix="/api", tags=["Webhooks"])

    # ... rest of code ...
```

---

## Testing Checklist

For each feature, ensure:

- [ ] Unit tests for core logic
- [ ] Integration tests with existing code
- [ ] API endpoint tests
- [ ] Error handling tests
- [ ] Settings toggle works (feature can be disabled)

---

## Implementation Order

1. **Week 1: Priority 1** - Integrate existing code
   - Wire proxy_manager.py
   - Wire captcha_solver.py
   - Complete review extraction
   - Verify popular_times integration

2. **Week 2: Priority 2** - New core features
   - Geo-coordinate search
   - Bulk URL import
   - Photo extraction
   - Webhook notifications

3. **Week 3: Priority 3** - Chrome extension
   - Build extension
   - Test with local API
   - Document installation

4. **Week 4: Priority 4** - Analytics
   - Sentiment analysis
   - Competitor comparison
   - Data freshness
   - Email templates

5. **Week 5: Priority 5** - Export enhancements
   - Cloud storage upload
   - Optimized export formats
   - Testing and polish

---

## Notes

- All new code follows existing patterns (singleton extractors, Pydantic schemas, FastAPI routers)
- Each feature is toggleable via settings
- Error handling ensures graceful degradation if a feature fails
- Backward compatibility maintained for all existing endpoints
