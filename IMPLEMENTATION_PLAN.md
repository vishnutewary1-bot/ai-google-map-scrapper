# MapLeads Pro - Feature Implementation Plan

## Overview

This document provides a detailed step-by-step implementation plan for adding new features to MapLeads Pro without disturbing existing functionality. Each feature is self-contained and can be implemented independently.

**Current Codebase Structure:**
```
ai-google-map-scrapper/
├── api/
│   ├── routes/          # API endpoints
│   ├── schemas/         # Pydantic request/response schemas
│   └── services/        # Business logic services
├── scraper/
│   ├── extractors/      # Data extractors (maps, contact, social, etc.)
│   ├── browser_engine.py
│   ├── unified_scraper.py
│   └── scheduler.py
├── database/
│   ├── models.py        # SQLAlchemy models
│   └── connection.py
├── utils/               # Utility modules
└── frontend/
    └── app.js           # Frontend JavaScript
```

---

## PHASE 1: Core Enhancements (No External Dependencies)

### Feature 1.1: Email Pattern Guessing

**Purpose:** Generate possible email addresses when no email is found, based on common patterns.

**Files to Create:**
- `utils/email_guesser.py`

**Files to Modify:**
- `scraper/unified_scraper.py` (add guessing after website extraction fails)
- `database/models.py` (add `guessed_emails` field)
- `api/schemas/responses.py` (include guessed emails in response)
- `frontend/app.js` (display guessed emails with indicator)

**Implementation Steps:**

```python
# Step 1: Create utils/email_guesser.py

"""Email pattern guessing based on domain and business name."""
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse


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
                'tripadvisor.com', 'wix.com', 'squarespace.com', 'wordpress.com'
            ]

            if any(skip in domain for skip in skip_domains):
                return None

            return domain
        except:
            return None

    def extract_name_parts(self, business_name: str) -> Dict[str, str]:
        """Extract potential name parts from business name."""
        if not business_name:
            return {}

        # Clean business name
        name = business_name.lower()
        name = re.sub(r'[^\w\s]', '', name)

        # Remove common business suffixes
        suffixes = ['llc', 'inc', 'ltd', 'corp', 'co', 'company', 'enterprises', 'services', 'group']
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
            List of dicts with 'email' and 'confidence' keys
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
                if email not in seen and self._is_valid_format(email):
                    seen.add(email)

                    # Calculate confidence (higher patterns = higher confidence)
                    confidence = max(0.3, 0.9 - (i * 0.05))

                    # Boost confidence for generic emails
                    if email.split('@')[0] in ['info', 'contact', 'hello', 'sales']:
                        confidence = min(0.95, confidence + 0.1)

                    guesses.append({
                        'email': email,
                        'confidence': round(confidence, 2),
                        'pattern': pattern
                    })
            except KeyError:
                continue

        # Sort by confidence and limit
        guesses.sort(key=lambda x: x['confidence'], reverse=True)
        return guesses[:max_guesses]

    def _parse_person_name(self, name: str) -> Dict[str, str]:
        """Parse a person's name into first/last."""
        if not name:
            return {}

        name = name.lower().strip()
        parts = name.split()

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
    max_guesses: int = 5
) -> List[Dict]:
    """Convenience function to guess emails for a business."""
    guesser = EmailGuesser()
    return guesser.guess_emails(website, business_name, owner_name, max_guesses=max_guesses)
```

```python
# Step 2: Modify database/models.py - Add field to BusinessLead class

# Add after email_3 field (around line 65):
guessed_emails = Column(JSON, nullable=True)  # AI-guessed email patterns
```

```python
# Step 3: Modify scraper/unified_scraper.py - Add guessing logic

# Add import at top:
from utils.email_guesser import guess_business_emails

# In _scrape_listing() method, after website enrichment (around line 200):
# If no email found, try guessing
if not lead_data.get('email') and lead_data.get('website'):
    guessed = guess_business_emails(
        website=lead_data.get('website'),
        business_name=lead_data.get('business_name'),
        owner_name=lead_data.get('owner_name'),
        max_guesses=3
    )
    if guessed:
        lead_data['guessed_emails'] = guessed
        logger.info(f"Generated {len(guessed)} email guesses for {lead_data.get('business_name')}")
```

```javascript
// Step 4: Modify frontend/app.js - Display guessed emails

// In renderLeadCard function, add after email display:
if (lead.guessed_emails && lead.guessed_emails.length > 0) {
    const guessedHtml = lead.guessed_emails.map(g =>
        `<span class="guessed-email" title="Confidence: ${g.confidence * 100}%">
            ${g.email} <i class="fas fa-question-circle"></i>
        </span>`
    ).join(', ');
    html += `<p><strong>Possible Emails:</strong> ${guessedHtml}</p>`;
}
```

---

### Feature 1.2: WhatsApp Number Detection

**Purpose:** Identify and format WhatsApp-compatible phone numbers.

**Files to Create:**
- `utils/whatsapp_detector.py`

**Files to Modify:**
- `scraper/unified_scraper.py`
- `database/models.py` (add `whatsapp_number` and `whatsapp_link` fields)
- `frontend/app.js`

**Implementation Steps:**

```python
# Step 1: Create utils/whatsapp_detector.py

"""WhatsApp number detection and formatting."""
import re
from typing import Optional, Tuple


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
    }

    # Mobile number patterns by country (simplified)
    MOBILE_PATTERNS = {
        '91': r'^[6-9]\d{9}$',       # India: 10 digits starting with 6-9
        '1': r'^\d{10}$',            # US/CA: 10 digits
        '44': r'^7\d{9}$',           # UK: 10 digits starting with 7
        '55': r'^\d{10,11}$',        # Brazil: 10-11 digits
    }

    def clean_phone(self, phone: str) -> str:
        """Remove all non-digit characters except +."""
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

        if country_code in self.MOBILE_PATTERNS:
            pattern = self.MOBILE_PATTERNS[country_code]
            return bool(re.match(pattern, cleaned))

        # Default: assume mobile if it's the right length
        return len(cleaned) >= 10

    def format_for_whatsapp(self, phone: str, default_country: str = '91') -> str:
        """
        Format phone number for WhatsApp API.
        Returns number in format: country_code + number (no + or spaces)
        """
        cleaned = self.clean_phone(phone)

        # If number starts with +, remove it
        if cleaned.startswith('+'):
            cleaned = cleaned[1:]

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

        if message:
            from urllib.parse import quote
            return f"https://wa.me/{formatted}?text={quote(message)}"
        else:
            return f"https://wa.me/{formatted}"

    def detect_whatsapp_likelihood(self, phone: str, country: Optional[str] = None) -> dict:
        """
        Detect likelihood that a phone number has WhatsApp.

        Returns:
            Dict with 'likely_whatsapp', 'confidence', 'whatsapp_link'
        """
        if not phone:
            return {'likely_whatsapp': False, 'confidence': 0, 'whatsapp_link': None}

        cleaned = self.clean_phone(phone)
        country_code, number = self.extract_country_code(cleaned)

        # Base confidence based on country
        if country_code in self.HIGH_WHATSAPP_COUNTRIES:
            confidence = 0.7  # High WhatsApp adoption country
        else:
            confidence = 0.4  # Unknown or low adoption

        # Boost if it looks like a mobile number
        if self.is_mobile_number(phone, country_code):
            confidence += 0.2

        # India and Brazil have very high WhatsApp penetration
        if country_code in ['91', '55']:
            confidence += 0.1

        confidence = min(0.95, confidence)

        return {
            'likely_whatsapp': confidence >= 0.6,
            'confidence': round(confidence, 2),
            'whatsapp_link': self.generate_whatsapp_link(phone) if confidence >= 0.5 else None,
            'country_code': country_code
        }


# Convenience function
def detect_whatsapp(phone: str) -> dict:
    """Quick function to detect WhatsApp likelihood."""
    detector = WhatsAppDetector()
    return detector.detect_whatsapp_likelihood(phone)
```

```python
# Step 2: Modify database/models.py - Add fields

# Add after social_whatsapp field (around line 86):
whatsapp_number = Column(String(50), nullable=True)  # Formatted WhatsApp number
whatsapp_link = Column(String(200), nullable=True)   # wa.me link
whatsapp_likelihood = Column(Float, nullable=True)   # 0-1 confidence score
```

