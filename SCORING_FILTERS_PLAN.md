# MapLeads Pro - Lead Scoring (1-5 Stars) & Scrape Filters Plan

## Executive Summary

This document provides a complete gap analysis and implementation plan for:
1. **Logic-Based Lead Scoring System (1-5 Stars)** - Rate leads based on website, social media, contact info quality
2. **Logic-Based Scrape Filters** - Filter during scraping to get better quality leads

---

# PART 1: GAP ANALYSIS

## A. Lead Scoring System (1-5 Stars)

### What ALREADY EXISTS in `utils/lead_scoring.py`

| Feature | Status | Details |
|---------|--------|---------|
| `LeadScorer` class | EXISTS | Lines 77-167 |
| Weighted scoring (0-100 scale) | EXISTS | 6 categories with weights |
| Contact info scoring | EXISTS | Phone +40pts, Email +30pts, Website +10pts |
| Business email bonus | EXISTS | +10pts for non-gmail/yahoo emails |
| Data completeness check | EXISTS | Checks 10 fields |
| Social media presence check | EXISTS | Checks for social links |
| Rating/reputation scoring | EXISTS | Uses Google rating & review count |
| Grade system (A+ to F) | EXISTS | `_calculate_grade()` method |
| `ScoringWeights` dataclass | EXISTS | Customizable weights |
| Strengths/weaknesses analysis | EXISTS | Auto-identifies lead quality |
| Recommendations generation | EXISTS | Suggests best approach |

### What is MISSING for 1-5 Star System

| Feature | Status | What Needs to Be Done |
|---------|--------|----------------------|
| **Star conversion (0-100 to 1-5)** | MISSING | Add `score_to_stars()` method |
| **Star rating in database** | MISSING | Add `star_rating` column to BusinessLead |
| **Star display in UI** | MISSING | Add star icons to leads table |
| **Star filter dropdown** | MISSING | Filter leads by star rating |
| **Website quality scoring** | PARTIAL | Expand to check SSL, mobile-friendly |
| **Social media completeness** | PARTIAL | Count how many social platforms |
| **Quick visual badges** | MISSING | Color-coded star badges |
| **Star in lead details** | MISSING | Show in detail modal |

---

## B. Logic-Based Scrape Filters

### What ALREADY EXISTS in `api/schemas/requests.py`

| Filter | Status | Location |
|--------|--------|----------|
| `LeadFilters` class | EXISTS | Lines 83-124 |
| City/State/Country/Pincode | EXISTS | Location-based filtering |
| `has_email` | EXISTS | Boolean filter |
| `has_phone` | EXISTS | Boolean filter |
| `has_website` | EXISTS | Boolean filter |
| `has_facebook` | EXISTS | Boolean filter |
| `has_instagram` | EXISTS | Boolean filter |
| `has_linkedin` | EXISTS | Boolean filter |
| `min_rating` / `max_rating` | EXISTS | 0-5 range |
| `min_reviews` / `max_reviews` | EXISTS | Review count range |
| `min_quality` | EXISTS | Quality score threshold |
| `search` (text search) | EXISTS | Name/address search |
| `job_id` filter | EXISTS | Filter by scrape job |
| Date filters | EXISTS | scraped_after/before |

### What is MISSING for Scrape Filters

| Feature | Status | What Needs to Be Done |
|---------|--------|----------------------|
| **PRE-SCRAPE Filters** | MISSING | Apply filters DURING scraping (not after) |
| **Filter UI in scrape form** | MISSING | Add filter controls to New Scrape page |
| **Compound logic (AND/OR)** | MISSING | "Has 5 stars AND no website" |
| **Star rating filter** | MISSING | Filter by calculated star rating |
| **"Missing" opportunity filters** | MISSING | `missing_website`, `missing_social` |
| **Industry filter presets** | MISSING | Pre-configured filter templates |
| **Save/load filter templates** | MISSING | Custom filter configurations |
| **Real-time preview count** | MISSING | Show estimated matching count |
| **Filter processor module** | MISSING | `utils/scrape_filters.py` |

---

# PART 2: IMPLEMENTATION PLAN

## Phase 1: Star Rating Backend

