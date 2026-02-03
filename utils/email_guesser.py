"""Email pattern guessing based on domain and business name.

This module generates possible email addresses when no email is found,
based on common patterns used by businesses.
"""

import re
from typing import List, Dict, Optional
from urllib.parse import urlparse
from loguru import logger


class EmailGuesser:
    """
    Generates possible email addresses based on common patterns.
    Uses business name and website domain.
    """

    # Common email patterns (ordered by likelihood)
    PATTERNS = [
        "{first}@{domain}",           # john@company.com
        "{first}.{last}@{domain}",    # john.doe@company.com
        "{first}{last}@{domain}",     # johndoe@company.com
        "{f}{last}@{domain}",         # jdoe@company.com
        "info@{domain}",              # info@company.com
        "contact@{domain}",           # contact@company.com
        "hello@{domain}",             # hello@company.com
        "support@{domain}",           # support@company.com
        "sales@{domain}",             # sales@company.com
        "admin@{domain}",             # admin@company.com
        "enquiry@{domain}",           # enquiry@company.com
        "enquiries@{domain}",         # enquiries@company.com
        "office@{domain}",            # office@company.com
        "mail@{domain}",              # mail@company.com
        "{business}@{domain}",        # companyname@company.com
    ]

    def __init__(self):
        self.common_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']

    def extract_domain(self, website: str) -> Optional[str]:
        """Extract domain from website URL."""
        if not website:
            return None

        try:
            # Add protocol if missing
            if not website.startswith(('http://', 'https://')):
                website = 'https://' + website

            parsed = urlparse(website)
            domain = parsed.netloc

            # Remove www prefix
            if domain.startswith('www.'):
                domain = domain[4:]

            # Skip if it's a social media or common platform
            skip_domains = [
                'facebook.com', 'instagram.com', 'twitter.com', 'linkedin.com',
                'youtube.com', 'tiktok.com', 'google.com', 'yelp.com',
                'tripadvisor.com', 'wix.com', 'squarespace.com', 'wordpress.com',
                'weebly.com', 'godaddy.com', 'blogger.com', 'tumblr.com',
                'pinterest.com', 'medium.com', 'github.com', 'shopify.com'
            ]

            if any(skip in domain for skip in skip_domains):
                return None

            # Make sure domain has at least one dot
            if '.' not in domain:
                return None

            return domain
        except Exception as e:
            logger.debug(f"Error extracting domain from {website}: {e}")
            return None

    def extract_name_parts(self, business_name: str) -> Dict[str, str]:
        """Extract potential name parts from business name."""
        if not business_name:
            return {}

        # Clean business name
        name = business_name.lower()
        name = re.sub(r'[^\w\s]', '', name)

        # Remove common business suffixes
        suffixes = [
            'llc', 'inc', 'ltd', 'corp', 'co', 'company', 'enterprises',
            'services', 'group', 'solutions', 'consulting', 'pvt', 'private',
            'limited', 'international', 'global', 'associates', 'partners'
        ]
        words = name.split()
        words = [w for w in words if w not in suffixes]

        if not words:
            return {}

        return {
            'business': ''.join(words),
            'first': words[0] if words else '',
            'last': words[-1] if len(words) > 1 else words[0],
            'f': words[0][0] if words and words[0] else ''
        }

    def guess_emails(
        self,
        website: str,
        business_name: str,
        owner_name: Optional[str] = None,
        contact_name: Optional[str] = None,
        max_guesses: int = 5
    ) -> List[Dict[str, any]]:
        """
        Generate possible email addresses.

        Args:
            website: Business website URL
            business_name: Business name
            owner_name: Owner name if known
            contact_name: Contact person name if known
            max_guesses: Maximum number of guesses to return

        Returns:
            List of dicts with 'email', 'confidence', and 'pattern' keys
        """
        domain = self.extract_domain(website)
        if not domain:
            return []

        guesses = []

        # Get name parts from different sources
        name_parts = self.extract_name_parts(business_name)

        # If we have a contact/owner name, prioritize those patterns
        if contact_name or owner_name:
            person_name = contact_name or owner_name
            person_parts = self._parse_person_name(person_name)
            if person_parts:
                name_parts.update(person_parts)

        # Generate emails from patterns
        seen = set()
        for i, pattern in enumerate(self.PATTERNS):
            try:
                email = pattern.format(
                    first=name_parts.get('first', 'info'),
                    last=name_parts.get('last', ''),
                    f=name_parts.get('f', 'i'),
                    business=name_parts.get('business', 'info'),
                    domain=domain
                )

                # Clean up and validate
                email = email.lower().strip()

                # Skip if empty parts result in double @@ or similar issues
                if '@@' in email or email.startswith('@') or '@.' in email:
                    continue

                if email not in seen and self._is_valid_format(email):
                    seen.add(email)

                    # Calculate confidence (higher patterns = higher confidence)
                    confidence = max(0.3, 0.9 - (i * 0.05))

                    # Boost confidence for generic emails
                    local_part = email.split('@')[0]
                    if local_part in ['info', 'contact', 'hello', 'sales', 'support']:
                        confidence = min(0.95, confidence + 0.1)

                    guesses.append({
                        'email': email,
                        'confidence': round(confidence, 2),
                        'pattern': pattern,
                        'is_generic': local_part in ['info', 'contact', 'hello', 'sales', 'support', 'admin', 'office']
                    })
            except KeyError:
                continue

        # Sort by confidence and limit
        guesses.sort(key=lambda x: x['confidence'], reverse=True)

        logger.debug(f"Generated {len(guesses[:max_guesses])} email guesses for domain {domain}")
        return guesses[:max_guesses]

    def _parse_person_name(self, name: str) -> Dict[str, str]:
        """Parse a person's name into first/last."""
        if not name:
            return {}

        name = name.lower().strip()
        # Remove titles
        titles = ['mr', 'mrs', 'ms', 'dr', 'prof', 'sir', 'madam']
        parts = name.split()
        parts = [p for p in parts if p.rstrip('.') not in titles]

        if len(parts) >= 2:
            return {
                'first': parts[0],
                'last': parts[-1],
                'f': parts[0][0] if parts[0] else ''
            }
        elif len(parts) == 1:
            return {
                'first': parts[0],
                'last': parts[0],
                'f': parts[0][0] if parts[0] else ''
            }
        return {}

    def _is_valid_format(self, email: str) -> bool:
        """Check if email has valid format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))


# Convenience function
def guess_business_emails(
    website: str,
    business_name: str,
    owner_name: Optional[str] = None,
    contact_name: Optional[str] = None,
    max_guesses: int = 5
) -> List[Dict]:
    """
    Convenience function to guess emails for a business.

    Args:
        website: Business website URL
        business_name: Business name
        owner_name: Owner name if known (optional)
        contact_name: Contact person name if known (optional)
        max_guesses: Maximum number of guesses to return (default: 5)

    Returns:
        List of dicts with 'email', 'confidence', 'pattern', 'is_generic' keys
    """
    guesser = EmailGuesser()
    return guesser.guess_emails(
        website=website,
        business_name=business_name,
        owner_name=owner_name,
        contact_name=contact_name,
        max_guesses=max_guesses
    )


# Alias for backward compatibility
EmailPatternGuesser = EmailGuesser
