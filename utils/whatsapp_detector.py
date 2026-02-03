"""WhatsApp number detection and formatting.

This module detects if a phone number is likely a WhatsApp number
and generates WhatsApp click-to-chat links.
"""

import re
from typing import Optional, Tuple, Dict
from urllib.parse import quote
from loguru import logger


class WhatsAppDetector:
    """
    Detects if a phone number is likely a WhatsApp number
    and generates WhatsApp links.
    """

    # Country codes with high WhatsApp usage
    HIGH_WHATSAPP_COUNTRIES = {
        '1': 'US/CA',      # USA/Canada
        '44': 'UK',        # UK
        '91': 'IN',        # India (very high)
        '55': 'BR',        # Brazil (very high)
        '52': 'MX',        # Mexico
        '62': 'ID',        # Indonesia
        '234': 'NG',       # Nigeria
        '27': 'ZA',        # South Africa
        '49': 'DE',        # Germany
        '33': 'FR',        # France
        '34': 'ES',        # Spain
        '39': 'IT',        # Italy
        '81': 'JP',        # Japan
        '82': 'KR',        # South Korea
        '86': 'CN',        # China (limited)
        '61': 'AU',        # Australia
        '971': 'UAE',      # UAE
        '966': 'SA',       # Saudi Arabia
        '92': 'PK',        # Pakistan
        '880': 'BD',       # Bangladesh
        '63': 'PH',        # Philippines
        '84': 'VN',        # Vietnam
        '66': 'TH',        # Thailand
        '60': 'MY',        # Malaysia
        '65': 'SG',        # Singapore
        '20': 'EG',        # Egypt
        '254': 'KE',       # Kenya
        '255': 'TZ',       # Tanzania
        '256': 'UG',       # Uganda
        '233': 'GH',       # Ghana
        '225': 'CI',       # Ivory Coast
        '212': 'MA',       # Morocco
        '213': 'DZ',       # Algeria
        '216': 'TN',       # Tunisia
        '90': 'TR',        # Turkey
        '7': 'RU',         # Russia
        '380': 'UA',       # Ukraine
        '48': 'PL',        # Poland
        '31': 'NL',        # Netherlands
        '32': 'BE',        # Belgium
        '41': 'CH',        # Switzerland
        '43': 'AT',        # Austria
        '351': 'PT',       # Portugal
        '30': 'GR',        # Greece
        '46': 'SE',        # Sweden
        '47': 'NO',        # Norway
        '45': 'DK',        # Denmark
        '358': 'FI',       # Finland
        '353': 'IE',       # Ireland
        '972': 'IL',       # Israel
        '54': 'AR',        # Argentina
        '56': 'CL',        # Chile
        '57': 'CO',        # Colombia
        '51': 'PE',        # Peru
        '58': 'VE',        # Venezuela
        '593': 'EC',       # Ecuador
    }

    # Mobile number patterns by country (simplified)
    MOBILE_PATTERNS = {
        '91': r'^[6-9]\d{9}$',       # India: 10 digits starting with 6-9
        '1': r'^\d{10}$',            # US/CA: 10 digits
        '44': r'^7\d{9}$',           # UK: 10 digits starting with 7
        '55': r'^\d{10,11}$',        # Brazil: 10-11 digits
        '62': r'^8\d{9,11}$',        # Indonesia: starts with 8
        '63': r'^9\d{9}$',           # Philippines: starts with 9
        '92': r'^3\d{9}$',           # Pakistan: starts with 3
        '880': r'^1\d{9}$',          # Bangladesh: starts with 1
        '49': r'^1[567]\d{8,9}$',    # Germany: starts with 15, 16, or 17
        '33': r'^[67]\d{8}$',        # France: starts with 6 or 7
        '34': r'^[67]\d{8}$',        # Spain: starts with 6 or 7
    }

    # Countries with very high WhatsApp penetration (>70%)
    VERY_HIGH_ADOPTION = {'91', '55', '62', '234', '92', '880', '63', '52', '54', '57', '51'}

    def clean_phone(self, phone: str) -> str:
        """Remove all non-digit characters."""
        if not phone:
            return ''
        # Keep only digits
        return re.sub(r'[^\d]', '', phone)

    def extract_country_code(self, phone: str) -> Tuple[Optional[str], str]:
        """
        Extract country code from phone number.
        Returns (country_code, remaining_number).
        """
        cleaned = self.clean_phone(phone)

        # Try 3-digit, then 2-digit, then 1-digit country codes
        for length in [3, 2, 1]:
            if len(cleaned) > length:
                potential_code = cleaned[:length]
                if potential_code in self.HIGH_WHATSAPP_COUNTRIES:
                    return potential_code, cleaned[length:]

        return None, cleaned

    def is_mobile_number(self, phone: str, country_code: Optional[str] = None) -> bool:
        """Check if number appears to be a mobile number."""
        cleaned = self.clean_phone(phone)

        if not country_code:
            country_code, cleaned = self.extract_country_code(phone)

        if country_code and country_code in self.MOBILE_PATTERNS:
            pattern = self.MOBILE_PATTERNS[country_code]
            return bool(re.match(pattern, cleaned))

        # Default: assume mobile if it's the right length (10+ digits)
        return len(cleaned) >= 10

    def format_for_whatsapp(self, phone: str, default_country: str = '91') -> str:
        """
        Format phone number for WhatsApp API.
        Returns number in format: country_code + number (no + or spaces)
        """
        cleaned = self.clean_phone(phone)

        if not cleaned:
            return ''

        # Check if it already has a country code
        country_code, number = self.extract_country_code(cleaned)

        if country_code:
            return cleaned  # Already has country code
        else:
            # Add default country code
            return default_country + cleaned

    def generate_whatsapp_link(
        self,
        phone: str,
        message: Optional[str] = None,
        default_country: str = '91'
    ) -> str:
        """
        Generate WhatsApp click-to-chat link.

        Args:
            phone: Phone number
            message: Optional pre-filled message
            default_country: Default country code if not present

        Returns:
            WhatsApp URL (wa.me link)
        """
        formatted = self.format_for_whatsapp(phone, default_country)

        if not formatted:
            return ''

        if message:
            return f"https://wa.me/{formatted}?text={quote(message)}"
        else:
            return f"https://wa.me/{formatted}"

    def detect_whatsapp_likelihood(
        self,
        phone: str,
        country: Optional[str] = None,
        default_country: str = '91'
    ) -> Dict:
        """
        Detect likelihood that a phone number has WhatsApp.

        Args:
            phone: Phone number to analyze
            country: Optional country name/code hint
            default_country: Default country code for formatting

        Returns:
            Dict with 'likely_whatsapp', 'confidence', 'whatsapp_link', 'country_code'
        """
        if not phone:
            return {
                'likely_whatsapp': False,
                'confidence': 0,
                'whatsapp_link': None,
                'country_code': None,
                'formatted_number': None
            }

        cleaned = self.clean_phone(phone)

        if len(cleaned) < 10:
            return {
                'likely_whatsapp': False,
                'confidence': 0,
                'whatsapp_link': None,
                'country_code': None,
                'formatted_number': None,
                'reason': 'Phone number too short'
            }

        country_code, number = self.extract_country_code(cleaned)

        # Base confidence based on country
        if country_code in self.VERY_HIGH_ADOPTION:
            confidence = 0.85  # Very high WhatsApp adoption country
        elif country_code in self.HIGH_WHATSAPP_COUNTRIES:
            confidence = 0.65  # High WhatsApp adoption country
        else:
            confidence = 0.35  # Unknown or low adoption

        # Boost if it looks like a mobile number
        if self.is_mobile_number(phone, country_code):
            confidence += 0.10

        # Cap confidence
        confidence = min(0.95, confidence)

        formatted_number = self.format_for_whatsapp(phone, default_country)

        return {
            'likely_whatsapp': confidence >= 0.5,
            'confidence': round(confidence, 2),
            'whatsapp_link': self.generate_whatsapp_link(phone, default_country=default_country) if confidence >= 0.4 else None,
            'country_code': country_code,
            'country_name': self.HIGH_WHATSAPP_COUNTRIES.get(country_code, 'Unknown'),
            'formatted_number': formatted_number,
            'is_mobile': self.is_mobile_number(phone, country_code)
        }


# Convenience function
def detect_whatsapp(
    phone: str,
    country: Optional[str] = None,
    default_country: str = '91'
) -> Dict:
    """
    Quick function to detect WhatsApp likelihood.

    Args:
        phone: Phone number to analyze
        country: Optional country name/code hint
        default_country: Default country code for formatting (default: India '91')

    Returns:
        Dict with WhatsApp detection results
    """
    detector = WhatsAppDetector()
    return detector.detect_whatsapp_likelihood(phone, country, default_country)


def generate_whatsapp_link(
    phone: str,
    message: Optional[str] = None,
    default_country: str = '91'
) -> str:
    """
    Generate WhatsApp click-to-chat link.

    Args:
        phone: Phone number
        message: Optional pre-filled message
        default_country: Default country code if not present

    Returns:
        WhatsApp URL (wa.me link)
    """
    detector = WhatsAppDetector()
    return detector.generate_whatsapp_link(phone, message, default_country)


# Alias for backward compatibility
WhatsAppNumberDetector = WhatsAppDetector
