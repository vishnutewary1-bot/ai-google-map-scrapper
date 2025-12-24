"""Advanced deduplication using fuzzy matching and proximity."""
from typing import List, Dict, Tuple, Optional
from rapidfuzz import fuzz
from loguru import logger
import re
from database import db_manager, BusinessLead


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