```python
# Step 3: Modify scraper/unified_scraper.py

# Add import:
from utils.whatsapp_detector import detect_whatsapp

# In _scrape_listing(), after phone extraction:
if lead_data.get('phone'):
    wa_result = detect_whatsapp(lead_data['phone'])
    if wa_result['likely_whatsapp']:
        lead_data['whatsapp_number'] = lead_data['phone']
        lead_data['whatsapp_link'] = wa_result['whatsapp_link']
        lead_data['whatsapp_likelihood'] = wa_result['confidence']
```

---

### Feature 1.3: Business Hours Analysis

**Purpose:** Analyze business hours to identify optimal contact times.

**Files to Create:**
- `utils/hours_analyzer.py`

**Files to Modify:**
- `scraper/unified_scraper.py`
- `database/models.py`
- `frontend/app.js`

**Implementation Steps:**

```python
# Step 1: Create utils/hours_analyzer.py

"""Business hours analysis for optimal contact timing."""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time
import re


class HoursAnalyzer:
    """
    Analyzes business hours to determine:
    - Best time to call/contact
    - If business is currently open
    - Weekly availability patterns
    """

    DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

    def __init__(self):
        self.timezone_offset = 0  # Hours from UTC

    def parse_hours_string(self, hours_str: str) -> Optional[Tuple[time, time]]:
        """
        Parse hours string like "9:00 AM - 5:00 PM" into time objects.
        Returns (open_time, close_time) or None if closed.
        """
        if not hours_str:
            return None

        hours_str = hours_str.lower().strip()

        # Handle closed
        if hours_str in ['closed', 'fermé', 'cerrado', 'geschlossen']:
            return None

        # Handle 24 hours
        if '24' in hours_str or 'open 24' in hours_str:
            return (time(0, 0), time(23, 59))

        # Try to parse time range
        patterns = [
            r'(\d{1,2}):?(\d{2})?\s*(am|pm)?\s*[-–to]+\s*(\d{1,2}):?(\d{2})?\s*(am|pm)?',
            r'(\d{1,2})\s*(am|pm)\s*[-–to]+\s*(\d{1,2})\s*(am|pm)',
        ]

        for pattern in patterns:
            match = re.search(pattern, hours_str, re.IGNORECASE)
            if match:
                groups = match.groups()
                try:
                    open_time = self._parse_time(groups[:3])
                    close_time = self._parse_time(groups[3:])
                    return (open_time, close_time)
                except:
                    continue

        return None

    def _parse_time(self, parts: tuple) -> time:
        """Parse time parts into time object."""
        hour = int(parts[0]) if parts[0] else 0
        minute = int(parts[1]) if parts[1] else 0
        period = parts[2].lower() if len(parts) > 2 and parts[2] else None

        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0

        return time(hour % 24, minute)

    def analyze_hours(self, hours_data: Dict[str, str]) -> Dict:
        """
        Analyze business hours from dict like:
        {'monday': '9:00 AM - 5:00 PM', 'tuesday': '...', ...}

        Returns analysis with best contact times, patterns, etc.
        """
        result = {
            'is_open_now': False,
            'best_call_times': [],
            'total_hours_per_week': 0,
            'open_days': [],
            'closed_days': [],
            'opening_pattern': 'unknown',  # regular, extended, limited, 24/7
            'earliest_opening': None,
            'latest_closing': None,
            'weekend_hours': False,
        }

        parsed_hours = {}
        total_minutes = 0

        for day in self.DAYS:
            day_key = f'hours_{day}' if f'hours_{day}' in hours_data else day
            hours_str = hours_data.get(day_key) or hours_data.get(day)

            times = self.parse_hours_string(hours_str) if hours_str else None
            parsed_hours[day] = times

            if times:
                result['open_days'].append(day.capitalize())

                # Calculate hours for this day
                open_time, close_time = times
                if close_time > open_time:
                    minutes = (close_time.hour * 60 + close_time.minute) - \
                              (open_time.hour * 60 + open_time.minute)
                else:  # Crosses midnight
                    minutes = (24 * 60 - (open_time.hour * 60 + open_time.minute)) + \
                              (close_time.hour * 60 + close_time.minute)
                total_minutes += minutes

                # Track earliest/latest
                if not result['earliest_opening'] or open_time < result['earliest_opening']:
                    result['earliest_opening'] = open_time.strftime('%I:%M %p')
                if not result['latest_closing'] or close_time > result['latest_closing']:
                    result['latest_closing'] = close_time.strftime('%I:%M %p')
            else:
                result['closed_days'].append(day.capitalize())

        # Calculate total hours
        result['total_hours_per_week'] = round(total_minutes / 60, 1)

        # Check weekend hours
        if parsed_hours.get('saturday') or parsed_hours.get('sunday'):
            result['weekend_hours'] = True

        # Determine pattern
        if result['total_hours_per_week'] >= 140:
            result['opening_pattern'] = '24/7'
        elif result['total_hours_per_week'] >= 60:
            result['opening_pattern'] = 'extended'
        elif result['total_hours_per_week'] >= 40:
            result['opening_pattern'] = 'regular'
        elif result['total_hours_per_week'] > 0:
            result['opening_pattern'] = 'limited'

        # Generate best call times
        result['best_call_times'] = self._calculate_best_call_times(parsed_hours)

        # Check if currently open
        result['is_open_now'] = self._is_currently_open(parsed_hours)

        return result

    def _calculate_best_call_times(self, parsed_hours: Dict) -> List[Dict]:
        """Calculate the best times to call based on typical business patterns."""
        best_times = []

        # Best time is usually mid-morning (avoid early rush) on weekdays
        for day in ['tuesday', 'wednesday', 'thursday']:
            times = parsed_hours.get(day)
            if times:
                open_time, close_time = times

                # Suggest 10-11 AM or 2-3 PM (after lunch)
                mid_morning = time(10, 30)
                afternoon = time(14, 30)

                if open_time <= mid_morning and close_time > time(11, 0):
                    best_times.append({
                        'day': day.capitalize(),
                        'time': '10:30 AM',
                        'reason': 'Mid-morning, settled after opening'
                    })

                if open_time <= afternoon and close_time > time(15, 0):
                    best_times.append({
                        'day': day.capitalize(),
                        'time': '2:30 PM',
                        'reason': 'Afternoon, after lunch rush'
                    })

        return best_times[:3]  # Top 3 suggestions

    def _is_currently_open(self, parsed_hours: Dict) -> bool:
        """Check if business is currently open."""
        now = datetime.now()
        day_name = self.DAYS[now.weekday()]
        current_time = now.time()

        times = parsed_hours.get(day_name)
        if times:
            open_time, close_time = times
            if close_time > open_time:
                return open_time <= current_time <= close_time
            else:  # Crosses midnight
                return current_time >= open_time or current_time <= close_time

        return False


# Convenience function
def analyze_business_hours(hours_dict: Dict[str, str]) -> Dict:
    """Analyze business hours and return insights."""
    analyzer = HoursAnalyzer()
    return analyzer.analyze_hours(hours_dict)
```

---

### Feature 1.4: Advanced Duplicate Detection

**Purpose:** Improve deduplication using fuzzy matching and multiple criteria.

**Files to Modify:**
- `utils/deduplicator.py` (enhance existing)
- `api/routes/leads.py` (add duplicate detection endpoint)
- `frontend/app.js` (add merge UI)

**Implementation Steps:**

