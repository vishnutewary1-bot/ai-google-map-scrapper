"""AI-powered lead scoring module for MapLeads Pro.

Enhanced lead scoring with customizable weights and detailed breakdown.
"""
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

try:
    from sklearn.preprocessing import MinMaxScaler
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Database imports (optional)
try:
    from database import db_manager, BusinessLead
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False
    db_manager = None
    BusinessLead = None


@dataclass
class StarRatingInfo:
    """Star rating information with label, color, and suggested action."""
    stars: int
    label: str
    color: str
    suggested_action: str
    score_range: str


# Star rating conversion utilities
def score_to_stars(score: float) -> int:
    """
    Convert a 0-100 lead score to a 1-5 star rating.

    Args:
        score: Lead score from 0-100

    Returns:
        Star rating from 1-5

    Ranges:
        5 Stars: 85-100 (Excellent)
        4 Stars: 70-84 (Good)
        3 Stars: 50-69 (Average)
        2 Stars: 30-49 (Below Average)
        1 Star: 0-29 (Poor)
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


def get_star_description(stars: int) -> StarRatingInfo:
    """
    Get detailed description for a star rating.

    Args:
        stars: Star rating from 1-5

    Returns:
        StarRatingInfo with label, color, suggested_action, and score_range
    """
    descriptions = {
        5: StarRatingInfo(
            stars=5,
            label="Excellent",
            color="#22c55e",  # Green
            suggested_action="High priority - Contact immediately for best conversion",
            score_range="85-100"
        ),
        4: StarRatingInfo(
            stars=4,
            label="Good",
            color="#84cc16",  # Lime green
            suggested_action="Strong lead - Include in primary outreach campaigns",
            score_range="70-84"
        ),
        3: StarRatingInfo(
            stars=3,
            label="Average",
            color="#eab308",  # Yellow
            suggested_action="Moderate potential - Consider for secondary campaigns",
            score_range="50-69"
        ),
        2: StarRatingInfo(
            stars=2,
            label="Below Average",
            color="#f97316",  # Orange
            suggested_action="Low priority - May need data enrichment before outreach",
            score_range="30-49"
        ),
        1: StarRatingInfo(
            stars=1,
            label="Poor",
            color="#ef4444",  # Red
            suggested_action="Not recommended - Consider for re-scraping or removal",
            score_range="0-29"
        )
    }

    # Default to 1 star if invalid input
    return descriptions.get(stars, descriptions[1])


def get_star_display(stars: int, include_label: bool = True) -> Dict:
    """
    Get star rating display information for frontend rendering.

    Args:
        stars: Star rating from 1-5
        include_label: Whether to include the text label

    Returns:
        Dictionary with stars, label, color, and icon info
    """
    info = get_star_description(stars)

    return {
        "stars": stars,
        "filled_stars": stars,
        "empty_stars": 5 - stars,
        "label": info.label if include_label else None,
        "color": info.color,
        "suggested_action": info.suggested_action,
        "score_range": info.score_range,
        "display_text": f"{'★' * stars}{'☆' * (5 - stars)}"
    }


@dataclass
class ScoringWeights:
    """Customizable weights for lead scoring."""
    # Contact completeness (0-1)
    has_email: float = 15.0
    has_phone: float = 15.0
    has_website: float = 10.0
    has_multiple_contacts: float = 5.0
    has_business_email: float = 5.0

    # Social presence (0-1)
    has_social_media: float = 8.0
    has_multiple_social: float = 5.0
    has_linkedin: float = 3.0

    # Business quality indicators
    high_rating: float = 10.0  # 4.0+ rating
    many_reviews: float = 8.0  # 50+ reviews
    verified_business: float = 5.0

    # Company maturity
    established_business: float = 5.0  # 5+ years
    has_employees_info: float = 3.0
    has_revenue_info: float = 3.0

    # Engagement indicators
    responds_to_reviews: float = 5.0
    has_photos: float = 3.0
    has_description: float = 3.0
    has_hours: float = 2.0

    def get_max_score(self) -> float:
        """Calculate maximum possible score."""
        return sum([
            self.has_email, self.has_phone, self.has_website,
            self.has_multiple_contacts, self.has_business_email,
            self.has_social_media, self.has_multiple_social, self.has_linkedin,
            self.high_rating, self.many_reviews, self.verified_business,
            self.established_business, self.has_employees_info, self.has_revenue_info,
            self.responds_to_reviews, self.has_photos, self.has_description, self.has_hours
        ])


class LeadScorer:
    """
    AI-powered lead scoring system.
    Combines rule-based scoring with optional AI enhancement.
    """

    # Scoring weights for different factors
    WEIGHTS = {
        "contact_info": 0.25,      # Phone, email, website availability
        "data_completeness": 0.15,  # Overall data quality
        "online_presence": 0.15,    # Website, social media
        "reputation": 0.20,         # Rating, review count
        "engagement_potential": 0.15,  # Reviews, responses
        "business_maturity": 0.10   # Indicators of established business
    }

    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize lead scorer.

        Args:
            openai_api_key: Optional OpenAI API key for AI-enhanced scoring
        """
        self.openai_client = None
        if openai_api_key and OPENAI_AVAILABLE:
            openai.api_key = openai_api_key
            self.openai_client = openai

        self.scaler = MinMaxScaler() if SKLEARN_AVAILABLE else None

    def calculate_score(self, lead: Dict) -> Dict:
        """
        Calculate comprehensive lead score.

        Args:
            lead: Lead dictionary

        Returns:
            Dict with overall score, component scores, and star rating
        """
        scores = {
            "overall_score": 0,
            "grade": "F",
            "stars": 1,
            "star_label": "Poor",
            "star_color": "#ef4444",
            "star_info": None,
            "components": {},
            "strengths": [],
            "weaknesses": [],
            "recommendations": []
        }

        try:
            # Calculate component scores
            contact_score = self._score_contact_info(lead)
            completeness_score = self._score_data_completeness(lead)
            presence_score = self._score_online_presence(lead)
            reputation_score = self._score_reputation(lead)
            engagement_score = self._score_engagement_potential(lead)
            maturity_score = self._score_business_maturity(lead)

            scores["components"] = {
                "contact_info": round(contact_score, 1),
                "data_completeness": round(completeness_score, 1),
                "online_presence": round(presence_score, 1),
                "reputation": round(reputation_score, 1),
                "engagement_potential": round(engagement_score, 1),
                "business_maturity": round(maturity_score, 1)
            }

            # Calculate weighted overall score
            overall = (
                contact_score * self.WEIGHTS["contact_info"] +
                completeness_score * self.WEIGHTS["data_completeness"] +
                presence_score * self.WEIGHTS["online_presence"] +
                reputation_score * self.WEIGHTS["reputation"] +
                engagement_score * self.WEIGHTS["engagement_potential"] +
                maturity_score * self.WEIGHTS["business_maturity"]
            )

            scores["overall_score"] = round(overall, 1)
            scores["grade"] = self._calculate_grade(overall)

            # Calculate star rating (1-5)
            stars = score_to_stars(overall)
            star_info = get_star_description(stars)
            scores["stars"] = stars
            scores["star_label"] = star_info.label
            scores["star_color"] = star_info.color
            scores["star_info"] = {
                "stars": star_info.stars,
                "label": star_info.label,
                "color": star_info.color,
                "suggested_action": star_info.suggested_action,
                "score_range": star_info.score_range
            }

            # Identify strengths and weaknesses
            self._analyze_strengths_weaknesses(scores, lead)

            # Generate recommendations
            self._generate_recommendations(scores, lead)

        except Exception as e:
            logger.error(f"Error calculating lead score: {e}")
            scores["error"] = str(e)

        return scores

    def _score_contact_info(self, lead: Dict) -> float:
        """Score based on contact information availability."""
        score = 0

        # Phone number (most valuable for cold calling)
        if lead.get("phone"):
            score += 40
            # Bonus for valid format
            if re.match(r"^\+?[\d\s\-\(\)]{10,}$", lead["phone"]):
                score += 10

        # Email (valuable for email campaigns)
        if lead.get("email"):
            score += 30
            # Bonus for business email (not gmail, etc.)
            if not any(d in lead["email"].lower() for d in ["gmail", "yahoo", "hotmail", "outlook"]):
                score += 10

        # Website
        if lead.get("website"):
            score += 10

        return min(score, 100)

    def _score_data_completeness(self, lead: Dict) -> float:
        """Score based on data completeness."""
        fields_to_check = [
            "business_name", "full_address", "city", "state", "pin_code",
            "phone", "website", "category", "email", "place_id"
        ]

        filled = sum(1 for f in fields_to_check if lead.get(f))
        base_score = (filled / len(fields_to_check)) * 80

        # Bonus for additional fields
        if lead.get("owner_name"):
            base_score += 5
        if lead.get("latitude") and lead.get("longitude"):
            base_score += 5
        if lead.get("subcategories"):
            base_score += 5
        if any(lead.get(f"hours_{d}") for d in ["monday", "tuesday", "wednesday"]):
            base_score += 5

        return min(base_score, 100)

    def _score_online_presence(self, lead: Dict) -> float:
        """Score based on online presence."""
        score = 0

        # Website
        if lead.get("website"):
            score += 30
            # Bonus for HTTPS
            if lead["website"].startswith("https"):
                score += 5

        # Social media presence
        social_platforms = [
            "social_facebook", "social_instagram", "social_twitter",
            "social_linkedin", "social_youtube"
        ]
        social_count = sum(1 for s in social_platforms if lead.get(s))
        score += social_count * 12  # Up to 60 points for all 5

        # Maps presence
        if lead.get("maps_url"):
            score += 5

        return min(score, 100)

    def _score_reputation(self, lead: Dict) -> float:
        """Score based on business reputation."""
        score = 0

        rating = lead.get("rating")
        review_count = lead.get("review_count", 0)

        # Rating component (0-50 points)
        if rating:
            if rating >= 4.5:
                score += 50
            elif rating >= 4.0:
                score += 40
            elif rating >= 3.5:
                score += 30
            elif rating >= 3.0:
                score += 20
            else:
                score += 10

        # Review count component (0-50 points)
        if review_count:
            if review_count >= 100:
                score += 50
            elif review_count >= 50:
                score += 40
            elif review_count >= 20:
                score += 30
            elif review_count >= 10:
                score += 20
            elif review_count >= 5:
                score += 10

        return min(score, 100)

    def _score_engagement_potential(self, lead: Dict) -> float:
        """Score based on engagement potential."""
        score = 50  # Base score

        review_count = lead.get("review_count", 0)

        # High review count indicates engaged customers
        if review_count >= 50:
            score += 20
        elif review_count >= 20:
            score += 10

        # Has hours listed (indicates active business)
        if any(lead.get(f"hours_{d}") for d in ["monday", "tuesday"]):
            score += 15

        # Has email (can engage directly)
        if lead.get("email"):
            score += 15

        return min(score, 100)

    def _score_business_maturity(self, lead: Dict) -> float:
        """Score indicators of an established business."""
        score = 50  # Base score

        # Has website
        if lead.get("website"):
            score += 15

        # Has multiple social profiles
        social_count = sum(1 for s in [
            "social_facebook", "social_instagram", "social_linkedin"
        ] if lead.get(s))
        score += social_count * 10

        # Has significant reviews (indicates time in business)
        if lead.get("review_count", 0) >= 50:
            score += 15

        return min(score, 100)

    def _calculate_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "A-"
        elif score >= 75:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 65:
            return "B-"
        elif score >= 60:
            return "C+"
        elif score >= 55:
            return "C"
        elif score >= 50:
            return "C-"
        elif score >= 45:
            return "D+"
        elif score >= 40:
            return "D"
        else:
            return "F"

    def _analyze_strengths_weaknesses(self, scores: Dict, lead: Dict):
        """Identify lead strengths and weaknesses."""
        components = scores["components"]

        # Identify strengths (scores >= 70)
        for component, score in components.items():
            if score >= 70:
                if component == "contact_info":
                    scores["strengths"].append("Strong contact information available")
                elif component == "reputation":
                    scores["strengths"].append(f"Good reputation (Rating: {lead.get('rating', 'N/A')})")
                elif component == "online_presence":
                    scores["strengths"].append("Strong online presence")
                elif component == "data_completeness":
                    scores["strengths"].append("Complete business profile")

        # Identify weaknesses (scores < 50)
        for component, score in components.items():
            if score < 50:
                if component == "contact_info":
                    scores["weaknesses"].append("Limited contact information")
                elif component == "reputation":
                    scores["weaknesses"].append("Limited reviews or low rating")
                elif component == "online_presence":
                    scores["weaknesses"].append("Weak online presence")
                elif component == "data_completeness":
                    scores["weaknesses"].append("Incomplete business data")

    def _generate_recommendations(self, scores: Dict, lead: Dict):
        """Generate actionable recommendations."""
        recommendations = []

        # Contact-based recommendations
        if lead.get("phone") and lead.get("email"):
            recommendations.append("High-priority lead: Has both phone and email for multi-channel outreach")
        elif lead.get("phone"):
            recommendations.append("Good for cold calling campaigns")
        elif lead.get("email"):
            recommendations.append("Suitable for email marketing campaigns")

        # Rating-based recommendations
        rating = lead.get("rating")
        if rating and rating < 4.0:
            recommendations.append("Opportunity: May be looking for solutions to improve customer satisfaction")
        elif rating and rating >= 4.5:
            recommendations.append("Premium lead: High customer satisfaction indicates successful business")

        # Review-based recommendations
        review_count = lead.get("review_count", 0)
        if review_count >= 50:
            recommendations.append("Established business with significant customer base")
        elif review_count < 10:
            recommendations.append("Newer or smaller business - may be more receptive to new services")

        # Website-based recommendations
        if not lead.get("website"):
            recommendations.append("No website found - opportunity for web development services")
        if not lead.get("email") and lead.get("website"):
            recommendations.append("Has website but no email - try website contact form")

        scores["recommendations"] = recommendations[:5]  # Limit to top 5

    async def score_with_ai(self, lead: Dict, context: Optional[str] = None) -> Dict:
        """
        Use AI to enhance lead scoring with contextual analysis.

        Args:
            lead: Lead dictionary
            context: Additional context (e.g., target industry, campaign type)

        Returns:
            Enhanced scoring with AI insights
        """
        # Get base score first
        base_scores = self.calculate_score(lead)

        if not self.openai_client:
            logger.warning("OpenAI not configured for AI scoring")
            return base_scores

        try:
            # Prepare lead summary for AI
            lead_summary = f"""
            Business: {lead.get('business_name')}
            Category: {lead.get('category')}
            Location: {lead.get('city')}, {lead.get('state')}
            Rating: {lead.get('rating')}/5 ({lead.get('review_count', 0)} reviews)
            Has Phone: {bool(lead.get('phone'))}
            Has Email: {bool(lead.get('email'))}
            Has Website: {bool(lead.get('website'))}
            Social Presence: {sum(1 for s in ['social_facebook', 'social_instagram', 'social_linkedin'] if lead.get(s))} platforms
            """

            prompt = f"""Analyze this business lead and provide insights:

{lead_summary}

Campaign Context: {context or 'General B2B outreach'}

Provide:
1. Overall lead quality assessment (1 sentence)
2. Best outreach approach for this lead
3. Key talking points based on their business
4. Potential pain points this business might have
5. Risk factors to consider

Be concise and actionable."""

            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a B2B sales analyst helping qualify leads."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )

            ai_insights = response.choices[0].message.content

            base_scores["ai_insights"] = ai_insights
            base_scores["ai_enhanced"] = True

        except Exception as e:
            logger.error(f"Error with AI scoring: {e}")
            base_scores["ai_error"] = str(e)

        return base_scores

    def batch_score(self, leads: List[Dict]) -> List[Dict]:
        """
        Score multiple leads and rank them.

        Args:
            leads: List of lead dictionaries

        Returns:
            List of leads with scores, sorted by overall score
        """
        scored_leads = []

        for lead in leads:
            score_data = self.calculate_score(lead)
            scored_leads.append({
                **lead,
                "lead_score": score_data["overall_score"],
                "lead_grade": score_data["grade"],
                "score_components": score_data["components"],
                "score_recommendations": score_data["recommendations"]
            })

        # Sort by score descending
        scored_leads.sort(key=lambda x: x["lead_score"], reverse=True)

        return scored_leads

    def score_and_save(self, filters: Optional[Dict] = None) -> Dict:
        """
        Score all leads in database and update their quality scores.

        Args:
            filters: Optional filters for leads to score

        Returns:
            Summary of scoring operation
        """
        results = {
            "leads_scored": 0,
            "average_score": 0,
            "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
            "top_leads": []
        }

        try:
            with db_manager.get_session() as session:
                query = session.query(BusinessLead)

                if filters:
                    if filters.get("city"):
                        query = query.filter(BusinessLead.city == filters["city"])
                    if filters.get("category"):
                        query = query.filter(BusinessLead.category == filters["category"])

                leads = query.all()
                total_score = 0

                for lead in leads:
                    lead_dict = lead.to_dict()
                    score_data = self.calculate_score(lead_dict)

                    # Update lead's quality score
                    lead.data_quality_score = int(score_data["overall_score"])
                    total_score += score_data["overall_score"]

                    # Track grade distribution
                    grade = score_data["grade"][0]  # First letter
                    if grade in results["grade_distribution"]:
                        results["grade_distribution"][grade] += 1

                    results["leads_scored"] += 1

                session.commit()

                # Calculate average
                if results["leads_scored"] > 0:
                    results["average_score"] = round(total_score / results["leads_scored"], 1)

                # Get top 10 leads
                top_leads = session.query(BusinessLead).order_by(
                    BusinessLead.data_quality_score.desc()
                ).limit(10).all()

                results["top_leads"] = [
                    {
                        "id": l.id,
                        "name": l.business_name,
                        "score": l.data_quality_score,
                        "phone": l.phone,
                        "email": l.email
                    }
                    for l in top_leads
                ]

        except Exception as e:
            logger.error(f"Error in batch scoring: {e}")
            results["error"] = str(e)

        return results