### Task 1.1: Add Star Conversion Method
**File:** `utils/lead_scoring.py`

Add these methods to the `LeadScorer` class:

```python
def score_to_stars(self, score: float) -> int:
    """
    Convert 0-100 quality score to 1-5 star rating.

    Thresholds:
    - 5 Stars: 85-100 (Excellent - high conversion potential)
    - 4 Stars: 70-84 (Good - worth pursuing)
    - 3 Stars: 50-69 (Average - may need nurturing)
    - 2 Stars: 30-49 (Below average - low priority)
    - 1 Star: 0-29 (Poor - consider skipping)
    """
    if score >= 85:
        return 5
    elif score >= 70:
        return 4
    elif score >= 50:
        return 3
    elif score >= 30:
        return 2
    else:
        return 1

def get_star_description(self, stars: int) -> dict:
    """Get detailed description for star rating."""
    descriptions = {
        5: {
            "label": "Excellent Lead",
            "color": "success",
            "description": "High conversion potential - prioritize outreach",
            "suggested_action": "Call immediately"
        },
        4: {
            "label": "Good Lead",
            "color": "info",
            "description": "Worth pursuing - has good business presence",
            "suggested_action": "Send personalized email"
        },
        3: {
            "label": "Average Lead",
            "color": "warning",
            "description": "May need nurturing - incomplete data",
            "suggested_action": "Add to nurture sequence"
        },
        2: {
            "label": "Below Average",
            "color": "secondary",
            "description": "Low priority - limited contact info",
            "suggested_action": "Research more before contact"
        },
        1: {
            "label": "Poor Lead",
            "color": "danger",
            "description": "Consider skipping - minimal data",
            "suggested_action": "Skip or bulk campaign only"
        }
    }
    return descriptions.get(stars, descriptions[1])
```

### Task 1.2: Update calculate_score Method
**File:** `utils/lead_scoring.py`

Modify the return value to include stars:

```python
# In calculate_score method, before return:
stars = self.score_to_stars(scores["overall_score"])
star_info = self.get_star_description(stars)

scores["stars"] = stars
scores["star_label"] = star_info["label"]
scores["star_color"] = star_info["color"]
scores["suggested_action"] = star_info["suggested_action"]

return scores
```

### Task 1.3: Add Database Column
**File:** `database/models.py`

Add to BusinessLead model:
```python
star_rating = Column(Integer, default=0, index=True)
```

### Task 1.4: Create Migration Script
**File:** `migrate_star_rating.py`

```python
"""Add star_rating column to business_leads table."""
from database import db_manager
from sqlalchemy import text

def migrate():
    with db_manager.get_session() as session:
        try:
            session.execute(text(
                "ALTER TABLE business_leads ADD COLUMN star_rating INTEGER DEFAULT 0"
            ))
            session.commit()
            print("Migration successful: star_rating column added")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("Column already exists")
            else:
                raise

if __name__ == "__main__":
    migrate()
```

---

## Phase 2: Star Rating Frontend

### Task 2.1: Add Star Display Functions
**File:** `frontend/app.js`

```javascript
// Render star icons
function renderStars(rating, size = 'sm') {
    const sizeClass = size === 'lg' ? 'fa-lg' : '';
    let html = '';
    for (let i = 1; i <= 5; i++) {
        if (i <= rating) {
            html += `<i class="fas fa-star text-warning ${sizeClass}"></i>`;
        } else {
            html += `<i class="far fa-star text-muted ${sizeClass}"></i>`;
        }
    }
    return html;
}

// Get colored badge for star rating
function getStarBadge(rating) {
    const config = {
        5: { color: 'success', label: 'Excellent' },
        4: { color: 'info', label: 'Good' },
        3: { color: 'warning', label: 'Average' },
        2: { color: 'secondary', label: 'Below Avg' },
        1: { color: 'danger', label: 'Poor' },
        0: { color: 'dark', label: 'Unrated' }
    };
    const c = config[rating] || config[0];
    return `<span class="badge bg-${c.color}" title="${c.label}">
        ${renderStars(rating)}
    </span>`;
}
```

### Task 2.2: Update Leads Table
**File:** `frontend/index.html`

