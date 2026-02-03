"""Advanced deduplication using fuzzy matching and proximity.

This module provides advanced duplicate detection with:
- Fuzzy name matching
- Phone number normalization
- Geographic proximity checks
- Address similarity
- Multi-criteria scoring
"""

from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher
from loguru import logger
import re

# Try to import rapidfuzz, fall back to difflib
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    fuzz = None

# Database imports (optional)
try:
    from database import db_manager, BusinessLead
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False
    db_manager = None
    BusinessLead = None


class AdvancedDeduplicator:
    """Advanced deduplication with fuzzy matching and geographic proximity."""

    def __init__(
        self,
        name_similarity_threshold: float = 85.0,
        address_similarity_threshold: float = 80.0,
        proximity_threshold_meters: float = 50.0
    ):
        self.name_threshold = name_similarity_threshold
        self.address_threshold = address_similarity_threshold
        self.proximity_threshold = proximity_threshold_meters

    def normalize_phone(self, phone: Optional[str]) -> Optional[str]:
        """Normalize phone number format."""
        if not phone:
            return None

        # Remove all non-digit characters except +
        normalized = re.sub(r'[^\d+]', '', phone)

        # Remove leading zeros
        normalized = normalized.lstrip('0')

        # Add country code if missing (assuming India)
        if not normalized.startswith('+'):
            if len(normalized) == 10:
                normalized = '+91' + normalized
            elif len(normalized) == 11 and normalized.startswith('91'):
                normalized = '+' + normalized

        return normalized

    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two business names."""
        if not name1 or not name2:
            return 0.0

        # Normalize names
        norm1 = name1.lower().strip()
        norm2 = name2.lower().strip()

        # Use token set ratio for better matching
        # This handles word order differences
        similarity = fuzz.token_set_ratio(norm1, norm2)

        return similarity

    def calculate_address_similarity(self, addr1: Optional[str], addr2: Optional[str]) -> float:
        """Calculate similarity between two addresses."""
        if not addr1 or not addr2:
            return 0.0

        norm1 = addr1.lower().strip()
        norm2 = addr2.lower().strip()

        similarity = fuzz.token_set_ratio(norm1, norm2)

        return similarity

    def calculate_distance(
        self,
        lat1: Optional[float],
        lon1: Optional[float],
        lat2: Optional[float],
        lon2: Optional[float]
    ) -> Optional[float]:
        """Calculate distance between two coordinates in meters (Haversine formula)."""
        if None in (lat1, lon1, lat2, lon2):
            return None

        from math import radians, sin, cos, sqrt, atan2

        # Earth radius in meters
        R = 6371000

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        distance = R * c
        return distance

    def find_duplicates(self, lead: BusinessLead) -> List[Tuple[BusinessLead, Dict]]:
        """
        Find potential duplicates for a given lead.

        Returns list of (duplicate_lead, match_info) tuples.
        """
        duplicates = []

        try:
            with db_manager.get_session() as session:
                # Level 1: Exact Place ID match
                if lead.place_id:
                    exact_match = session.query(BusinessLead).filter(
                        BusinessLead.place_id == lead.place_id,
                        BusinessLead.id != lead.id
                    ).first()

                    if exact_match:
                        duplicates.append((exact_match, {
                            'match_type': 'exact_place_id',
                            'confidence': 100.0
                        }))
                        return duplicates

                # Level 2: Phone number match
                if lead.phone:
                    normalized_phone = self.normalize_phone(lead.phone)
                    if normalized_phone:
                        phone_matches = session.query(BusinessLead).filter(
                            BusinessLead.phone.isnot(None),
                            BusinessLead.id != lead.id
                        ).all()

                        for match in phone_matches:
                            if self.normalize_phone(match.phone) == normalized_phone:
                                duplicates.append((match, {
                                    'match_type': 'phone_number',
                                    'confidence': 95.0
                                }))

                # Level 3: Fuzzy name + address match
                # Get candidates in same city/pin code
                candidates = session.query(BusinessLead).filter(
                    BusinessLead.id != lead.id
                )

                if lead.city:
                    candidates = candidates.filter(BusinessLead.city == lead.city)
                elif lead.pin_code:
                    candidates = candidates.filter(BusinessLead.pin_code == lead.pin_code)
                else:
                    # Too broad, skip fuzzy matching
                    return duplicates

                candidates = candidates.all()

                for candidate in candidates:
                    # Calculate name similarity
                    name_sim = self.calculate_name_similarity(
                        lead.business_name,
                        candidate.business_name
                    )

                    # Calculate address similarity
                    addr_sim = self.calculate_address_similarity(
                        lead.full_address,
                        candidate.full_address
                    )

                    # Calculate geographic distance
                    distance = self.calculate_distance(
                        lead.latitude, lead.longitude,
                        candidate.latitude, candidate.longitude
                    )

                    # Determine if duplicate
                    is_duplicate = False
                    confidence = 0.0
                    match_type = ''

                    # High name similarity + same city
                    if name_sim >= self.name_threshold:
                        is_duplicate = True
                        confidence = name_sim
                        match_type = 'fuzzy_name'

                        # Boost confidence if address also matches
                        if addr_sim >= self.address_threshold:
                            confidence = (name_sim + addr_sim) / 2
                            match_type = 'fuzzy_name_address'

                        # Boost confidence if very close geographically
                        if distance and distance <= self.proximity_threshold:
                            confidence = min(confidence + 10, 100)
                            match_type += '_proximity'

                    # Close proximity + similar name (even if below threshold)
                    elif distance and distance <= self.proximity_threshold:
                        if name_sim >= 70:  # Lower threshold for proximity
                            is_duplicate = True
                            confidence = 85.0
                            match_type = 'proximity_similar_name'

                    if is_duplicate:
                        duplicates.append((candidate, {
                            'match_type': match_type,
                            'confidence': confidence,
                            'name_similarity': name_sim,
                            'address_similarity': addr_sim,
                            'distance_meters': distance
                        }))

        except Exception as e:
            logger.error(f"Error finding duplicates: {e}")

        return duplicates

    def deduplicate_database(self, strategy: str = 'mark', dry_run: bool = False) -> Dict:
        """
        Run deduplication on entire database.

        Strategies:
        - 'mark': Mark duplicates with a flag (keep both)
        - 'merge': Merge duplicate data into single record
        - 'delete': Delete the duplicate with lower quality

        Returns statistics about deduplication.
        """
        stats = {
            'total_processed': 0,
            'duplicates_found': 0,
            'actions_taken': 0,
            'errors': 0
        }

        try:
            with db_manager.get_session() as session:
                all_leads = session.query(BusinessLead).all()
                stats['total_processed'] = len(all_leads)

                logger.info(f"Running deduplication on {len(all_leads)} leads...")

                for i, lead in enumerate(all_leads):
                    if i % 100 == 0:
                        logger.info(f"Processed {i}/{len(all_leads)} leads...")

                    duplicates = self.find_duplicates(lead)

                    if duplicates:
                        stats['duplicates_found'] += len(duplicates)
                        logger.info(f"Found {len(duplicates)} duplicates for: {lead.business_name}")

                        for dup_lead, match_info in duplicates:
                            logger.info(f"  - {dup_lead.business_name} (confidence: {match_info['confidence']:.1f}%)")

                            if not dry_run:
                                if strategy == 'delete':
                                    # Delete the one with lower quality score
                                    if lead.data_quality_score >= dup_lead.data_quality_score:
                                        session.delete(dup_lead)
                                        stats['actions_taken'] += 1
                                elif strategy == 'merge':
                                    # Merge data (keep the one with higher quality, fill missing fields)
                                    self._merge_leads(lead, dup_lead, session)
                                    stats['actions_taken'] += 1

                if not dry_run:
                    session.commit()

        except Exception as e:
            logger.error(f"Error during deduplication: {e}")
            stats['errors'] += 1

        logger.success(f"Deduplication complete: {stats}")
        return stats

    def _merge_leads(self, primary: BusinessLead, duplicate: BusinessLead, session):
        """Merge duplicate lead data into primary lead."""
        # Fill missing fields from duplicate
        fields_to_merge = [
            'phone', 'website', 'email', 'category',
            'social_facebook', 'social_instagram', 'social_twitter',
            'social_linkedin', 'social_youtube'
        ]

        for field in fields_to_merge:
            primary_value = getattr(primary, field)
            duplicate_value = getattr(duplicate, field)

            # If primary is missing but duplicate has value, copy it
            if not primary_value and duplicate_value:
                setattr(primary, field, duplicate_value)

        # Recalculate quality score
        primary.calculate_quality_score()

        # Delete duplicate
        session.delete(duplicate)

        logger.info(f"Merged {duplicate.business_name} into {primary.business_name}")

    # ==================== NEW METHODS (Feature 1.4) ====================

    def normalize_name(self, name: str) -> str:
        """Normalize business name for comparison."""
        if not name:
            return ''

        # Lowercase
        name = name.lower().strip()

        # Remove punctuation
        name = re.sub(r'[^\w\s]', '', name)

        # Remove extra spaces
        name = re.sub(r'\s+', ' ', name)

        # Remove common suffixes
        suffixes = [
            'llc', 'inc', 'ltd', 'corp', 'co', 'pvt', 'private', 'limited',
            'company', 'enterprises', 'services', 'group', 'solutions',
            'international', 'intl', 'associates', 'partners'
        ]
        words = name.split()
        words = [w for w in words if w not in suffixes]

        return ' '.join(words)

    def calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using best available method."""
        if not str1 or not str2:
            return 0.0

        str1 = str1.lower().strip()
        str2 = str2.lower().strip()

        if HAS_RAPIDFUZZ:
            return fuzz.token_set_ratio(str1, str2) / 100.0
        else:
            # Fall back to difflib SequenceMatcher
            return SequenceMatcher(None, str1, str2).ratio()

    def find_duplicates_in_list(
        self,
        leads: List[Dict],
        similarity_threshold: float = 0.85
    ) -> List[Dict]:
        """
        Find potential duplicate leads in a list of lead dictionaries.

        Args:
            leads: List of lead dictionaries
            similarity_threshold: Minimum similarity to consider a match (0-1)

        Returns:
            List of duplicate groups with similarity scores.
        """
        duplicates = []
        checked = set()

        for i, lead1 in enumerate(leads):
            if i in checked:
                continue

            group = {
                'primary': lead1,
                'primary_index': i,
                'duplicates': [],
                'match_reasons': []
            }

            for j, lead2 in enumerate(leads[i+1:], i+1):
                if j in checked:
                    continue

                match_score, reasons = self._compare_lead_dicts(lead1, lead2)

                if match_score >= similarity_threshold:
                    checked.add(j)
                    group['duplicates'].append({
                        'lead': lead2,
                        'index': j,
                        'score': round(match_score, 3),
                        'reasons': reasons
                    })

            if group['duplicates']:
                checked.add(i)
                duplicates.append(group)

        return duplicates

    def _compare_lead_dicts(self, lead1: Dict, lead2: Dict) -> Tuple[float, List[str]]:
        """Compare two lead dictionaries and return match score with reasons."""
        scores = []
        reasons = []

        # Exact place_id match (definitive)
        if lead1.get('place_id') and lead1.get('place_id') == lead2.get('place_id'):
            return 1.0, ['Same Google Place ID']

        # Phone number match (strong indicator)
        phone1 = self.normalize_phone(lead1.get('phone', ''))
        phone2 = self.normalize_phone(lead2.get('phone', ''))
        if phone1 and phone2 and phone1 == phone2:
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
        addr1 = (lead1.get('full_address') or lead1.get('address') or '').lower()
        addr2 = (lead2.get('full_address') or lead2.get('address') or '').lower()
        if addr1 and addr2:
            addr_sim = self.calculate_similarity(addr1, addr2)
            if addr_sim >= 0.7:
                scores.append(addr_sim * 0.6)
                reasons.append(f'Similar address ({int(addr_sim*100)}%)')

        # Website match
        website1 = (lead1.get('website') or '').lower().rstrip('/')
        website2 = (lead2.get('website') or '').lower().rstrip('/')
        if website1 and website2 and website1 == website2:
            scores.append(0.9)
            reasons.append('Same website')

        # Email match
        email1 = (lead1.get('email') or '').lower()
        email2 = (lead2.get('email') or '').lower()
        if email1 and email2 and email1 == email2:
            scores.append(0.85)
            reasons.append('Same email')

        # Geographic proximity
        if all(lead1.get(k) and lead2.get(k) for k in ['latitude', 'longitude']):
            distance = self.calculate_distance(
                lead1['latitude'], lead1['longitude'],
                lead2['latitude'], lead2['longitude']
            )
            if distance is not None and distance <= 50:  # Within 50 meters
                scores.append(0.7)
                reasons.append(f'Very close location ({int(distance)}m)')

        # Calculate weighted average
        if scores:
            final_score = sum(scores) / len(scores)
            return final_score, reasons

        return 0.0, []

    def merge_lead_dicts(self, primary: Dict, secondary: Dict) -> Dict:
        """
        Merge two lead dictionaries, preferring non-null values from primary.

        Args:
            primary: Primary lead dict (values preferred)
            secondary: Secondary lead dict (fill missing values)

        Returns:
            Merged lead dictionary
        """
        merged = primary.copy()

        for key, value in secondary.items():
            if not merged.get(key) and value:
                merged[key] = value

        # Combine array fields
        array_fields = [
            'photos', 'reviews', 'subcategories', 'guessed_emails',
            'review_highlights', 'review_keywords'
        ]
        for field in array_fields:
            primary_val = primary.get(field) or []
            secondary_val = secondary.get(field) or []
            if primary_val and secondary_val:
                if isinstance(primary_val, list) and isinstance(secondary_val, list):
                    # Combine and deduplicate
                    combined = primary_val.copy()
                    for item in secondary_val:
                        if item not in combined:
                            combined.append(item)
                    merged[field] = combined

        # Take higher quality score
        primary_quality = primary.get('data_quality_score') or primary.get('quality_score') or 0
        secondary_quality = secondary.get('data_quality_score') or secondary.get('quality_score') or 0
        merged['data_quality_score'] = max(primary_quality, secondary_quality)

        return merged

    def deduplicate_lead_list(
        self,
        leads: List[Dict],
        strategy: str = 'merge',
        similarity_threshold: float = 0.85
    ) -> Tuple[List[Dict], Dict]:
        """
        Deduplicate a list of leads.

        Args:
            leads: List of lead dictionaries
            strategy: 'merge' (combine data), 'keep_first', or 'keep_best'
            similarity_threshold: Minimum similarity to consider a match (0-1)

        Returns:
            Tuple of (deduplicated_leads, stats)
        """
        stats = {
            'total_input': len(leads),
            'duplicates_found': 0,
            'total_output': 0,
            'merged': 0
        }

        if not leads:
            return [], stats

        duplicate_groups = self.find_duplicates_in_list(leads, similarity_threshold)

        # Track which leads are duplicates
        duplicate_indices = set()
        for group in duplicate_groups:
            stats['duplicates_found'] += len(group['duplicates'])
            for dup in group['duplicates']:
                duplicate_indices.add(dup['index'])

        # Build output list
        deduplicated = []
        for i, lead in enumerate(leads):
            if i in duplicate_indices:
                continue

            # Check if this lead is a primary in any group
            for group in duplicate_groups:
                if group['primary_index'] == i:
                    if strategy == 'merge':
                        # Merge all duplicates into primary
                        merged = lead.copy()
                        for dup in group['duplicates']:
                            merged = self.merge_lead_dicts(merged, dup['lead'])
                            stats['merged'] += 1
                        lead = merged
                    elif strategy == 'keep_best':
                        # Keep the one with highest quality
                        best = lead
                        best_score = lead.get('data_quality_score') or lead.get('quality_score') or 0
                        for dup in group['duplicates']:
                            dup_score = dup['lead'].get('data_quality_score') or dup['lead'].get('quality_score') or 0
                            if dup_score > best_score:
                                best = dup['lead']
                                best_score = dup_score
                        lead = best
                    # 'keep_first' - just use original lead
                    break

            deduplicated.append(lead)

        stats['total_output'] = len(deduplicated)

        logger.info(f"Deduplication: {stats['total_input']} -> {stats['total_output']} "
                    f"({stats['duplicates_found']} duplicates found)")

        return deduplicated, stats


# Convenience functions
def find_duplicates(leads: List[Dict], threshold: float = 0.85) -> List[Dict]:
    """Find duplicate leads in a list."""
    deduplicator = AdvancedDeduplicator()
    return deduplicator.find_duplicates_in_list(leads, threshold)


def deduplicate_leads(
    leads: List[Dict],
    strategy: str = 'merge',
    threshold: float = 0.85
) -> Tuple[List[Dict], Dict]:
    """Deduplicate a list of leads."""
    deduplicator = AdvancedDeduplicator()
    return deduplicator.deduplicate_lead_list(leads, strategy, threshold)
