"""
Pre-scrape filter processor for MapLeads Pro.

Filters businesses DURING scraping before saving to database.
This is different from LeadFilters which query already-saved leads.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from loguru import logger


@dataclass
class FilterResult:
    """Result of filtering a business."""
    passed: bool
    reason: str
    matched_criteria: List[str] = field(default_factory=list)
    failed_criteria: List[str] = field(default_factory=list)


# Filter presets for common use cases
FILTER_PRESETS = {
    "web_design_clients": {
        "name": "Web Design Clients",
        "description": "Businesses with good ratings that need a website",
        "filters": {
            "min_google_rating": 4.0,
            "min_review_count": 10,
            "missing_website": True,
            "require_phone": True,
            "logic_operator": "AND"
        }
    },
    "social_media_clients": {
        "name": "Social Media Clients",
        "description": "Businesses with websites but no social media presence",
        "filters": {
            "min_google_rating": 3.5,
            "require_website": True,
            "missing_social_media": True,
            "logic_operator": "AND"
        }
    },
    "premium_leads": {
        "name": "Premium Leads",
        "description": "High-quality leads with excellent ratings and complete profiles",
        "filters": {
            "min_google_rating": 4.5,
            "min_review_count": 50,
            "require_website": True,
            "require_phone": True,
            "require_any_social": True,
            "logic_operator": "AND"
        }
    },
    "new_business_opportunities": {
        "name": "New Business Opportunities",
        "description": "New or small businesses that need help with online presence",
        "filters": {
            "max_review_count": 10,
            "missing_website": True,
            "missing_social_media": True,
            "logic_operator": "AND"
        }
    },
    "email_campaign_ready": {
        "name": "Email Campaign Ready",
        "description": "Businesses with email addresses for outreach campaigns",
        "filters": {
            "min_google_rating": 3.0,
            "require_email": True,
            "require_phone": True,
            "logic_operator": "AND"
        }
    },
    "cold_calling_ready": {
        "name": "Cold Calling Ready",
        "description": "Businesses with phone numbers for telemarketing",
        "filters": {
            "min_google_rating": 3.5,
            "min_review_count": 5,
            "require_phone": True,
            "logic_operator": "AND"
        }
    },
    "local_seo_clients": {
        "name": "Local SEO Clients",
        "description": "Businesses that could benefit from better local SEO",
        "filters": {
            "min_google_rating": 3.0,
            "require_website": True,
            "max_review_count": 20,
            "logic_operator": "AND"
        }
    }
}


class ScrapeFilterProcessor:
    """
    Processes pre-scrape filters to determine if a business should be saved.
    """

    def __init__(self, filters: Optional[Dict[str, Any]] = None):
        """
        Initialize the filter processor.

        Args:
            filters: Filter configuration dictionary. Keys should match ScrapeFilters fields.
        """
        self.filters = filters or {}
        self.logic_operator = self.filters.get("logic_operator", "AND").upper()

        # Statistics tracking
        self.stats = {
            "total_processed": 0,
            "passed": 0,
            "failed": 0,
            "failed_reasons": {}
        }

    @classmethod
    def from_preset(cls, preset_name: str) -> "ScrapeFilterProcessor":
        """
        Create a filter processor from a preset.

        Args:
            preset_name: Name of the preset to use

        Returns:
            ScrapeFilterProcessor configured with preset filters
        """
        if preset_name not in FILTER_PRESETS:
            logger.warning(f"Unknown preset '{preset_name}', using no filters")
            return cls()

        preset = FILTER_PRESETS[preset_name]
        logger.info(f"Using filter preset: {preset['name']}")
        return cls(preset["filters"])

    @classmethod
    def from_schema(cls, schema) -> "ScrapeFilterProcessor":
        """
        Create a filter processor from a ScrapeFilters schema object.

        Args:
            schema: ScrapeFilters Pydantic model instance

        Returns:
            ScrapeFilterProcessor configured with schema filters
        """
        if schema is None:
            return cls()

        # Convert Pydantic model to dict, excluding None values
        filters = {
            k: v for k, v in schema.model_dump().items()
            if v is not None and v is not False
        }
        return cls(filters)

    def should_include(self, business: Dict[str, Any]) -> FilterResult:
        """
        Determine if a business should be included based on filters.

        Args:
            business: Dictionary of business data

        Returns:
            FilterResult with pass/fail status and details
        """
        self.stats["total_processed"] += 1

        # If no filters, include everything
        if not self.filters:
            self.stats["passed"] += 1
            return FilterResult(passed=True, reason="No filters applied")

        matched = []
        failed = []

        # Check each filter criterion
        checks = [
            self._check_rating(business),
            self._check_review_count(business),
            self._check_contact_requirements(business),
            self._check_opportunity_filters(business),
            self._check_social_requirements(business),
            self._check_business_status(business),
        ]

        for check_result in checks:
            if check_result["matched"]:
                matched.extend(check_result["matched"])
            if check_result["failed"]:
                failed.extend(check_result["failed"])

        # Apply logic operator
        if self.logic_operator == "AND":
            passed = len(failed) == 0
        else:  # OR
            passed = len(matched) > 0 or len(failed) == 0

        # Update stats
        if passed:
            self.stats["passed"] += 1
            reason = f"Passed {len(matched)} criteria" if matched else "No applicable filters"
        else:
            self.stats["failed"] += 1
            reason = f"Failed: {', '.join(failed)}"

            # Track failure reasons
            for fail_reason in failed:
                self.stats["failed_reasons"][fail_reason] = \
                    self.stats["failed_reasons"].get(fail_reason, 0) + 1

        return FilterResult(
            passed=passed,
            reason=reason,
            matched_criteria=matched,
            failed_criteria=failed
        )

    def _check_rating(self, business: Dict) -> Dict[str, List[str]]:
        """Check Google rating filters."""
        matched = []
        failed = []

        rating = business.get("rating")

        # Min rating check
        min_rating = self.filters.get("min_google_rating")
        if min_rating is not None:
            if rating is not None and rating >= min_rating:
                matched.append(f"rating >= {min_rating}")
            elif rating is not None:
                failed.append(f"rating {rating} < {min_rating}")
            else:
                failed.append("no rating (required)")

        # Max rating check
        max_rating = self.filters.get("max_google_rating")
        if max_rating is not None:
            if rating is not None and rating <= max_rating:
                matched.append(f"rating <= {max_rating}")
            elif rating is not None:
                failed.append(f"rating {rating} > {max_rating}")

        return {"matched": matched, "failed": failed}

    def _check_review_count(self, business: Dict) -> Dict[str, List[str]]:
        """Check review count filters."""
        matched = []
        failed = []

        review_count = business.get("review_count", 0) or 0

        # Min reviews check
        min_reviews = self.filters.get("min_review_count")
        if min_reviews is not None:
            if review_count >= min_reviews:
                matched.append(f"reviews >= {min_reviews}")
            else:
                failed.append(f"reviews {review_count} < {min_reviews}")

        # Max reviews check
        max_reviews = self.filters.get("max_review_count")
        if max_reviews is not None:
            if review_count <= max_reviews:
                matched.append(f"reviews <= {max_reviews}")
            else:
                failed.append(f"reviews {review_count} > {max_reviews}")

        return {"matched": matched, "failed": failed}

    def _check_contact_requirements(self, business: Dict) -> Dict[str, List[str]]:
        """Check contact requirement filters."""
        matched = []
        failed = []

        phone = business.get("phone")
        website = business.get("website")
        email = business.get("email")

        # Require phone
        if self.filters.get("require_phone"):
            if phone:
                matched.append("has phone")
            else:
                failed.append("no phone (required)")

        # Require website
        if self.filters.get("require_website"):
            if website:
                matched.append("has website")
            else:
                failed.append("no website (required)")

        # Require email
        if self.filters.get("require_email"):
            if email:
                matched.append("has email")
            else:
                failed.append("no email (required)")

        return {"matched": matched, "failed": failed}

    def _check_opportunity_filters(self, business: Dict) -> Dict[str, List[str]]:
        """Check opportunity filters (missing data = sales opportunity)."""
        matched = []
        failed = []

        website = business.get("website")
        email = business.get("email")
        has_social = self._has_any_social(business)

        # Missing website (web design opportunity)
        if self.filters.get("missing_website"):
            if not website:
                matched.append("no website (opportunity)")
            else:
                failed.append("has website (not an opportunity)")

        # Missing social media (SMM opportunity)
        if self.filters.get("missing_social_media"):
            if not has_social:
                matched.append("no social media (opportunity)")
            else:
                failed.append("has social media (not an opportunity)")

        # Missing email
        if self.filters.get("missing_email"):
            if not email:
                matched.append("no email (opportunity)")
            else:
                failed.append("has email (not an opportunity)")

        return {"matched": matched, "failed": failed}

    def _check_social_requirements(self, business: Dict) -> Dict[str, List[str]]:
        """Check social media requirement filters."""
        matched = []
        failed = []

        facebook = business.get("social_facebook") or business.get("facebook")
        instagram = business.get("social_instagram") or business.get("instagram")
        linkedin = business.get("social_linkedin") or business.get("linkedin")

        # Require Facebook
        if self.filters.get("require_facebook"):
            if facebook:
                matched.append("has Facebook")
            else:
                failed.append("no Facebook (required)")

        # Require Instagram
        if self.filters.get("require_instagram"):
            if instagram:
                matched.append("has Instagram")
            else:
                failed.append("no Instagram (required)")

        # Require LinkedIn
        if self.filters.get("require_linkedin"):
            if linkedin:
                matched.append("has LinkedIn")
            else:
                failed.append("no LinkedIn (required)")

        # Require any social
        if self.filters.get("require_any_social"):
            if self._has_any_social(business):
                matched.append("has social media")
            else:
                failed.append("no social media (required)")

        return {"matched": matched, "failed": failed}

    def _check_business_status(self, business: Dict) -> Dict[str, List[str]]:
        """Check business status filters."""
        matched = []
        failed = []

        status = business.get("business_status", "").lower()
        is_permanently_closed = "permanently closed" in status or business.get("permanently_closed", False)
        is_temporarily_closed = "temporarily closed" in status or business.get("temporarily_closed", False)

        # Exclude permanently closed
        if self.filters.get("exclude_permanently_closed", True):
            if is_permanently_closed:
                failed.append("permanently closed")
            else:
                matched.append("not permanently closed")

        # Exclude temporarily closed
        if self.filters.get("exclude_temporarily_closed"):
            if is_temporarily_closed:
                failed.append("temporarily closed")
            else:
                matched.append("not temporarily closed")

        return {"matched": matched, "failed": failed}

    def _has_any_social(self, business: Dict) -> bool:
        """Check if business has any social media presence."""
        social_fields = [
            "social_facebook", "facebook",
            "social_instagram", "instagram",
            "social_linkedin", "linkedin",
            "social_twitter", "twitter",
            "social_youtube", "youtube",
            "social_tiktok", "tiktok"
        ]
        return any(business.get(field) for field in social_fields)

    def get_stats(self) -> Dict[str, Any]:
        """Get filtering statistics."""
        stats = self.stats.copy()
        if stats["total_processed"] > 0:
            stats["pass_rate"] = round(stats["passed"] / stats["total_processed"] * 100, 1)
        else:
            stats["pass_rate"] = 0
        return stats

    def reset_stats(self):
        """Reset filtering statistics."""
        self.stats = {
            "total_processed": 0,
            "passed": 0,
            "failed": 0,
            "failed_reasons": {}
        }


def get_filter_presets() -> Dict[str, Dict[str, Any]]:
    """Get all available filter presets."""
    return FILTER_PRESETS


def get_preset_names() -> List[str]:
    """Get list of preset names."""
    return list(FILTER_PRESETS.keys())


def apply_filters_to_business(business: Dict, filters: Optional[Dict] = None) -> FilterResult:
    """
    Convenience function to apply filters to a single business.

    Args:
        business: Business data dictionary
        filters: Filter configuration

    Returns:
        FilterResult
    """
    processor = ScrapeFilterProcessor(filters)
    return processor.should_include(business)