Add "Rating" column header:
```html
<th>Quality</th>
```

In the table row template:
```html
<td>${getStarBadge(lead.star_rating || 0)}</td>
```

### Task 2.3: Add Star Filter
**File:** `frontend/index.html`

Add filter dropdown:
```html
<div class="col-auto">
    <select id="starFilter" class="form-select form-select-sm" onchange="loadLeads()">
        <option value="">All Ratings</option>
        <option value="5">5 Stars Only</option>
        <option value="4">4+ Stars</option>
        <option value="3">3+ Stars</option>
        <option value="2">2+ Stars</option>
    </select>
</div>
```

### Task 2.4: Update Lead Details Modal
Add star display in lead details view.

---

## Phase 3: Pre-Scrape Filters Backend

### Task 3.1: Create ScrapeFilters Schema
**File:** `api/schemas/requests.py`

```python
class ScrapeFilters(BaseModel):
    """Filters to apply during scraping."""

    # Google Rating Filters
    min_google_rating: Optional[float] = Field(None, ge=1.0, le=5.0,
        description="Minimum Google Maps rating (1-5)")
    max_google_rating: Optional[float] = Field(None, ge=1.0, le=5.0,
        description="Maximum Google Maps rating")

    # Review Count Filters
    min_review_count: Optional[int] = Field(None, ge=0,
        description="Minimum number of reviews")
    max_review_count: Optional[int] = Field(None,
        description="Maximum number of reviews")

    # Contact Requirements (MUST HAVE)
    require_phone: bool = Field(False,
        description="Only include if has phone number")
    require_website: bool = Field(False,
        description="Only include if has website")
    require_email: bool = Field(False,
        description="Only include if has email (requires website scraping)")

    # Opportunity Filters (MUST NOT HAVE - find opportunities)
    missing_website: bool = Field(False,
        description="Only include businesses WITHOUT a website")
    missing_social_media: bool = Field(False,
        description="Only include businesses WITHOUT social media")
    missing_email: bool = Field(False,
        description="Only include businesses WITHOUT email")

    # Social Media Requirements
    require_facebook: bool = Field(False)
    require_instagram: bool = Field(False)
    require_linkedin: bool = Field(False)
    require_any_social: bool = Field(False,
        description="Must have at least one social media account")

    # Business Status
    exclude_permanently_closed: bool = Field(True,
        description="Exclude permanently closed businesses")
    exclude_temporarily_closed: bool = Field(False,
        description="Exclude temporarily closed businesses")

    # Logic Operator
    logic_operator: str = Field("AND",
        pattern="^(AND|OR)$",
        description="How to combine filter conditions")

    # Star Rating Filter (calculated)
    min_star_rating: Optional[int] = Field(None, ge=1, le=5,
        description="Minimum calculated star rating")
```

### Task 3.2: Update ScrapeRequest
**File:** `api/schemas/requests.py`

Add filters field to ScrapeRequest:
```python
# Add to ScrapeRequest class:
filters: Optional[ScrapeFilters] = Field(None,
    description="Pre-scrape filters to apply")
```

### Task 3.3: Create Filter Processor Module
**File:** `utils/scrape_filters.py` (NEW FILE)