class EnhancedLeadScorer:
    """
    Enhanced lead scoring with customizable weights and detailed breakdown.
    Feature 6.1 implementation.
    """

    def __init__(self, weights: Optional[ScoringWeights] = None):
        """
        Initialize enhanced lead scorer.

        Args:
            weights: Optional custom scoring weights
        """
        self.weights = weights or ScoringWeights()

    def score_lead(self, lead: Dict) -> Dict:
        """
        Score a lead and return detailed breakdown.

        Args:
            lead: Lead dictionary

        Returns:
            Dict with 'score', 'grade', 'breakdown', 'recommendations'
        """
        breakdown = {}
        total_score = 0.0
        max_possible = self.weights.get_max_score()
        recommendations = []

        # ===== Contact Completeness =====

        # Email
        if lead.get('email'):
            breakdown['email'] = self.weights.has_email
            total_score += self.weights.has_email

            # Bonus for business email
            email = lead['email'].lower()
            if not any(d in email for d in ['gmail', 'yahoo', 'hotmail', 'outlook', 'aol']):
                breakdown['business_email'] = self.weights.has_business_email
                total_score += self.weights.has_business_email
        else:
            breakdown['email'] = 0
            recommendations.append("Add email address")

        # Phone
        if lead.get('phone'):
            breakdown['phone'] = self.weights.has_phone
            total_score += self.weights.has_phone
        else:
            breakdown['phone'] = 0
            recommendations.append("Add phone number")

        # Website
        if lead.get('website'):
            breakdown['website'] = self.weights.has_website
            total_score += self.weights.has_website
        else:
            breakdown['website'] = 0
            recommendations.append("Add website")

        # Multiple contacts
        contact_count = sum(1 for k in ['email_1', 'email_2', 'phone_1', 'phone_2'] if lead.get(k))
        if contact_count >= 2:
            breakdown['multiple_contacts'] = self.weights.has_multiple_contacts
            total_score += self.weights.has_multiple_contacts

        # ===== Social Media =====

        social_platforms = ['social_facebook', 'social_instagram', 'social_linkedin', 'social_twitter', 'social_youtube']
        social_count = sum(1 for p in social_platforms if lead.get(p))

        if social_count > 0:
            breakdown['social_media'] = self.weights.has_social_media
            total_score += self.weights.has_social_media
        else:
            recommendations.append("Find social media profiles")

        if social_count >= 3:
            breakdown['multiple_social'] = self.weights.has_multiple_social
            total_score += self.weights.has_multiple_social

        if lead.get('social_linkedin'):
            breakdown['linkedin'] = self.weights.has_linkedin
            total_score += self.weights.has_linkedin

        # ===== Rating Quality =====

        rating = lead.get('rating', 0) or 0
        if rating >= 4.0:
            breakdown['high_rating'] = self.weights.high_rating
            total_score += self.weights.high_rating
        elif rating >= 3.5:
            breakdown['high_rating'] = self.weights.high_rating * 0.5
            total_score += self.weights.high_rating * 0.5

        review_count = lead.get('review_count', 0) or 0
        if review_count >= 100:
            breakdown['reviews'] = self.weights.many_reviews
            total_score += self.weights.many_reviews
        elif review_count >= 50:
            breakdown['reviews'] = self.weights.many_reviews * 0.7
            total_score += self.weights.many_reviews * 0.7
        elif review_count >= 20:
            breakdown['reviews'] = self.weights.many_reviews * 0.4
            total_score += self.weights.many_reviews * 0.4

        # ===== Business Maturity =====

        founded_year = lead.get('founded_year')
        if founded_year:
            years = datetime.now().year - founded_year
            if years >= 5:
                breakdown['established'] = self.weights.established_business
                total_score += self.weights.established_business
            elif years >= 2:
                breakdown['established'] = self.weights.established_business * 0.5
                total_score += self.weights.established_business * 0.5

        if lead.get('employees') or lead.get('employees_min'):
            breakdown['employees_info'] = self.weights.has_employees_info
            total_score += self.weights.has_employees_info

        if lead.get('revenue') or lead.get('revenue_min'):
            breakdown['revenue_info'] = self.weights.has_revenue_info
            total_score += self.weights.has_revenue_info

        # ===== Engagement =====

        if lead.get('photos') or lead.get('photo_count', 0) > 0:
            breakdown['photos'] = self.weights.has_photos
            total_score += self.weights.has_photos

        if lead.get('description'):
            breakdown['description'] = self.weights.has_description
            total_score += self.weights.has_description

        if any(lead.get(f'hours_{d}') for d in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']):
            breakdown['hours'] = self.weights.has_hours
            total_score += self.weights.has_hours

        # ===== Calculate Final Score =====

        final_score = int((total_score / max_possible) * 100) if max_possible > 0 else 0

        # Determine grade
        if final_score >= 90:
            grade = 'A+'
        elif final_score >= 80:
            grade = 'A'
        elif final_score >= 70:
            grade = 'B'
        elif final_score >= 60:
            grade = 'C'
        elif final_score >= 50:
            grade = 'D'
        else:
            grade = 'F'

        # Quality tier
        if final_score >= 80:
            quality_tier = 'premium'
        elif final_score >= 50:
            quality_tier = 'standard'
        else:
            quality_tier = 'basic'

        # Calculate star rating
        stars = score_to_stars(final_score)
        star_info = get_star_description(stars)

        return {
            'score': final_score,
            'grade': grade,
            'stars': stars,
            'star_label': star_info.label,
            'star_color': star_info.color,
            'star_info': {
                'stars': star_info.stars,
                'label': star_info.label,
                'color': star_info.color,
                'suggested_action': star_info.suggested_action,
                'score_range': star_info.score_range
            },
            'breakdown': breakdown,
            'max_possible': int(max_possible),
            'earned': round(total_score, 1),
            'recommendations': recommendations[:3],  # Top 3 recommendations
            'quality_tier': quality_tier,
            'components': {
                'contact': breakdown.get('email', 0) + breakdown.get('phone', 0) + breakdown.get('website', 0),
                'social': breakdown.get('social_media', 0) + breakdown.get('multiple_social', 0),
                'reputation': breakdown.get('high_rating', 0) + breakdown.get('reviews', 0),
                'maturity': breakdown.get('established', 0) + breakdown.get('employees_info', 0) + breakdown.get('revenue_info', 0)
            }
        }

    def batch_score(self, leads: List[Dict]) -> List[Dict]:
        """Score multiple leads and add score data to each."""
        scored = []
        for lead in leads:
            score_data = self.score_lead(lead)
            scored.append({
                **lead,
                'lead_score': score_data['score'],
                'lead_grade': score_data['grade'],
                'quality_tier': score_data['quality_tier'],
                'score_breakdown': score_data['breakdown']
            })
        return sorted(scored, key=lambda x: x['lead_score'], reverse=True)


# Convenience functions for enhanced scoring
def score_lead_enhanced(lead: Dict, weights: Optional[ScoringWeights] = None) -> Dict:
    """Quick function to score a lead with enhanced scoring."""
    scorer = EnhancedLeadScorer(weights)
    return scorer.score_lead(lead)


def batch_score_leads(leads: List[Dict], weights: Optional[ScoringWeights] = None) -> List[Dict]:
    """Batch score leads with enhanced scoring."""
    scorer = EnhancedLeadScorer(weights)
    return scorer.batch_score(leads)


# Singleton instance
_lead_scorer = None

def get_lead_scorer(openai_api_key: Optional[str] = None) -> LeadScorer:
    """Get or create the lead scorer instance."""
    global _lead_scorer
    if _lead_scorer is None:
        _lead_scorer = LeadScorer(openai_api_key)
    return _lead_scorer


def get_enhanced_scorer(weights: Optional[ScoringWeights] = None) -> EnhancedLeadScorer:
    """Get an enhanced lead scorer instance."""
    return EnhancedLeadScorer(weights)