```python
# Step 1: Enhance utils/deduplicator.py - Add fuzzy matching

# Add to existing deduplicator.py:

from difflib import SequenceMatcher
from typing import List, Dict, Tuple
import re


class AdvancedDeduplicator:
    """Enhanced deduplication with fuzzy matching."""

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold

    def normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison."""
        if not phone:
            return ''
        # Remove all non-digits
        return re.sub(r'\D', '', phone)[-10:]  # Keep last 10 digits

    def normalize_name(self, name: str) -> str:
        """Normalize business name for comparison."""
        if not name:
            return ''
        # Lowercase, remove punctuation, extra spaces
        name = name.lower()
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', ' ', name).strip()

        # Remove common suffixes
        suffixes = ['llc', 'inc', 'ltd', 'corp', 'co', 'pvt', 'private', 'limited']
        words = name.split()
        words = [w for w in words if w not in suffixes]

        return ' '.join(words)

    def calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using SequenceMatcher."""
        if not str1 or not str2:
            return 0.0
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def find_duplicates(self, leads: List[Dict]) -> List[Dict]:
        """
        Find potential duplicate leads.

        Returns list of duplicate groups with similarity scores.
        """
        duplicates = []
        checked = set()

        for i, lead1 in enumerate(leads):
            if i in checked:
                continue

            group = {
                'primary': lead1,
                'duplicates': [],
                'match_reasons': []
            }

            for j, lead2 in enumerate(leads[i+1:], i+1):
                if j in checked:
                    continue

                match_score, reasons = self._compare_leads(lead1, lead2)

                if match_score >= self.similarity_threshold:
                    checked.add(j)
                    group['duplicates'].append({
                        'lead': lead2,
                        'score': match_score,
                        'reasons': reasons
                    })

            if group['duplicates']:
                checked.add(i)
                duplicates.append(group)

        return duplicates

    def _compare_leads(self, lead1: Dict, lead2: Dict) -> Tuple[float, List[str]]:
        """Compare two leads and return match score with reasons."""
        scores = []
        reasons = []

        # Exact place_id match (definitive)
        if lead1.get('place_id') and lead1.get('place_id') == lead2.get('place_id'):
            return 1.0, ['Same Google Place ID']

        # Phone number match (strong indicator)
        phone1 = self.normalize_phone(lead1.get('phone', ''))
        phone2 = self.normalize_phone(lead2.get('phone', ''))
        if phone1 and phone1 == phone2:
            scores.append(0.95)
            reasons.append('Same phone number')

        # Name similarity
        name1 = self.normalize_name(lead1.get('business_name', ''))
        name2 = self.normalize_name(lead2.get('business_name', ''))
        name_sim = self.calculate_similarity(name1, name2)
        if name_sim >= 0.8:
            scores.append(name_sim * 0.8)
            reasons.append(f'Similar name ({int(name_sim*100)}%)')

        # Address similarity
        addr1 = (lead1.get('full_address') or '').lower()
        addr2 = (lead2.get('full_address') or '').lower()
        if addr1 and addr2:
            addr_sim = self.calculate_similarity(addr1, addr2)
            if addr_sim >= 0.7:
                scores.append(addr_sim * 0.6)
                reasons.append(f'Similar address ({int(addr_sim*100)}%)')

        # Website match
        if lead1.get('website') and lead1.get('website') == lead2.get('website'):
            scores.append(0.9)
            reasons.append('Same website')

        # Email match
        if lead1.get('email') and lead1.get('email') == lead2.get('email'):
            scores.append(0.85)
            reasons.append('Same email')

        # Calculate weighted average
        if scores:
            final_score = sum(scores) / len(scores)
            return final_score, reasons

        return 0.0, []

    def merge_leads(self, primary: Dict, secondary: Dict) -> Dict:
        """Merge two leads, preferring non-null values from primary."""
        merged = primary.copy()

        for key, value in secondary.items():
            if not merged.get(key) and value:
                merged[key] = value

        # Combine arrays
        array_fields = ['photos', 'reviews', 'subcategories', 'guessed_emails']
        for field in array_fields:
            if primary.get(field) and secondary.get(field):
                merged[field] = list(set(primary[field] + secondary[field]))

        return merged
```

---

### Feature 1.5: Review Analysis Enhancement

**Purpose:** Extract detailed insights from reviews including keywords, sentiment trends, and response rates.

**Files to Create:**
- `utils/review_analyzer.py`

**Files to Modify:**
- `scraper/extractors/review_extractor.py`
- `database/models.py`
- `frontend/app.js`

**Implementation Steps:**

```python
# Step 1: Create utils/review_analyzer.py

"""Enhanced review analysis with keyword extraction and trends."""
import re
from typing import Dict, List, Optional
from collections import Counter
from datetime import datetime


class ReviewAnalyzer:
    """
    Analyzes reviews to extract:
    - Common keywords/topics
    - Sentiment trends over time
    - Owner response rate
    - Highlighted phrases
    """

    # Positive/negative indicator words
    POSITIVE_WORDS = {
        'excellent', 'amazing', 'great', 'wonderful', 'fantastic', 'best',
        'friendly', 'helpful', 'professional', 'quick', 'clean', 'delicious',
        'recommend', 'love', 'awesome', 'perfect', 'outstanding'
    }

    NEGATIVE_WORDS = {
        'terrible', 'awful', 'worst', 'bad', 'poor', 'horrible', 'rude',
        'slow', 'dirty', 'expensive', 'disappointing', 'avoid', 'never',
        'unprofessional', 'waste', 'overpriced'
    }

    # Common stop words to exclude
    STOP_WORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
        'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
        'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'up',
        'about', 'into', 'over', 'after', 'and', 'but', 'or', 'not', 'very'
    }

    def extract_keywords(self, reviews: List[Dict], top_n: int = 10) -> List[Dict]:
        """
        Extract most common meaningful keywords from reviews.

        Returns list of {keyword, count, sentiment} dicts.
        """
        word_counts = Counter()
        word_sentiment = {}

        for review in reviews:
            text = (review.get('text') or '').lower()
            rating = review.get('rating', 3)

            # Extract words
            words = re.findall(r'\b[a-z]{3,}\b', text)

            for word in words:
                if word not in self.STOP_WORDS:
                    word_counts[word] += 1

                    # Track sentiment association
                    if word not in word_sentiment:
                        word_sentiment[word] = {'positive': 0, 'negative': 0}
                    if rating >= 4:
                        word_sentiment[word]['positive'] += 1
                    elif rating <= 2:
                        word_sentiment[word]['negative'] += 1

        # Get top keywords
        keywords = []
        for word, count in word_counts.most_common(top_n):
            sentiment = word_sentiment.get(word, {})
            pos = sentiment.get('positive', 0)
            neg = sentiment.get('negative', 0)

            if pos > neg * 2:
                sent_label = 'positive'
            elif neg > pos * 2:
                sent_label = 'negative'
            else:
                sent_label = 'neutral'

            keywords.append({
                'keyword': word,
                'count': count,
                'sentiment': sent_label
            })

        return keywords

    def analyze_trends(self, reviews: List[Dict]) -> Dict:
        """
        Analyze rating trends over time.

        Returns trend data including direction and momentum.
        """
        if not reviews or len(reviews) < 3:
            return {'trend': 'insufficient_data', 'momentum': 0}

        # Sort by date
        dated_reviews = []
        for r in reviews:
            date_str = r.get('date') or r.get('relative_date')
            if date_str:
                dated_reviews.append({
                    'rating': r.get('rating', 0),
                    'date': date_str
                })

        if len(dated_reviews) < 3:
            return {'trend': 'insufficient_data', 'momentum': 0}

        # Simple trend: compare first half vs second half average
        mid = len(dated_reviews) // 2
        first_half_avg = sum(r['rating'] for r in dated_reviews[:mid]) / mid
        second_half_avg = sum(r['rating'] for r in dated_reviews[mid:]) / (len(dated_reviews) - mid)

        diff = second_half_avg - first_half_avg

        if diff > 0.3:
            trend = 'improving'
        elif diff < -0.3:
            trend = 'declining'
        else:
            trend = 'stable'

        return {
            'trend': trend,
            'momentum': round(diff, 2),
            'early_average': round(first_half_avg, 2),
            'recent_average': round(second_half_avg, 2)
        }

    def calculate_response_rate(self, reviews: List[Dict]) -> Dict:
        """Calculate owner response rate to reviews."""
        total = len(reviews)
        responded = sum(1 for r in reviews if r.get('owner_response'))

        if total == 0:
            return {'response_rate': 0, 'total_reviews': 0, 'responses': 0}

        return {
            'response_rate': round(responded / total * 100, 1),
            'total_reviews': total,
            'responses': responded,
            'engagement_level': 'high' if responded/total > 0.5 else 'medium' if responded/total > 0.2 else 'low'
        }

    def extract_highlights(self, reviews: List[Dict], max_highlights: int = 5) -> List[str]:
        """Extract notable phrases/sentences from reviews."""
        highlights = []

        for review in reviews:
            if review.get('rating', 0) >= 4:
                text = review.get('text', '')
                sentences = re.split(r'[.!?]', text)

                for sentence in sentences:
                    sentence = sentence.strip()
                    if 20 < len(sentence) < 150:
                        # Check for positive indicators
                        lower = sentence.lower()
                        if any(w in lower for w in self.POSITIVE_WORDS):
                            highlights.append(sentence)

        # Return unique highlights
        seen = set()
        unique = []
        for h in highlights:
            if h.lower() not in seen:
                seen.add(h.lower())
                unique.append(h)

        return unique[:max_highlights]

    def full_analysis(self, reviews: List[Dict]) -> Dict:
        """Perform complete review analysis."""
        if not reviews:
            return {
                'total_reviews': 0,
                'average_rating': 0,
                'keywords': [],
                'trends': {},
                'response_rate': {},
                'highlights': []
            }

        ratings = [r.get('rating', 0) for r in reviews if r.get('rating')]

        return {
            'total_reviews': len(reviews),
            'average_rating': round(sum(ratings) / len(ratings), 2) if ratings else 0,
            'rating_distribution': {
                '5_star': sum(1 for r in ratings if r == 5),
                '4_star': sum(1 for r in ratings if r == 4),
                '3_star': sum(1 for r in ratings if r == 3),
                '2_star': sum(1 for r in ratings if r == 2),
                '1_star': sum(1 for r in ratings if r == 1),
            },
            'keywords': self.extract_keywords(reviews),
            'trends': self.analyze_trends(reviews),
            'response_rate': self.calculate_response_rate(reviews),
            'highlights': self.extract_highlights(reviews)
        }


# Convenience function
def analyze_reviews(reviews: List[Dict]) -> Dict:
    """Quick function to analyze reviews."""
    analyzer = ReviewAnalyzer()
    return analyzer.full_analysis(reviews)
```