```python
"""
Pre-scrape and post-scrape filter processor for MapLeads Pro.

Filters can be applied:
1. During scraping (pre-enrichment) - based on Google Maps data only
2. After enrichment (post-scrape) - based on full data including website

Example filter combinations:
- "5 star reviews but no website" = find web design opportunities
- "4+ rating with website but no social" = find social media clients
- "Has phone, no email" = businesses to call for email collection
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class FilterResult:
    """Result of applying filters to a business."""
    passed: bool
    reason: str
    matched_criteria: List[str] = field(default_factory=list)
    failed_criteria: List[str] = field(default_factory=list)


class ScrapeFilterProcessor:
    """
    Process pre-scrape and post-scrape filters.

    Usage:
        filters = {"min_google_rating": 4.0, "missing_website": True}
        processor = ScrapeFilterProcessor(filters)
        result = processor.should_include(business_data)
        if result.passed:
            save_lead(business_data)
    """

    def __init__(self, filters: dict):
        """
        Initialize filter processor.

        Args:
            filters: Dictionary of filter criteria
        """
        self.filters = filters or {}
        self.logic = filters.get("logic_operator", "AND")
        self.stats = {
            "total_checked": 0,
            "passed": 0,
            "failed": 0,
            "by_reason": {}
        }

    def should_include(self, business: Dict) -> FilterResult:
        """
        Check if a business passes all filter criteria.

        Args:
            business: Business data dictionary

        Returns:
            FilterResult with pass/fail status and details
        """
        self.stats["total_checked"] += 1

        results = []
        matched = []
        failed = []

        # --- RATING FILTERS ---
        if self.filters.get("min_google_rating"):
            rating = float(business.get("rating") or 0)
            min_rating = self.filters["min_google_rating"]
            if rating >= min_rating:
                results.append(True)
                matched.append(f"Rating {rating} >= {min_rating}")
            else:
                results.append(False)
                failed.append(f"Rating {rating} < {min_rating}")

        if self.filters.get("max_google_rating"):
            rating = float(business.get("rating") or 0)
            max_rating = self.filters["max_google_rating"]
            if rating <= max_rating:
                results.append(True)
                matched.append(f"Rating {rating} <= {max_rating}")
            else:
                results.append(False)
                failed.append(f"Rating {rating} > {max_rating}")

        # --- REVIEW COUNT FILTERS ---
        if self.filters.get("min_review_count"):
            reviews = int(business.get("reviews_count") or business.get("review_count") or 0)
            min_reviews = self.filters["min_review_count"]
            if reviews >= min_reviews:
                results.append(True)
                matched.append(f"Reviews {reviews} >= {min_reviews}")
            else:
                results.append(False)
                failed.append(f"Reviews {reviews} < {min_reviews}")

        if self.filters.get("max_review_count"):
            reviews = int(business.get("reviews_count") or business.get("review_count") or 0)
            max_reviews = self.filters["max_review_count"]
            if reviews <= max_reviews:
                results.append(True)
                matched.append(f"Reviews {reviews} <= {max_reviews}")
            else:
                results.append(False)
                failed.append(f"Reviews {reviews} > {max_reviews}")

        # --- CONTACT REQUIREMENT FILTERS ---
        if self.filters.get("require_phone"):
            has_phone = bool(business.get("phone"))
            if has_phone:
                results.append(True)
                matched.append("Has phone number")
            else:
                results.append(False)
                failed.append("No phone number")

        if self.filters.get("require_website"):
            has_website = bool(business.get("website"))
            if has_website:
                results.append(True)
                matched.append("Has website")
            else:
                results.append(False)
                failed.append("No website")

        if self.filters.get("require_email"):
            has_email = bool(business.get("email"))
            if has_email:
                results.append(True)
                matched.append("Has email")
            else:
                results.append(False)
                failed.append("No email")

        # --- OPPORTUNITY FILTERS (INVERSE - looking for missing data) ---
        if self.filters.get("missing_website"):
            has_website = bool(business.get("website"))
            if not has_website:
                results.append(True)
                matched.append("No website (opportunity)")
            else:
                results.append(False)
                failed.append("Has website (not an opportunity)")

        if self.filters.get("missing_email"):
            has_email = bool(business.get("email"))
            if not has_email:
                results.append(True)
                matched.append("No email (opportunity)")
            else:
                results.append(False)
                failed.append("Has email (not an opportunity)")

        if self.filters.get("missing_social_media"):
            social_fields = ["facebook", "instagram", "linkedin", "twitter"]
            has_social = any(business.get(f) for f in social_fields)
            if not has_social:
                results.append(True)
                matched.append("No social media (opportunity)")
            else:
                results.append(False)
                failed.append("Has social media (not an opportunity)")

        # --- SOCIAL MEDIA REQUIREMENT FILTERS ---
        if self.filters.get("require_facebook"):
            if business.get("facebook"):
                results.append(True)
                matched.append("Has Facebook")
            else:
                results.append(False)
                failed.append("No Facebook")

        if self.filters.get("require_instagram"):
            if business.get("instagram"):
                results.append(True)
                matched.append("Has Instagram")
            else:
                results.append(False)
                failed.append("No Instagram")

        if self.filters.get("require_linkedin"):
            if business.get("linkedin"):
                results.append(True)
                matched.append("Has LinkedIn")
            else:
                results.append(False)
                failed.append("No LinkedIn")

        if self.filters.get("require_any_social"):
            social_fields = ["facebook", "instagram", "linkedin", "twitter"]
            has_any = any(business.get(f) for f in social_fields)
            if has_any:
                results.append(True)
                matched.append("Has social media")
            else:
                results.append(False)
                failed.append("No social media")

        # --- BUSINESS STATUS FILTERS ---
        if self.filters.get("exclude_permanently_closed", True):
            is_closed = business.get("permanently_closed", False)
            if not is_closed:
                results.append(True)
            else:
                results.append(False)
                failed.append("Permanently closed")

        if self.filters.get("exclude_temporarily_closed"):
            is_temp_closed = business.get("temporarily_closed", False)
            if not is_temp_closed:
                results.append(True)
            else:
                results.append(False)
                failed.append("Temporarily closed")

        # --- APPLY LOGIC ---
        if not results:
            # No filters applied
            self.stats["passed"] += 1
            return FilterResult(
                passed=True,
                reason="No filters applied",
                matched_criteria=matched,
                failed_criteria=failed
            )

        if self.logic == "AND":
            passed = all(results)
        else:  # OR
            passed = any(results)

        # Update stats
        if passed:
            self.stats["passed"] += 1
        else:
            self.stats["failed"] += 1
            for reason in failed:
                self.stats["by_reason"][reason] = self.stats["by_reason"].get(reason, 0) + 1

        return FilterResult(
            passed=passed,
            reason="All criteria met" if passed else "Filter criteria not met",
            matched_criteria=matched,
            failed_criteria=failed
        )

    def get_stats(self) -> Dict:
        """Get filtering statistics."""
        return {
            **self.stats,
            "pass_rate": (self.stats["passed"] / self.stats["total_checked"] * 100)
                if self.stats["total_checked"] > 0 else 0
        }


# Pre-defined filter presets
FILTER_PRESETS = {
    "web_design_clients": {
        "name": "Web Design Clients",
        "description": "High-rated businesses without websites - perfect for web design pitches",
        "filters": {
            "min_google_rating": 4.0,
            "min_review_count": 10,
            "missing_website": True,
            "require_phone": True
        }
    },
    "social_media_clients": {
        "name": "Social Media Marketing Clients",
        "description": "Businesses with websites but no social presence",
        "filters": {
            "min_google_rating": 3.5,
            "require_website": True,
            "missing_social_media": True
        }
    },
    "premium_leads": {
        "name": "Premium High-Quality Leads",
        "description": "Established businesses with excellent reviews and complete info",
        "filters": {
            "min_google_rating": 4.5,
            "min_review_count": 50,
            "require_website": True,
            "require_phone": True,
            "require_any_social": True
        }
    },
    "new_business_opportunities": {
        "name": "New Business Opportunities",
        "description": "Recently opened businesses that need everything",
        "filters": {
            "max_review_count": 10,
            "missing_website": True,
            "missing_social_media": True
        }
    },
    "email_campaign_ready": {
        "name": "Email Campaign Ready",
        "description": "Businesses with verified email addresses",
        "filters": {
            "require_email": True,
            "require_phone": True,
            "min_google_rating": 3.0
        }
    },
    "cold_calling_ready": {
        "name": "Cold Calling Ready",
        "description": "Businesses with phone numbers and good ratings",
        "filters": {
            "require_phone": True,
            "min_google_rating": 3.5,
            "min_review_count": 5
        }
    },
    "local_seo_clients": {
        "name": "Local SEO Clients",
        "description": "Businesses with websites but low review counts",
        "filters": {
            "require_website": True,
            "max_review_count": 20,
            "min_google_rating": 3.0
        }
    }
}


def get_preset(preset_name: str) -> Optional[Dict]:
    """Get a filter preset by name."""
    return FILTER_PRESETS.get(preset_name)


def list_presets() -> List[Dict]:
    """List all available filter presets."""
    return [
        {"id": k, **v}
        for k, v in FILTER_PRESETS.items()
    ]
```

