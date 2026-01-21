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
        ("founded_year", "Founded", "older_better"),
    ]

    def compare_businesses(self, leads: List[Dict]) -> Dict:
        """Compare multiple businesses."""
        if len(leads) < 2:
            return {"error": "Need at least 2 businesses to compare"}

        comparison = {
            "businesses": [l.get("business_name") for l in leads],
            "business_count": len(leads),
            "metrics": [],
            "winner_summary": {},
            "insights": [],
            "overall_winner": None,
            "comparison_matrix": {}
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

            elif comparison_type == "older_better":
                valid_values = {k: v for k, v in values.items() if v is not None}
                if valid_values:
                    winner = min(valid_values, key=valid_values.get)
                    metric.winner = winner
                    winner_counts[winner] += 1
                    years_diff = max(valid_values.values()) - min(valid_values.values())
                    if years_diff > 0:
                        metric.insight = f"{winner} is the most established ({years_diff} years older)"

            comparison["metrics"].append({
                "name": metric.name,
                "values": metric.values,
                "winner": metric.winner,
                "insight": metric.insight,
                "comparison_type": comparison_type
            })

        # Social media comparison
        social_fields = ["social_facebook", "social_instagram", "social_linkedin", "social_twitter"]
        social_counts = {}
        for lead in leads:
            name = lead.get("business_name")
            count = sum(1 for f in social_fields if lead.get(f))
            social_counts[name] = count

        if any(social_counts.values()):
            social_winner = max(social_counts, key=social_counts.get)
            winner_counts[social_winner] += 1
            comparison["metrics"].append({
                "name": "Social Media Presence",
                "values": social_counts,
                "winner": social_winner,
                "insight": f"{social_winner} has the strongest social media presence ({social_counts[social_winner]} platforms)",
                "comparison_type": "higher_better"
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

        if any(contact_scores.values()):
            contact_winner = max(contact_scores, key=contact_scores.get)
            winner_counts[contact_winner] += 1
            comparison["metrics"].append({
                "name": "Contact Completeness",
                "values": contact_scores,
                "winner": contact_winner,
                "insight": f"{contact_winner} has the most complete contact information",
                "comparison_type": "higher_better"
            })

        # Price level comparison (if available)
        price_levels = {}
        price_order = {"$": 1, "$$": 2, "$$$": 3, "$$$$": 4}
        for lead in leads:
            name = lead.get("business_name")
            price = lead.get("price_level")
            if price and price in price_order:
                price_levels[name] = price

        if price_levels:
            comparison["metrics"].append({
                "name": "Price Level",
                "values": price_levels,
                "winner": None,
                "insight": "Price levels shown for comparison",
                "comparison_type": "info_only"
            })

        # Determine overall winner
        comparison["winner_summary"] = dict(sorted(
            winner_counts.items(),
            key=lambda x: x[1],
            reverse=True
        ))

        overall_winner = max(winner_counts, key=winner_counts.get)
        comparison["overall_winner"] = overall_winner

        # Generate insights
        comparison["insights"].append(
            f"{overall_winner} wins in the most categories ({winner_counts[overall_winner]} out of {len(comparison['metrics'])})"
        )

        # Check for ties
        top_score = winner_counts[overall_winner]
        tied = [name for name, score in winner_counts.items() if score == top_score]
        if len(tied) > 1:
            comparison["insights"].append(f"Close competition between: {', '.join(tied)}")

        # Add specific insights
        for metric in comparison["metrics"]:
            if metric.get("insight"):
                comparison["insights"].append(metric["insight"])

        # Build comparison matrix
        for lead in leads:
            name = lead.get("business_name")
            comparison["comparison_matrix"][name] = {
                "rating": lead.get("rating"),
                "reviews": lead.get("review_count"),
                "quality_score": lead.get("data_quality_score"),
                "has_website": bool(lead.get("website")),
                "has_email": bool(lead.get("email")),
                "has_phone": bool(lead.get("phone")),
                "social_count": sum(1 for f in social_fields if lead.get(f)),
                "founded_year": lead.get("founded_year"),
                "wins": winner_counts[name]
            }

        return comparison

    def get_recommendations(self, comparison: Dict) -> List[str]:
        """Generate recommendations based on comparison."""
        recommendations = []

        if comparison.get("error"):
            return recommendations

        winner = comparison.get("overall_winner")
        metrics = comparison.get("metrics", [])

        for metric in metrics:
            if metric.get("winner") and metric["winner"] != winner:
                name = metric["name"]
                metric_winner = metric["winner"]
                recommendations.append(
                    f"Consider {metric_winner} for best {name.lower()}"
                )

        # Add value-based recommendation
        matrix = comparison.get("comparison_matrix", {})
        if matrix:
            # Find best value (high rating, reasonable price)
            best_value = None
            best_value_score = 0

            for name, data in matrix.items():
                rating = data.get("rating") or 0
                reviews = data.get("reviews") or 0
                score = rating * 20 + min(reviews, 100)  # Weight rating heavily

                if score > best_value_score:
                    best_value_score = score
                    best_value = name

            if best_value and best_value != winner:
                recommendations.append(
                    f"{best_value} offers the best value based on rating and reviews"
                )

        return recommendations


# Singleton
competitor_comparator = CompetitorComparator()


def compare_leads(lead_ids: List[int], session) -> Dict:
    """Compare leads by their IDs."""
    from database.models import BusinessLead

    leads = session.query(BusinessLead).filter(
        BusinessLead.id.in_(lead_ids)
    ).all()

    if len(leads) < 2:
        return {"error": "Need at least 2 leads to compare"}

    lead_dicts = [lead.to_dict() for lead in leads]
    return competitor_comparator.compare_businesses(lead_dicts)