---

## PHASE 2: Scheduled Jobs & Automation

### Feature 2.1: Enable Scheduled/Recurring Jobs in UI

**Purpose:** Expose the existing scheduler functionality through the frontend.

**Files to Modify:**
- `api/routes/features.py` (add scheduler endpoints)
- `api/schemas/requests.py` (add scheduler schemas)
- `frontend/app.js` (add scheduler UI)

**Implementation Steps:**

```python
# Step 1: Add to api/schemas/requests.py

class ScheduledJobRequest(BaseModel):
    """Request schema for creating scheduled jobs."""

    task_id: str = Field(..., min_length=1, max_length=100, description="Unique task ID")
    search_query: str = Field(..., min_length=1, max_length=500)
    location: Optional[str] = Field(None, max_length=200)
    max_results: int = Field(100, ge=1, le=500)

    # Schedule type
    schedule_type: str = Field(
        "daily",
        pattern="^(hourly|daily|weekly|once)$",
        description="Type of schedule"
    )

    # Schedule configuration
    interval_hours: Optional[int] = Field(None, ge=1, le=168, description="For hourly type")
    run_time: Optional[str] = Field(None, description="Time to run (HH:MM format)")
    day_of_week: Optional[str] = Field(None, description="For weekly: mon,tue,wed,thu,fri,sat,sun")
    run_at: Optional[str] = Field(None, description="For once: ISO datetime")

    # Options
    extract_emails: bool = Field(True)
    extract_social: bool = Field(True)
    notify_on_complete: bool = Field(True)
    webhook_url: Optional[str] = Field(None)
```

```python
# Step 2: Add to api/routes/features.py

from scraper.scheduler import get_scheduler, ScheduledTask

@router.post("/scheduled-jobs")
async def create_scheduled_job(request: ScheduledJobRequest):
    """Create a new scheduled scraping job."""
    scheduler = get_scheduler()

    # Create task based on schedule type
    if request.schedule_type == "daily":
        hour, minute = map(int, (request.run_time or "09:00").split(":"))
        success = scheduler.create_daily_task(
            task_id=request.task_id,
            search_query=request.search_query,
            location=request.location,
            max_results=request.max_results,
            hour=hour,
            minute=minute,
            extract_emails=request.extract_emails,
            notify_on_complete=request.notify_on_complete,
            webhook_url=request.webhook_url
        )
    elif request.schedule_type == "weekly":
        hour, minute = map(int, (request.run_time or "09:00").split(":"))
        success = scheduler.create_weekly_task(
            task_id=request.task_id,
            search_query=request.search_query,
            location=request.location,
            max_results=request.max_results,
            day_of_week=request.day_of_week or "mon",
            hour=hour,
            minute=minute,
            extract_emails=request.extract_emails,
            notify_on_complete=request.notify_on_complete,
            webhook_url=request.webhook_url
        )
    elif request.schedule_type == "hourly":
        success = scheduler.create_hourly_task(
            task_id=request.task_id,
            search_query=request.search_query,
            location=request.location,
            max_results=request.max_results,
            interval_hours=request.interval_hours or 1,
            extract_emails=request.extract_emails,
            notify_on_complete=request.notify_on_complete,
            webhook_url=request.webhook_url
        )
    else:
        raise HTTPException(400, "Invalid schedule type")

    if success:
        return {"status": "created", "task_id": request.task_id}
    else:
        raise HTTPException(400, "Failed to create scheduled job")


@router.get("/scheduled-jobs")
async def list_scheduled_jobs():
    """List all scheduled jobs."""
    scheduler = get_scheduler()
    return {
        "jobs": scheduler.list_tasks(),
        "status": scheduler.get_status()
    }


@router.delete("/scheduled-jobs/{task_id}")
async def delete_scheduled_job(task_id: str):
    """Delete a scheduled job."""
    scheduler = get_scheduler()
    if scheduler.remove_task(task_id):
        return {"status": "deleted"}
    raise HTTPException(404, "Task not found")


@router.post("/scheduled-jobs/{task_id}/pause")
async def pause_scheduled_job(task_id: str):
    """Pause a scheduled job."""
    scheduler = get_scheduler()
    if scheduler.pause_task(task_id):
        return {"status": "paused"}
    raise HTTPException(404, "Task not found")


@router.post("/scheduled-jobs/{task_id}/resume")
async def resume_scheduled_job(task_id: str):
    """Resume a paused job."""
    scheduler = get_scheduler()
    if scheduler.resume_task(task_id):
        return {"status": "resumed"}
    raise HTTPException(404, "Task not found")


@router.post("/scheduled-jobs/{task_id}/run-now")
async def run_job_now(task_id: str):
    """Run a scheduled job immediately."""
    scheduler = get_scheduler()
    if scheduler.run_task_now(task_id):
        return {"status": "triggered"}
    raise HTTPException(404, "Task not found")
```

```javascript
// Step 3: Add to frontend/app.js - Scheduler UI Section

// Add new tab for Scheduler
const schedulerTabHtml = `
<div id="scheduler-tab" class="tab-content">
    <div class="scheduler-header">
        <h3>Scheduled Jobs</h3>
        <button class="btn btn-primary" onclick="showCreateScheduleModal()">
            <i class="fas fa-plus"></i> New Schedule
        </button>
    </div>

    <div id="scheduled-jobs-list" class="scheduled-jobs-container">
        <!-- Jobs will be loaded here -->
    </div>
</div>
`;

async function loadScheduledJobs() {
    const response = await fetch('/api/scheduled-jobs');
    const data = await response.json();

    const container = document.getElementById('scheduled-jobs-list');
    container.innerHTML = data.jobs.map(job => `
        <div class="scheduled-job-card ${job.enabled ? '' : 'paused'}">
            <div class="job-info">
                <h4>${job.search_query}</h4>
                <p>Location: ${job.location || 'Any'}</p>
                <p>Schedule: ${job.schedule_type} (${job.interval_hours}h)</p>
                <p>Next run: ${job.next_run || 'Not scheduled'}</p>
                <p>Last run: ${job.last_run || 'Never'}</p>
                <p>Runs: ${job.run_count}</p>
            </div>
            <div class="job-actions">
                ${job.enabled
                    ? `<button onclick="pauseJob('${job.task_id}')" class="btn btn-warning">Pause</button>`
                    : `<button onclick="resumeJob('${job.task_id}')" class="btn btn-success">Resume</button>`
                }
                <button onclick="runJobNow('${job.task_id}')" class="btn btn-primary">Run Now</button>
                <button onclick="deleteJob('${job.task_id}')" class="btn btn-danger">Delete</button>
            </div>
        </div>
    `).join('');
}

async function createScheduledJob(formData) {
    const response = await fetch('/api/scheduled-jobs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(formData)
    });

    if (response.ok) {
        showNotification('Scheduled job created!', 'success');
        loadScheduledJobs();
    } else {
        showNotification('Failed to create job', 'error');
    }
}
```

---

## PHASE 3: Alternative Data Sources

### Feature 3.1: JustDial Scraper (India)

**Purpose:** Add support for scraping JustDial business listings for Indian businesses.

**Files to Create:**
- `scraper/extractors/justdial_extractor.py`