---

## Phase 4: Pre-Scrape Filters Frontend

### Task 4.1: Add Filter Panel to New Scrape Form
**File:** `frontend/index.html`

Add collapsible filter section:
```html
<!-- Add after Search Query field -->
<div class="card mb-3 border-info">
    <div class="card-header bg-info bg-opacity-10">
        <h6 class="mb-0">
            <i class="fas fa-filter me-2"></i>Lead Filters (Optional)
            <button class="btn btn-sm btn-link float-end p-0" type="button"
                    data-bs-toggle="collapse" data-bs-target="#scrapeFilters">
                <i class="fas fa-chevron-down"></i>
            </button>
        </h6>
    </div>
    <div id="scrapeFilters" class="collapse">
        <div class="card-body">
            <!-- Filter Preset Dropdown -->
            <div class="row mb-3">
                <div class="col-12">
                    <label class="form-label fw-bold">Quick Presets</label>
                    <select id="filterPreset" class="form-select" onchange="applyFilterPreset()">
                        <option value="">-- Select a Preset --</option>
                        <option value="web_design_clients">Web Design Clients</option>
                        <option value="social_media_clients">Social Media Clients</option>
                        <option value="premium_leads">Premium Leads</option>
                        <option value="new_business_opportunities">New Business Opportunities</option>
                        <option value="email_campaign_ready">Email Campaign Ready</option>
                        <option value="cold_calling_ready">Cold Calling Ready</option>
                        <option value="local_seo_clients">Local SEO Clients</option>
                    </select>
                    <small class="text-muted" id="presetDescription"></small>
                </div>
            </div>

            <hr>

            <!-- Rating Filters -->
            <div class="row mb-3">
                <div class="col-md-6">
                    <label class="form-label">Minimum Google Rating</label>
                    <select id="filterMinRating" class="form-select">
                        <option value="">Any Rating</option>
                        <option value="4.5">4.5+ Stars</option>
                        <option value="4.0">4.0+ Stars</option>
                        <option value="3.5">3.5+ Stars</option>
                        <option value="3.0">3.0+ Stars</option>
                    </select>
                </div>
                <div class="col-md-6">
                    <label class="form-label">Minimum Reviews</label>
                    <select id="filterMinReviews" class="form-select">
                        <option value="">Any</option>
                        <option value="100">100+ reviews</option>
                        <option value="50">50+ reviews</option>
                        <option value="20">20+ reviews</option>
                        <option value="10">10+ reviews</option>
                        <option value="5">5+ reviews</option>
                    </select>
                </div>
            </div>

            <!-- Contact Requirements -->
            <div class="row mb-3">
                <div class="col-12">
                    <label class="form-label fw-bold text-success">
                        <i class="fas fa-check-circle me-1"></i>Must Have
                    </label>
                    <div class="d-flex flex-wrap gap-3">
                        <div class="form-check">
                            <input type="checkbox" id="filterRequirePhone" class="form-check-input">
                            <label class="form-check-label">Phone Number</label>
                        </div>
                        <div class="form-check">
                            <input type="checkbox" id="filterRequireWebsite" class="form-check-input">
                            <label class="form-check-label">Website</label>
                        </div>
                        <div class="form-check">
                            <input type="checkbox" id="filterRequireEmail" class="form-check-input">
                            <label class="form-check-label">Email</label>
                        </div>
                        <div class="form-check">
                            <input type="checkbox" id="filterRequireSocial" class="form-check-input">
                            <label class="form-check-label">Any Social Media</label>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Opportunity Filters -->
            <div class="row mb-3">
                <div class="col-12">
                    <label class="form-label fw-bold text-warning">
                        <i class="fas fa-lightbulb me-1"></i>Find Opportunities (Missing)
                    </label>
                    <div class="d-flex flex-wrap gap-3">
                        <div class="form-check">
                            <input type="checkbox" id="filterMissingWebsite" class="form-check-input">
                            <label class="form-check-label">No Website</label>
                        </div>
                        <div class="form-check">
                            <input type="checkbox" id="filterMissingSocial" class="form-check-input">
                            <label class="form-check-label">No Social Media</label>
                        </div>
                        <div class="form-check">
                            <input type="checkbox" id="filterMissingEmail" class="form-check-input">
                            <label class="form-check-label">No Email</label>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Filter Logic -->
            <div class="row">
                <div class="col-md-6">
                    <label class="form-label">Filter Logic</label>
                    <select id="filterLogic" class="form-select">
                        <option value="AND">Match ALL criteria (AND)</option>
                        <option value="OR">Match ANY criteria (OR)</option>
                    </select>
                </div>
                <div class="col-md-6 d-flex align-items-end">
                    <button type="button" class="btn btn-outline-secondary" onclick="clearFilters()">
                        <i class="fas fa-times me-1"></i>Clear Filters
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>
```

