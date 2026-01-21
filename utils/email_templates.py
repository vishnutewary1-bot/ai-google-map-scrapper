"""Cold email template generator using scraped data."""
from typing import Dict, List, Optional
from dataclasses import dataclass
import re
from datetime import datetime
from loguru import logger


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
        },
        "social_proof": {
            "subject": "Loved your work at {business_name}",
            "body": """Hi{contact_name_greeting},

I've been following {business_name} and really appreciate the work you're doing in {city}.

{personalization_line}

I specialize in helping {category_lower} businesses {value_prop}, and I think there could be a great fit here.

Would you be open to a brief conversation about how we might work together?

Looking forward to hearing from you,
[Your Name]"""
        },
        "direct": {
            "subject": "{business_name} + [Your Company]",
            "body": """Hi{contact_name_greeting},

I'll keep this brief.

I noticed {business_name} is {rating_text} in the {category_lower} space in {city_state}.

{personalization_line}

We help businesses like yours {value_prop}.

Interested in a quick 10-minute call?

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
        "real estate": "generate more listings and buyer leads",
        "automotive": "drive more showroom visits and service appointments",
        "fitness": "increase membership sign-ups and retention",
        "beauty": "boost appointments and build client loyalty",
        "legal": "attract more qualified client consultations",
        "financial": "grow their client base with qualified prospects",
    }

    def generate_email(
        self,
        lead: Dict,
        template_name: str = "introduction",
        value_prop: Optional[str] = None,
        sender_name: str = "[Your Name]",
        company_name: str = "[Your Company]"
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
            replacements["rating_text"] = f"a leader with your stellar {rating}-star rating"
        elif rating and rating >= 4.0:
            replacements["rating_text"] = f"highly rated ({rating} stars)"
        elif rating:
            replacements["rating_text"] = f"doing well with your {rating}-star rating"
        else:
            replacements["rating_text"] = "well-regarded in the area"

        # Review count text
        if review_count and review_count >= 100:
            replacements["review_count_text"] = f"over {review_count} reviews"
        elif review_count and review_count >= 50:
            replacements["review_count_text"] = f"{review_count} positive reviews"
        elif review_count:
            replacements["review_count_text"] = f"{review_count} reviews"
        else:
            replacements["review_count_text"] = "great reviews"

        # Value proposition
        if value_prop:
            replacements["value_prop"] = value_prop
        else:
            # Try to match category to value prop
            category_lower = category.lower() if category else ""
            matched_prop = None
            for key, prop in self.VALUE_PROPS.items():
                if key in category_lower:
                    matched_prop = prop
                    break
            replacements["value_prop"] = matched_prop or self.VALUE_PROPS["default"]

        # Personalization line based on available data
        personalization_lines = []

        if lead.get("founded_year"):
            years = datetime.now().year - lead["founded_year"]
            if years > 10:
                personalization_lines.append(
                    f"I see you've been serving {city} for over {years} years - that's impressive longevity!"
                )
            elif years > 5:
                personalization_lines.append(
                    f"With {years} years in business, you clearly know what works in this market."
                )

        if lead.get("social_instagram"):
            personalization_lines.append(
                "I checked out your Instagram and love the content you're putting out."
            )

        if lead.get("social_linkedin"):
            personalization_lines.append(
                "I came across your LinkedIn profile and was impressed by your company's growth."
            )

        if lead.get("employees") and any(x in str(lead.get("employees", "")).lower() for x in ["50", "100", "200"]):
            personalization_lines.append(
                "As a growing team, you're probably always looking for ways to scale efficiently."
            )

        if review_count and review_count > 200:
            personalization_lines.append(
                f"With {review_count}+ reviews, you've clearly built a loyal customer base."
            )

        if lead.get("website"):
            personalization_lines.append(
                "I took a look at your website and really liked what I saw."
            )

        replacements["personalization_line"] = (
            personalization_lines[0] if personalization_lines
            else f"Based on what I see, {business_name} is doing great work in the community."
        )

        # PS line
        ps_lines = [
            "Feel free to check out my work at [your website]",
            "I'm happy to share case studies from similar businesses",
            "Even if the timing isn't right now, I'd love to connect",
            "No worries if you're too busy - I know running a business is demanding",
            "I've attached a quick overview of what we do"
        ]
        replacements["ps_line"] = ps_lines[hash(business_name) % len(ps_lines)]

        # Replace sender info
        replacements["sender_name"] = sender_name
        replacements["company_name"] = company_name

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
            score += 5

        # Has category
        if lead.get("category"):
            score += 5

        return min(100, score)

    def generate_batch(
        self,
        leads: List[Dict],
        template_name: str = "introduction",
        value_prop: Optional[str] = None
    ) -> List[Dict]:
        """Generate emails for multiple leads."""
        results = []

        for lead in leads:
            try:
                email = self.generate_email(lead, template_name, value_prop)
                results.append({
                    "lead_id": lead.get("id"),
                    "business_name": lead.get("business_name"),
                    "email_address": lead.get("email") or lead.get("contact_email_1"),
                    "contact_name": lead.get("contact_name_1"),
                    "subject": email.subject,
                    "body": email.body,
                    "personalization_score": email.personalization_score,
                    "has_email": bool(lead.get("email") or lead.get("contact_email_1"))
                })
            except Exception as e:
                logger.error(f"Error generating email for {lead.get('business_name')}: {e}")
                continue

        return results

    def get_available_templates(self) -> List[Dict]:
        """Get list of available email templates."""
        return [
            {
                "name": name,
                "subject_preview": template["subject"][:50],
                "description": self._get_template_description(name)
            }
            for name, template in self.TEMPLATES.items()
        ]

    def _get_template_description(self, template_name: str) -> str:
        """Get description for a template."""
        descriptions = {
            "introduction": "Friendly introduction with rating mention",
            "value_focused": "Focus on business value and reviews",
            "local_focused": "Emphasizes local business connection",
            "social_proof": "Leads with appreciation and social proof",
            "direct": "Short and direct approach"
        }
        return descriptions.get(template_name, "Email template")

    def get_value_props(self) -> Dict[str, str]:
        """Get available value propositions by category."""
        return self.VALUE_PROPS.copy()


# Singleton
email_generator = ColdEmailGenerator()


def generate_email(lead: Dict, template: str = "introduction") -> Dict:
    """Quick function to generate an email."""
    result = email_generator.generate_email(lead, template)
    return {
        "subject": result.subject,
        "body": result.body,
        "personalization_score": result.personalization_score
    }