**Files to Modify:**
- `scraper/unified_scraper.py` (add JustDial support)
- `api/schemas/requests.py` (add data_source option)
- `frontend/app.js` (add source selector)

**Implementation Steps:**

```python
# Step 1: Create scraper/extractors/justdial_extractor.py

"""JustDial business listing extractor for Indian businesses."""
from typing import Dict, List, Optional
from playwright.sync_api import Page
from loguru import logger
import re
import time


class JustDialExtractor:
    """
    Extracts business data from JustDial.com
    Specialized for Indian business listings.
    """

    BASE_URL = "https://www.justdial.com"

    SELECTORS = {
        "listing": "li.cntanr",
        "business_name": "span.lng_cont_name",
        "category": "span.category",
        "address": "span.cont_sw_addr",
        "rating": "span.green-box",
        "review_count": "span.rt_count a",
        "phone_container": "a.tel-icon",
        "timing": "span.wtime",
        "website": "a.wdget",
    }

    def __init__(self, page: Page):
        self.page = page

    def search(self, query: str, city: str) -> str:
        """
        Navigate to search results.
        Returns the search URL.
        """
        # Format city name for URL
        city_slug = city.lower().replace(' ', '-')
        query_slug = query.lower().replace(' ', '-')

        url = f"{self.BASE_URL}/{city_slug}/{query_slug}"
        logger.info(f"Searching JustDial: {url}")

        self.page.goto(url, timeout=30000)
        self.page.wait_for_load_state('networkidle')

        return url

    def get_listings(self, max_results: int = 50) -> List[Dict]:
        """
        Extract business listings from current search results.
        """
        listings = []

        try:
            # Wait for listings to load
            self.page.wait_for_selector(self.SELECTORS["listing"], timeout=10000)

            # Get all listing elements
            elements = self.page.query_selector_all(self.SELECTORS["listing"])
            logger.info(f"Found {len(elements)} JustDial listings")

            for i, element in enumerate(elements[:max_results]):
                try:
                    listing = self._extract_listing(element, i)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.warning(f"Error extracting listing {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error getting JustDial listings: {e}")

        return listings

    def _extract_listing(self, element, index: int) -> Optional[Dict]:
        """Extract data from a single listing element."""
        try:
            data = {
                'data_source': 'justdial',
                'country': 'India'
            }

            # Business name
            name_el = element.query_selector(self.SELECTORS["business_name"])
            if name_el:
                data['business_name'] = name_el.text_content().strip()
            else:
                return None  # Skip if no name

            # Category
            cat_el = element.query_selector(self.SELECTORS["category"])
            if cat_el:
                data['category'] = cat_el.text_content().strip()

            # Address
            addr_el = element.query_selector(self.SELECTORS["address"])
            if addr_el:
                full_addr = addr_el.text_content().strip()
                data['full_address'] = full_addr
                # Parse city from address
                parts = full_addr.split(',')
                if len(parts) >= 2:
                    data['city'] = parts[-1].strip()

            # Rating
            rating_el = element.query_selector(self.SELECTORS["rating"])
            if rating_el:
                try:
                    data['rating'] = float(rating_el.text_content().strip())
                except:
                    pass

            # Review count
            review_el = element.query_selector(self.SELECTORS["review_count"])
            if review_el:
                review_text = review_el.text_content().strip()
                match = re.search(r'(\d+)', review_text)
                if match:
                    data['review_count'] = int(match.group(1))

            # Phone (JustDial often obfuscates phone numbers)
            phone = self._extract_phone(element)
            if phone:
                data['phone'] = phone

            # Timing/hours
            timing_el = element.query_selector(self.SELECTORS["timing"])
            if timing_el:
                timing = timing_el.text_content().strip()
                if 'Open' in timing:
                    data['is_open_now'] = True
                elif 'Closed' in timing:
                    data['is_open_now'] = False

            # Website
            website_el = element.query_selector(self.SELECTORS["website"])
            if website_el:
                data['website'] = website_el.get_attribute('href')

            return data

        except Exception as e:
            logger.warning(f"Error extracting JustDial listing: {e}")
            return None

    def _extract_phone(self, element) -> Optional[str]:
        """
        Extract phone number from JustDial listing.
        JustDial uses various obfuscation techniques.
        """
        try:
            # Method 1: Look for direct tel: link
            tel_links = element.query_selector_all('a[href^="tel:"]')
            for link in tel_links:
                href = link.get_attribute('href')
                if href:
                    phone = href.replace('tel:', '').strip()
                    if phone and len(phone) >= 10:
                        return phone

            # Method 2: Look for phone container with decoded number
            phone_container = element.query_selector(self.SELECTORS["phone_container"])
            if phone_container:
                # JustDial stores phone in data attributes or spans
                phone_spans = phone_container.query_selector_all('span')
                phone_parts = []
                for span in phone_spans:
                    text = span.text_content().strip()
                    if text.isdigit():
                        phone_parts.append(text)
                if phone_parts:
                    return ''.join(phone_parts)

            # Method 3: Look for data-phn attribute
            phn_attr = element.get_attribute('data-phn')
            if phn_attr:
                return phn_attr

        except Exception as e:
            logger.debug(f"Could not extract phone: {e}")

        return None

    def scroll_for_more(self, scroll_count: int = 3):
        """Scroll to load more results (lazy loading)."""
        for i in range(scroll_count):
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

            # Check if new content loaded
            current_count = len(self.page.query_selector_all(self.SELECTORS["listing"]))
            logger.debug(f"Scroll {i+1}: {current_count} listings visible")
```

---

### Feature 3.2: Yellow Pages Scraper

**Purpose:** Add support for scraping YellowPages.com for US businesses.

**Files to Create:**
- `scraper/extractors/yellowpages_extractor.py`

**Implementation Steps:**

```python
# Step 1: Create scraper/extractors/yellowpages_extractor.py

"""Yellow Pages business listing extractor for US businesses."""
from typing import Dict, List, Optional
from playwright.sync_api import Page
from loguru import logger
import re


class YellowPagesExtractor:
    """
    Extracts business data from YellowPages.com
    Specialized for US business listings.
    """

    BASE_URL = "https://www.yellowpages.com"

    SELECTORS = {
        "listing": "div.result",
        "business_name": "a.business-name span",
        "category": "div.categories a",
        "address": "div.street-address",
        "locality": "div.locality",
        "phone": "div.phones.phone.primary",
        "rating": "div.ratings div.rating",
        "website": "a.track-visit-website",
        "years_in_business": "div.years-in-business",
    }

    def __init__(self, page: Page):
        self.page = page

    def search(self, query: str, location: str) -> str:
        """Navigate to search results."""
        url = f"{self.BASE_URL}/search"
        params = f"?search_terms={query}&geo_location_terms={location}"

        full_url = url + params
        logger.info(f"Searching Yellow Pages: {full_url}")

        self.page.goto(full_url, timeout=30000)
        self.page.wait_for_load_state('networkidle')

        return full_url

    def get_listings(self, max_results: int = 50) -> List[Dict]:
        """Extract business listings."""
        listings = []

        try:
            self.page.wait_for_selector(self.SELECTORS["listing"], timeout=10000)
            elements = self.page.query_selector_all(self.SELECTORS["listing"])

            for i, element in enumerate(elements[:max_results]):
                try:
                    listing = self._extract_listing(element)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.warning(f"Error extracting listing {i}: {e}")

        except Exception as e:
            logger.error(f"Error getting Yellow Pages listings: {e}")

        return listings

    def _extract_listing(self, element) -> Optional[Dict]:
        """Extract data from listing element."""
        try:
            data = {
                'data_source': 'yellowpages',
                'country': 'USA'
            }

            # Business name
            name_el = element.query_selector(self.SELECTORS["business_name"])
            if name_el:
                data['business_name'] = name_el.text_content().strip()
            else:
                return None

            # Category
            cat_el = element.query_selector(self.SELECTORS["category"])
            if cat_el:
                data['category'] = cat_el.text_content().strip()

            # Address
            street_el = element.query_selector(self.SELECTORS["address"])
            locality_el = element.query_selector(self.SELECTORS["locality"])

            address_parts = []
            if street_el:
                data['street'] = street_el.text_content().strip()
                address_parts.append(data['street'])

            if locality_el:
                locality = locality_el.text_content().strip()
                address_parts.append(locality)
                # Parse city, state, zip
                match = re.match(r'(.+),\s*([A-Z]{2})\s*(\d{5})?', locality)
                if match:
                    data['city'] = match.group(1).strip()
                    data['state'] = match.group(2)
                    if match.group(3):
                        data['pin_code'] = match.group(3)

            data['full_address'] = ', '.join(address_parts)

            # Phone
            phone_el = element.query_selector(self.SELECTORS["phone"])
            if phone_el:
                data['phone'] = phone_el.text_content().strip()

            # Rating
            rating_el = element.query_selector(self.SELECTORS["rating"])
            if rating_el:
                rating_class = rating_el.get_attribute('class') or ''
                # Yellow Pages uses classes like "rating-4" for 4 stars
                match = re.search(r'rating-(\d+)', rating_class)
                if match:
                    data['rating'] = float(match.group(1))

            # Website
            website_el = element.query_selector(self.SELECTORS["website"])
            if website_el:
                data['website'] = website_el.get_attribute('href')

            # Years in business
            years_el = element.query_selector(self.SELECTORS["years_in_business"])
            if years_el:
                years_text = years_el.text_content().strip()
                match = re.search(r'(\d+)', years_text)
                if match:
                    years = int(match.group(1))
                    from datetime import datetime
                    data['founded_year'] = datetime.now().year - years

            return data

        except Exception as e:
            logger.warning(f"Error extracting Yellow Pages listing: {e}")
            return None

    def get_next_page(self) -> bool:
        """Navigate to next page of results."""
        try:
            next_btn = self.page.query_selector('a.next.ajax-page')
            if next_btn:
                next_btn.click()
                self.page.wait_for_load_state('networkidle')
                return True
        except:
            pass
        return False
```