### Task 4.2: Add Filter Functions
**File:** `frontend/app.js`

```javascript
// Filter preset descriptions
const FILTER_PRESET_DESCRIPTIONS = {
    "web_design_clients": "High-rated businesses without websites - perfect for web design pitches",
    "social_media_clients": "Businesses with websites but no social presence",
    "premium_leads": "Established businesses with excellent reviews and complete info",
    "new_business_opportunities": "Recently opened businesses that need everything",
    "email_campaign_ready": "Businesses with verified email addresses",
    "cold_calling_ready": "Businesses with phone numbers and good ratings",
    "local_seo_clients": "Businesses with websites but low review counts"
};

// Apply a filter preset
function applyFilterPreset() {
    const preset = document.getElementById('filterPreset').value;
    const descEl = document.getElementById('presetDescription');

    // Clear all filters first
    clearFilters();

    if (!preset) {
        descEl.textContent = '';
        return;
    }

    descEl.textContent = FILTER_PRESET_DESCRIPTIONS[preset] || '';

    // Apply preset-specific filters
    switch(preset) {
        case 'web_design_clients':
            document.getElementById('filterMinRating').value = '4.0';
            document.getElementById('filterMinReviews').value = '10';
            document.getElementById('filterMissingWebsite').checked = true;
            document.getElementById('filterRequirePhone').checked = true;
            break;
        case 'social_media_clients':
            document.getElementById('filterMinRating').value = '3.5';
            document.getElementById('filterRequireWebsite').checked = true;
            document.getElementById('filterMissingSocial').checked = true;
            break;
        case 'premium_leads':
            document.getElementById('filterMinRating').value = '4.5';
            document.getElementById('filterMinReviews').value = '50';
            document.getElementById('filterRequireWebsite').checked = true;
            document.getElementById('filterRequirePhone').checked = true;
            document.getElementById('filterRequireSocial').checked = true;
            break;
        case 'new_business_opportunities':
            document.getElementById('filterMissingWebsite').checked = true;
            document.getElementById('filterMissingSocial').checked = true;
            break;
        case 'email_campaign_ready':
            document.getElementById('filterMinRating').value = '3.0';
            document.getElementById('filterRequireEmail').checked = true;
            document.getElementById('filterRequirePhone').checked = true;
            break;
        case 'cold_calling_ready':
            document.getElementById('filterMinRating').value = '3.5';
            document.getElementById('filterMinReviews').value = '5';
            document.getElementById('filterRequirePhone').checked = true;
            break;
        case 'local_seo_clients':
            document.getElementById('filterMinRating').value = '3.0';
            document.getElementById('filterRequireWebsite').checked = true;
            break;
    }
}

// Clear all filters
function clearFilters() {
    document.getElementById('filterMinRating').value = '';
    document.getElementById('filterMinReviews').value = '';
    document.getElementById('filterRequirePhone').checked = false;
    document.getElementById('filterRequireWebsite').checked = false;
    document.getElementById('filterRequireEmail').checked = false;
    document.getElementById('filterRequireSocial').checked = false;
    document.getElementById('filterMissingWebsite').checked = false;
    document.getElementById('filterMissingSocial').checked = false;
    document.getElementById('filterMissingEmail').checked = false;
    document.getElementById('filterLogic').value = 'AND';
    document.getElementById('filterPreset').value = '';
    document.getElementById('presetDescription').textContent = '';
}

// Get current filter settings
function getScrapeFilters() {
    const filters = {};

    const minRating = document.getElementById('filterMinRating').value;
    if (minRating) filters.min_google_rating = parseFloat(minRating);

    const minReviews = document.getElementById('filterMinReviews').value;
    if (minReviews) filters.min_review_count = parseInt(minReviews);

    if (document.getElementById('filterRequirePhone').checked)
        filters.require_phone = true;
    if (document.getElementById('filterRequireWebsite').checked)
        filters.require_website = true;
    if (document.getElementById('filterRequireEmail').checked)
        filters.require_email = true;
    if (document.getElementById('filterRequireSocial').checked)
        filters.require_any_social = true;

    if (document.getElementById('filterMissingWebsite').checked)
        filters.missing_website = true;
    if (document.getElementById('filterMissingSocial').checked)
        filters.missing_social_media = true;
    if (document.getElementById('filterMissingEmail').checked)
        filters.missing_email = true;

    filters.logic_operator = document.getElementById('filterLogic').value;

    // Only return if there are actual filters
    const hasFilters = Object.keys(filters).length > 1; // > 1 because logic_operator is always there
    return hasFilters ? filters : null;
}

// Update startScrape function to include filters
// In the startScrape function, add:
// const filters = getScrapeFilters();
// if (filters) requestBody.filters = filters;
```

