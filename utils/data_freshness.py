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
            return {"status": "unknown", "days_old": None, "needs_refresh": True}

        # Parse datetime if string
        if isinstance(scraped_at, str):
            try:
                scraped_at = datetime.fromisoformat(scraped_at.replace('Z', '+00:00').replace('+00:00', ''))
            except:
                scraped_at = datetime.strptime(scraped_at[:19], "%Y-%m-%dT%H:%M:%S")

        now = datetime.utcnow()
        if scraped_at.tzinfo:
            scraped_at = scraped_at.replace(tzinfo=None)

        age = now - scraped_at

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
            "hours_old": int(age.total_seconds() / 3600),
            "scraped_at": scraped_at.isoformat() if scraped_at else None,
            "last_verified_at": last_verified.isoformat() if last_verified else None,
            "needs_refresh": status in ("stale", "outdated"),
            "freshness_score": self._calculate_freshness_score(age)
        }

    def _calculate_freshness_score(self, age: timedelta) -> int:
        """Calculate freshness score (100 = just scraped, 0 = very old)."""
        days = age.days

        if days <= 1:
            return 100
        elif days <= 7:
            return 90 - (days * 2)
        elif days <= 30:
            return 80 - ((days - 7) * 2)
        elif days <= 90:
            return 50 - ((days - 30) // 3)
        elif days <= 180:
            return 30 - ((days - 90) // 9)
        else:
            return max(0, 20 - ((days - 180) // 30))

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
                "full_address", "category", "is_open_now", "price_level",
                "hours_monday", "hours_tuesday", "hours_wednesday",
                "hours_thursday", "hours_friday", "hours_saturday", "hours_sunday"
            ]

        changes = {
            "has_changes": False,
            "changed_fields": [],
            "field_changes": {},
            "change_count": 0,
            "significance": "none"
        }

        significant_fields = ["phone", "email", "website", "full_address"]

        for field in tracked_fields:
            old_val = old_data.get(field)
            new_val = new_data.get(field)

            # Normalize values for comparison
            if old_val is not None:
                old_val = str(old_val).strip() if old_val else None
            if new_val is not None:
                new_val = str(new_val).strip() if new_val else None

            if old_val != new_val:
                changes["has_changes"] = True
                changes["changed_fields"].append(field)
                changes["field_changes"][field] = {
                    "old": old_val,
                    "new": new_val,
                    "is_significant": field in significant_fields
                }
                changes["change_count"] += 1

                # Track significance
                if field in significant_fields:
                    changes["significance"] = "high"
                elif changes["significance"] == "none":
                    changes["significance"] = "low"

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
            "average_age_days": 0,
            "oldest_lead": None,
            "newest_lead": None,
            "freshness_breakdown": {}
        }

        ages = []
        oldest_age = 0
        newest_age = float('inf')

        for lead in leads:
            freshness = self.get_freshness_status(lead)
            status = freshness["status"]
            stats[status] += 1

            if freshness.get("needs_refresh"):
                stats["needs_refresh_count"] += 1

            if freshness.get("days_old") is not None:
                ages.append(freshness["days_old"])

                if freshness["days_old"] > oldest_age:
                    oldest_age = freshness["days_old"]
                    stats["oldest_lead"] = {
                        "name": lead.get("business_name"),
                        "days_old": freshness["days_old"],
                        "scraped_at": freshness["scraped_at"]
                    }

                if freshness["days_old"] < newest_age:
                    newest_age = freshness["days_old"]
                    stats["newest_lead"] = {
                        "name": lead.get("business_name"),
                        "days_old": freshness["days_old"],
                        "scraped_at": freshness["scraped_at"]
                    }

        if ages:
            stats["average_age_days"] = round(sum(ages) / len(ages), 1)

        # Calculate percentages
        total = max(stats["total"], 1)
        stats["freshness_breakdown"] = {
            "fresh_percent": round((stats["fresh"] / total) * 100, 1),
            "recent_percent": round((stats["recent"] / total) * 100, 1),
            "stale_percent": round((stats["stale"] / total) * 100, 1),
            "outdated_percent": round((stats["outdated"] / total) * 100, 1),
        }

        return stats

    def get_refresh_priority(self, leads: List[Dict]) -> List[Dict]:
        """Get leads sorted by refresh priority (most stale first)."""
        prioritized = []

        for lead in leads:
            freshness = self.get_freshness_status(lead)
            priority_score = 0

            # Higher score = higher priority for refresh
            if freshness["status"] == "outdated":
                priority_score = 100
            elif freshness["status"] == "stale":
                priority_score = 75
            elif freshness["status"] == "recent":
                priority_score = 25
            else:
                priority_score = 0

            # Boost priority for high-value leads
            if lead.get("data_quality_score", 0) > 70:
                priority_score += 10
            if lead.get("email"):
                priority_score += 5
            if lead.get("phone"):
                priority_score += 5

            prioritized.append({
                "lead_id": lead.get("id"),
                "business_name": lead.get("business_name"),
                "freshness_status": freshness["status"],
                "days_old": freshness.get("days_old"),
                "priority_score": priority_score,
                "needs_refresh": freshness.get("needs_refresh", False)
            })

        # Sort by priority score (highest first)
        prioritized.sort(key=lambda x: x["priority_score"], reverse=True)

        return prioritized


# Singleton
freshness_tracker = DataFreshnessTracker()


def get_freshness(lead: Dict) -> Dict:
    """Quick function to get lead freshness."""
    return freshness_tracker.get_freshness_status(lead)


def check_changes(old_data: Dict, new_data: Dict) -> Dict:
    """Quick function to check for changes between data snapshots."""
    return freshness_tracker.compare_and_track_changes(old_data, new_data)