---

## PHASE 4: Website Analysis

### Feature 4.1: Website Analysis (No External APIs)

**Purpose:** Analyze business websites for tech stack, SSL, and basic metrics.

**Files to Create:**
- `utils/website_analyzer.py`

**Files to Modify:**
- `scraper/unified_scraper.py`
- `database/models.py`
- `frontend/app.js`

**Implementation Steps:**

```python
# Step 1: Create utils/website_analyzer.py

"""Website analysis without external APIs."""
import re
import ssl
import socket
from typing import Dict, Optional
from urllib.parse import urlparse
from datetime import datetime
from playwright.sync_api import Page
from loguru import logger


class WebsiteAnalyzer:
    """
    Analyzes websites for:
    - SSL certificate info
    - Technology stack (from HTML/headers)
    - Basic performance metrics
    - Contact page detection
    """

    # Technology detection patterns
    TECH_PATTERNS = {
        # CMS
        'WordPress': [r'wp-content', r'wp-includes', r'/wp-json/'],
        'Shopify': [r'cdn\.shopify\.com', r'shopify\.com'],
        'Wix': [r'wix\.com', r'wixsite\.com', r'_wix_'],
        'Squarespace': [r'squarespace\.com', r'static1\.squarespace'],
        'Webflow': [r'webflow\.com', r'website-files\.com'],
        'Drupal': [r'drupal\.js', r'/sites/default/files'],
        'Joomla': [r'joomla', r'/components/com_'],

        # E-commerce
        'WooCommerce': [r'woocommerce', r'/cart/'],
        'Magento': [r'magento', r'mage/'],
        'BigCommerce': [r'bigcommerce\.com'],
        'PrestaShop': [r'prestashop'],

        # JavaScript frameworks
        'React': [r'react', r'__REACT_DEVTOOLS_GLOBAL_HOOK__'],
        'Vue.js': [r'vue\.js', r'__VUE__'],
        'Angular': [r'angular', r'ng-'],
        'jQuery': [r'jquery'],
        'Bootstrap': [r'bootstrap'],

        # Analytics
        'Google Analytics': [r'google-analytics\.com', r'gtag/'],
        'Facebook Pixel': [r'connect\.facebook\.net', r'fbevents\.js'],
        'Hotjar': [r'hotjar\.com'],

        # Payment
        'Stripe': [r'stripe\.com', r'stripe\.js'],
        'PayPal': [r'paypal\.com'],

        # Chat/Support
        'Intercom': [r'intercom\.io'],
        'Zendesk': [r'zendesk\.com'],
        'LiveChat': [r'livechatinc\.com'],
        'Tawk.to': [r'tawk\.to'],
        'Crisp': [r'crisp\.chat'],
    }

    def __init__(self, page: Optional[Page] = None):
        self.page = page

    def analyze(self, url: str) -> Dict:
        """
        Perform full website analysis.

        Returns dict with ssl_info, technologies, performance, contact_pages
        """
        result = {
            'url': url,
            'analyzed_at': datetime.now().isoformat(),
            'ssl_info': {},
            'technologies': [],
            'performance': {},
            'contact_pages': [],
            'social_links': [],
            'has_contact_form': False,
        }

        # Parse URL
        try:
            parsed = urlparse(url if url.startswith('http') else f'https://{url}')
            domain = parsed.netloc or parsed.path.split('/')[0]
        except:
            return result

        # SSL Analysis
        result['ssl_info'] = self._check_ssl(domain)

        # Page analysis (requires page object)
        if self.page:
            try:
                page_analysis = self._analyze_page(url)
                result.update(page_analysis)
            except Exception as e:
                logger.warning(f"Page analysis error: {e}")

        return result

    def _check_ssl(self, domain: str) -> Dict:
        """Check SSL certificate information."""
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()

                    # Parse certificate dates
                    not_before = datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z')
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')

                    # Get issuer
                    issuer = dict(x[0] for x in cert.get('issuer', []))

                    return {
                        'valid': True,
                        'issuer': issuer.get('organizationName', 'Unknown'),
                        'expires': not_after.isoformat(),
                        'days_until_expiry': (not_after - datetime.now()).days,
                        'subject': dict(x[0] for x in cert.get('subject', [])).get('commonName', domain)
                    }
        except ssl.SSLError as e:
            return {'valid': False, 'error': 'SSL Error', 'details': str(e)}
        except socket.timeout:
            return {'valid': False, 'error': 'Connection timeout'}
        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def _analyze_page(self, url: str) -> Dict:
        """Analyze page content for technologies and features."""
        result = {
            'technologies': [],
            'contact_pages': [],
            'social_links': [],
            'has_contact_form': False,
            'performance': {}
        }

        try:
            # Navigate and measure load time
            start_time = datetime.now()
            self.page.goto(url, timeout=30000, wait_until='networkidle')
            load_time = (datetime.now() - start_time).total_seconds()

            result['performance']['load_time_seconds'] = round(load_time, 2)

            # Get page content
            html = self.page.content()

            # Detect technologies
            for tech, patterns in self.TECH_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, html, re.IGNORECASE):
                        if tech not in result['technologies']:
                            result['technologies'].append(tech)
                        break

            # Find contact pages
            contact_patterns = [
                r'href=["\']([^"\']*contact[^"\']*)["\']',
                r'href=["\']([^"\']*about[^"\']*)["\']',
                r'href=["\']([^"\']*reach-us[^"\']*)["\']',
            ]

            for pattern in contact_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                result['contact_pages'].extend(matches[:3])

            # Detect contact form
            if re.search(r'<form[^>]*contact|<form[^>]*email|type=["\']email["\']', html, re.IGNORECASE):
                result['has_contact_form'] = True

            # Find social links
            social_patterns = {
                'facebook': r'facebook\.com/[^"\'\s>]+',
                'instagram': r'instagram\.com/[^"\'\s>]+',
                'twitter': r'twitter\.com/[^"\'\s>]+',
                'linkedin': r'linkedin\.com/[^"\'\s>]+',
                'youtube': r'youtube\.com/[^"\'\s>]+',
            }

            for platform, pattern in social_patterns.items():
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    result['social_links'].append({
                        'platform': platform,
                        'url': f'https://{matches[0]}'
                    })

            # Get page title
            title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
            if title_match:
                result['page_title'] = title_match.group(1).strip()

            # Check mobile responsiveness (viewport meta tag)
            if re.search(r'<meta[^>]*viewport', html, re.IGNORECASE):
                result['mobile_responsive'] = True
            else:
                result['mobile_responsive'] = False

        except Exception as e:
            logger.error(f"Page analysis error for {url}: {e}")

        return result


# Convenience function
def analyze_website(url: str, page: Optional[Page] = None) -> Dict:
    """Quick function to analyze a website."""
    analyzer = WebsiteAnalyzer(page)
    return analyzer.analyze(url)
```