---

# PART 3: IMPLEMENTATION ORDER

## Priority Order

| Phase | Task | Priority | Effort |
|-------|------|----------|--------|
| 1.1 | Add star conversion method | HIGH | Low |
| 1.2 | Update calculate_score to include stars | HIGH | Low |
| 1.3 | Add star_rating database column | HIGH | Low |
| 2.1 | Add star display functions (JS) | HIGH | Low |
| 2.2 | Update leads table with star column | HIGH | Low |
| 2.3 | Add star filter dropdown | MEDIUM | Low |
| 3.1 | Create ScrapeFilters schema | HIGH | Medium |
| 3.2 | Create scrape_filters.py module | HIGH | Medium |
| 3.3 | Integrate filters into scraper | HIGH | Medium |
| 4.1 | Add filter UI to scrape form | MEDIUM | Medium |
| 4.2 | Add filter preset functions | MEDIUM | Low |
| 4.3 | Update startScrape with filters | MEDIUM | Low |

---

# PART 4: FILES SUMMARY

## Files to CREATE
| File | Purpose |
|------|---------|
| `utils/scrape_filters.py` | Filter processor & presets |
| `migrate_star_rating.py` | Database migration |

## Files to MODIFY
| File | Changes |
|------|---------|
| `utils/lead_scoring.py` | Add star conversion methods |
| `api/schemas/requests.py` | Add ScrapeFilters schema |
| `database/models.py` | Add star_rating column |
| `scraper/unified_scraper.py` | Integrate filter checking |
| `frontend/index.html` | Add filter UI, star column |
| `frontend/app.js` | Add filter & star functions |
| `api/services/lead_service.py` | Calculate stars on save |

---

# PART 5: EXAMPLE USE CASES

## Use Case 1: Web Design Agency
**Goal:** Find businesses with good reviews but no website
**Preset:** "Web Design Clients"
**Filters:**
- Minimum Rating: 4.0+
- Minimum Reviews: 10+
- Missing Website: YES
- Require Phone: YES

## Use Case 2: Social Media Agency
**Goal:** Find businesses that need social media help
**Preset:** "Social Media Clients"
**Filters:**
- Minimum Rating: 3.5+
- Require Website: YES
- Missing Social Media: YES

## Use Case 3: Cold Calling Campaign
**Goal:** Get phone numbers for high-quality businesses
**Preset:** "Cold Calling Ready"
**Filters:**
- Minimum Rating: 3.5+
- Minimum Reviews: 5+
- Require Phone: YES

## Use Case 4: Email Marketing Campaign
**Goal:** Build email list of quality businesses
**Preset:** "Email Campaign Ready"
**Filters:**
- Minimum Rating: 3.0+
- Require Email: YES
- Require Phone: YES

---

**Ready to implement? Say "proceed" and I'll start with Phase 1!**