```python
# Step 2: Modify database/models.py - Add fields

# Add after existing website field:
website_ssl_valid = Column(Boolean, nullable=True)
website_ssl_expiry = Column(DateTime, nullable=True)
website_technologies = Column(JSON, nullable=True)  # List of detected techs
website_load_time = Column(Float, nullable=True)  # Seconds
website_mobile_responsive = Column(Boolean, nullable=True)
website_has_contact_form = Column(Boolean, nullable=True)
```

---

## PHASE 5: Enhanced Export Options

### Feature 5.1: PDF Export with Lead Cards

**Purpose:** Export leads as professional PDF documents.

**Files to Create:**
- `utils/pdf_exporter.py`

**Files to Modify:**
- `api/services/export_service.py`
- `api/schemas/requests.py`
- `frontend/app.js`

**Implementation Steps:**

```python
# Step 1: Create utils/pdf_exporter.py

"""PDF export functionality using reportlab."""
from typing import List, Dict
from datetime import datetime
import io

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class PDFExporter:
    """
    Exports leads to PDF format with professional formatting.
    """

    def __init__(self, page_size=letter):
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required. Install with: pip install reportlab")

        self.page_size = page_size
        self.styles = getSampleStyleSheet()

        # Custom styles
        self.styles.add(ParagraphStyle(
            name='LeadTitle',
            fontSize=14,
            fontName='Helvetica-Bold',
            spaceAfter=6,
            textColor=colors.HexColor('#1a73e8')
        ))

        self.styles.add(ParagraphStyle(
            name='LeadInfo',
            fontSize=10,
            fontName='Helvetica',
            spaceAfter=3
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            fontSize=12,
            fontName='Helvetica-Bold',
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.HexColor('#333333')
        ))

    def export_leads(
        self,
        leads: List[Dict],
        title: str = "Business Leads Report",
        output_path: str = None
    ) -> bytes:
        """
        Export leads to PDF.

        Args:
            leads: List of lead dictionaries
            title: Report title
            output_path: Optional file path to save

        Returns:
            PDF bytes if no output_path, otherwise saves to file
        """
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.page_size,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )

        story = []

        # Title
        story.append(Paragraph(title, self.styles['Title']))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Total Leads: {len(leads)}",
            self.styles['Normal']
        ))
        story.append(Spacer(1, 20))

        # Lead cards
        for i, lead in enumerate(leads, 1):
            story.extend(self._create_lead_card(lead, i))

            # Page break every 3 leads
            if i % 3 == 0 and i < len(leads):
                story.append(PageBreak())
            else:
                story.append(Spacer(1, 20))

        doc.build(story)

        pdf_bytes = buffer.getvalue()
        buffer.close()

        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)

        return pdf_bytes

    def _create_lead_card(self, lead: Dict, index: int) -> list:
        """Create a lead card with all information."""
        elements = []

        # Business name and category
        name = lead.get('business_name', 'Unknown Business')
        category = lead.get('category', '')

        elements.append(Paragraph(
            f"{index}. {name}",
            self.styles['LeadTitle']
        ))

        if category:
            elements.append(Paragraph(f"Category: {category}", self.styles['LeadInfo']))

        # Contact information table
        contact_data = []

        if lead.get('phone'):
            contact_data.append(['Phone:', lead['phone']])
        if lead.get('email'):
            contact_data.append(['Email:', lead['email']])
        if lead.get('website'):
            contact_data.append(['Website:', lead['website'][:50] + '...' if len(lead.get('website', '')) > 50 else lead['website']])

        if contact_data:
            elements.append(Paragraph("Contact Information", self.styles['SectionHeader']))
            contact_table = Table(contact_data, colWidths=[1.2*inch, 4*inch])
            contact_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(contact_table)

        # Address
        if lead.get('full_address'):
            elements.append(Paragraph("Address", self.styles['SectionHeader']))
            elements.append(Paragraph(lead['full_address'], self.styles['LeadInfo']))

        # Ratings and reviews
        if lead.get('rating') or lead.get('review_count'):
            elements.append(Paragraph("Reviews", self.styles['SectionHeader']))
            rating_text = f"Rating: {lead.get('rating', 'N/A')} ⭐ | Reviews: {lead.get('review_count', 0)}"
            elements.append(Paragraph(rating_text, self.styles['LeadInfo']))

        # Social media
        social_links = []
        for platform in ['facebook', 'instagram', 'linkedin', 'twitter']:
            key = f'social_{platform}'
            if lead.get(key):
                social_links.append(platform.capitalize())

        if social_links:
            elements.append(Paragraph("Social Media", self.styles['SectionHeader']))
            elements.append(Paragraph(', '.join(social_links), self.styles['LeadInfo']))

        # Lead score
        if lead.get('lead_score'):
            elements.append(Paragraph(
                f"Lead Score: {lead['lead_score']}",
                self.styles['LeadInfo']
            ))

        # Horizontal line
        line_data = [['─' * 80]]
        line_table = Table(line_data, colWidths=[7*inch])
        line_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#cccccc')),
        ]))
        elements.append(Spacer(1, 10))
        elements.append(line_table)

        return elements

    def export_summary_table(
        self,
        leads: List[Dict],
        columns: List[str] = None,
        title: str = "Leads Summary"
    ) -> bytes:
        """Export leads as a summary table PDF."""
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.3*inch,
            leftMargin=0.3*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )

        # Default columns
        if not columns:
            columns = ['business_name', 'phone', 'email', 'city', 'rating']

        story = []

        # Title
        story.append(Paragraph(title, self.styles['Title']))
        story.append(Spacer(1, 20))

        # Table header
        header = [col.replace('_', ' ').title() for col in columns]
        table_data = [header]

        # Table rows
        for lead in leads:
            row = []
            for col in columns:
                value = lead.get(col, '')
                if value is None:
                    value = ''
                # Truncate long values
                if isinstance(value, str) and len(value) > 30:
                    value = value[:27] + '...'
                row.append(str(value))
            table_data.append(row)

        # Create table
        col_width = (doc.width - 0.5*inch) / len(columns)
        table = Table(table_data, colWidths=[col_width] * len(columns))

        table.setStyle(TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),

            # Body style
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            ('TOPPADDING', (0, 1), (-1, -1), 5),

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        story.append(table)

        doc.build(story)

        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes


# Convenience function
def export_leads_to_pdf(leads: List[Dict], output_path: str = None) -> bytes:
    """Quick function to export leads to PDF."""
    exporter = PDFExporter()
    return exporter.export_leads(leads, output_path=output_path)
```

---

## PHASE 6: Lead Scoring Improvements

### Feature 6.1: Enhanced Lead Scoring

**Purpose:** Improve lead scoring with more factors and customization.

**Files to Modify:**
- `utils/lead_scoring.py`
- `api/schemas/requests.py` (add scoring preferences)
- `frontend/app.js` (add scoring config UI)

**Implementation Steps:**

```python
# Step 1: Enhance utils/lead_scoring.py

"""Enhanced lead scoring with customizable weights."""
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class ScoringWeights:
    """Customizable weights for lead scoring."""
    # Contact completeness (0-1)
    has_email: float = 15.0
    has_phone: float = 15.0
    has_website: float = 10.0
    has_multiple_contacts: float = 5.0

    # Social presence (0-1)
    has_social_media: float = 8.0
    has_multiple_social: float = 5.0

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


class EnhancedLeadScorer:
    """
    Enhanced lead scoring with customizable weights and detailed breakdown.
    """

    def __init__(self, weights: Optional[ScoringWeights] = None):
        self.weights = weights or ScoringWeights()

    def score_lead(self, lead: Dict) -> Dict:
        """
        Score a lead and return detailed breakdown.

        Returns:
            Dict with 'score', 'grade', 'breakdown', 'recommendations'
        """
        breakdown = {}
        total_score = 0.0
        max_possible = 0.0
        recommendations = []

        # Contact completeness
        max_possible += self.weights.has_email + self.weights.has_phone + self.weights.has_website

        if lead.get('email'):
            breakdown['email'] = self.weights.has_email
            total_score += self.weights.has_email
        else:
            breakdown['email'] = 0
            recommendations.append("Add email address")

        if lead.get('phone'):
            breakdown['phone'] = self.weights.has_phone
            total_score += self.weights.has_phone
        else:
            breakdown['phone'] = 0
            recommendations.append("Add phone number")

        if lead.get('website'):
            breakdown['website'] = self.weights.has_website
            total_score += self.weights.has_website
        else:
            breakdown['website'] = 0
            recommendations.append("Add website")

        # Multiple contacts
        max_possible += self.weights.has_multiple_contacts
        contact_count = sum(1 for k in ['email_1', 'email_2', 'phone_1', 'phone_2'] if lead.get(k))
        if contact_count >= 2:
            breakdown['multiple_contacts'] = self.weights.has_multiple_contacts
            total_score += self.weights.has_multiple_contacts

        # Social media
        max_possible += self.weights.has_social_media + self.weights.has_multiple_social
        social_platforms = ['social_facebook', 'social_instagram', 'social_linkedin', 'social_twitter']
        social_count = sum(1 for p in social_platforms if lead.get(p))

        if social_count > 0:
            breakdown['social_media'] = self.weights.has_social_media
            total_score += self.weights.has_social_media
        else:
            recommendations.append("Find social media profiles")

        if social_count >= 3:
            breakdown['multiple_social'] = self.weights.has_multiple_social
            total_score += self.weights.has_multiple_social

        # Rating quality
        max_possible += self.weights.high_rating + self.weights.many_reviews

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

        # Business maturity
        max_possible += self.weights.established_business + self.weights.has_employees_info + self.weights.has_revenue_info

        founded_year = lead.get('founded_year')
        if founded_year:
            from datetime import datetime
            years = datetime.now().year - founded_year
            if years >= 5:
                breakdown['established'] = self.weights.established_business
                total_score += self.weights.established_business
            elif years >= 2:
                breakdown['established'] = self.weights.established_business * 0.5
                total_score += self.weights.established_business * 0.5

        if lead.get('employees'):
            breakdown['employees_info'] = self.weights.has_employees_info
            total_score += self.weights.has_employees_info

        if lead.get('revenue'):
            breakdown['revenue_info'] = self.weights.has_revenue_info
            total_score += self.weights.has_revenue_info

        # Engagement
        max_possible += self.weights.has_photos + self.weights.has_description

        if lead.get('photos') or lead.get('photo_count', 0) > 0:
            breakdown['photos'] = self.weights.has_photos
            total_score += self.weights.has_photos

        if lead.get('description'):
            breakdown['description'] = self.weights.has_description
            total_score += self.weights.has_description

        # Calculate final score (0-100)
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

        return {
            'score': final_score,
            'grade': grade,
            'breakdown': breakdown,
            'max_possible': int(max_possible),
            'earned': round(total_score, 1),
            'recommendations': recommendations[:3],  # Top 3 recommendations
            'quality_tier': 'premium' if final_score >= 80 else 'standard' if final_score >= 50 else 'basic'
        }


# Convenience function
def score_lead(lead: Dict, weights: Optional[ScoringWeights] = None) -> Dict:
    """Quick function to score a lead."""
    scorer = EnhancedLeadScorer(weights)
    return scorer.score_lead(lead)
```

---

## PHASE 7: Search Enhancements

### Feature 7.1: Saved Searches

**Purpose:** Allow users to save and reuse search configurations.

**Files to Modify:**
- `database/models.py` (add SavedSearch model)
- `api/routes/scraping.py` (add saved search endpoints)
- `frontend/app.js` (add saved search UI)

**Implementation Steps:**

```python
# Step 1: Add to database/models.py

class SavedSearch(Base):
    """Model for saved search configurations."""

    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Search identity
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Search parameters
    search_query = Column(String(500), nullable=False)
    location = Column(String(200), nullable=True)
    max_results = Column(Integer, default=100)

    # Extraction options (stored as JSON for flexibility)
    options = Column(JSON, nullable=True)

    # Filters (stored as JSON)
    filters = Column(JSON, nullable=True)

    # Usage tracking
    use_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SavedSearch(id={self.id}, name='{self.name}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'search_query': self.search_query,
            'location': self.location,
            'max_results': self.max_results,
            'options': self.options,
            'filters': self.filters,
            'use_count': self.use_count,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
```

```python
# Step 2: Add to api/routes/scraping.py

@router.post("/saved-searches")
async def create_saved_search(
    name: str,
    search_query: str,
    location: Optional[str] = None,
    max_results: int = 100,
    options: Optional[dict] = None,
    filters: Optional[dict] = None,
    description: Optional[str] = None
):
    """Save a search configuration for reuse."""
    from database import db_manager, SavedSearch

    with db_manager.session() as session:
        saved = SavedSearch(
            name=name,
            description=description,
            search_query=search_query,
            location=location,
            max_results=max_results,
            options=options,
            filters=filters
        )
        session.add(saved)
        session.commit()

        return {"status": "saved", "id": saved.id, "search": saved.to_dict()}


@router.get("/saved-searches")
async def list_saved_searches():
    """List all saved searches."""
    from database import db_manager, SavedSearch

    with db_manager.session() as session:
        searches = session.query(SavedSearch).order_by(
            SavedSearch.last_used_at.desc().nullslast(),
            SavedSearch.created_at.desc()
        ).all()

        return {"searches": [s.to_dict() for s in searches]}


@router.post("/saved-searches/{search_id}/run")
async def run_saved_search(search_id: int, background_tasks: BackgroundTasks):
    """Run a saved search."""
    from database import db_manager, SavedSearch

    with db_manager.session() as session:
        saved = session.query(SavedSearch).filter(SavedSearch.id == search_id).first()

        if not saved:
            raise HTTPException(404, "Saved search not found")

        # Update usage
        saved.use_count += 1
        saved.last_used_at = datetime.now()
        session.commit()

        # Create scrape request from saved search
        request_data = {
            'search_query': saved.search_query,
            'location': saved.location,
            'max_results': saved.max_results,
            **(saved.options or {})
        }

        # Start scraping (reuse existing scrape logic)
        # ... start job using request_data ...

        return {"status": "started", "saved_search": saved.to_dict()}


@router.delete("/saved-searches/{search_id}")
async def delete_saved_search(search_id: int):
    """Delete a saved search."""
    from database import db_manager, SavedSearch

    with db_manager.session() as session:
        saved = session.query(SavedSearch).filter(SavedSearch.id == search_id).first()

        if not saved:
            raise HTTPException(404, "Saved search not found")

        session.delete(saved)
        session.commit()

        return {"status": "deleted"}
```

---

## Summary: Implementation Priority Order

### High Priority (Core Value)
1. **Email Pattern Guessing** (Feature 1.1) - Increases email data coverage
2. **WhatsApp Number Detection** (Feature 1.2) - Adds communication channel
3. **Advanced Duplicate Detection** (Feature 1.4) - Improves data quality

### Medium Priority (User Experience)
4. **Business Hours Analysis** (Feature 1.3) - Adds contact timing insights
5. **Review Analysis Enhancement** (Feature 1.5) - Better review insights
6. **Scheduled Jobs UI** (Feature 2.1) - Enables automation

### Lower Priority (Extended Features)
7. **JustDial Scraper** (Feature 3.1) - India market expansion
8. **Yellow Pages Scraper** (Feature 3.2) - US market alternative
9. **Website Analysis** (Feature 4.1) - Additional business insights

### Optional (Polish Features)
10. **PDF Export** (Feature 5.1) - Professional reports
11. **Enhanced Lead Scoring** (Feature 6.1) - Better prioritization
12. **Saved Searches** (Feature 7.1) - User convenience

---

## Testing Checklist

For each feature, verify:
- [ ] New code doesn't break existing functionality
- [ ] Database migrations work (if applicable)
- [ ] API endpoints return correct responses
- [ ] Frontend displays new data correctly
- [ ] Error handling is in place
- [ ] Logging is added for debugging
- [ ] Performance is acceptable

---

## Notes for Implementation

1. **Database Migrations**: After adding new fields to models.py, delete the old database or run migrations:
   ```bash
   rm -f data/*.db
   python run_server.py  # Recreates tables
   ```

2. **Import Order**: Add imports at the top of files, grouped logically:
   ```python
   # Standard library
   import re
   from typing import Dict

   # Third-party
   from loguru import logger

   # Local
   from utils.email_guesser import guess_business_emails
   ```

3. **Backward Compatibility**: All new fields should be nullable or have defaults.

4. **Feature Flags**: Consider adding feature toggles in config for gradual rollout.

5. **Testing Each Feature**: After implementing each feature, test with:
   - A simple scrape job
   - Check the database has new fields
   - Check the API returns new data
   - Check the frontend displays it

