"""Lead service - business logic for lead management."""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.schemas.requests import LeadFilters, LeadUpdateRequest
from api.schemas.responses import LeadResponse, LeadListResponse

# Database imports
try:
    from database import db_manager
    from database.models import BusinessLead
    from sqlalchemy import func, or_, and_
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False
    db_manager = None
    BusinessLead = None


class LeadService:
    """Service for managing leads."""

    def get_leads(
        self,
        filters: Optional[LeadFilters] = None,
        limit: int = 100,
        offset: int = 0,
        include_aggregations: bool = False
    ) -> LeadListResponse:
        """
        Get leads with optional filters and pagination.

        Args:
            filters: Filter criteria
            limit: Maximum results to return
            offset: Results offset
            include_aggregations: Include city/state/category lists

        Returns:
            LeadListResponse with leads and metadata
        """
        if not HAS_DATABASE or db_manager.SessionLocal is None:
            return LeadListResponse(leads=[], total=0, limit=limit, offset=offset)

        with db_manager.get_session() as session:
            query = session.query(BusinessLead)

            # Apply filters
            if filters:
                query = self._apply_filters(query, filters)

            # Get total count
            total = query.count()

            # Get paginated results
            leads = (
                query
                .order_by(BusinessLead.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            # Build response
            response = LeadListResponse(
                leads=[self._lead_to_response(lead) for lead in leads],
                total=total,
                limit=limit,
                offset=offset,
            )

            # Add aggregations if requested
            if include_aggregations:
                response.cities = self._get_distinct_values(session, BusinessLead.city)
                response.states = self._get_distinct_values(session, BusinessLead.state)
                response.categories = self._get_distinct_values(session, BusinessLead.category)

            return response

    def get_lead(self, lead_id: int) -> Optional[LeadResponse]:
        """Get a single lead by ID."""
        if not HAS_DATABASE or db_manager.SessionLocal is None:
            return None

        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter(BusinessLead.id == lead_id).first()
            if not lead:
                return None
            return self._lead_to_response(lead)

    def update_lead(self, lead_id: int, request: LeadUpdateRequest) -> Optional[LeadResponse]:
        """Update a lead."""
        if not HAS_DATABASE or db_manager.SessionLocal is None:
            return None

        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter(BusinessLead.id == lead_id).first()
            if not lead:
                return None

            # Update fields
            update_data = request.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(lead, field):
                    setattr(lead, field, value)

            lead.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(lead)

            return self._lead_to_response(lead)

    def delete_lead(self, lead_id: int) -> bool:
        """Delete a lead."""
        if not HAS_DATABASE or db_manager.SessionLocal is None:
            return False

        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter(BusinessLead.id == lead_id).first()
            if not lead:
                return False

            session.delete(lead)
            session.commit()
            return True

    def bulk_delete(self, lead_ids: List[int]) -> int:
        """Delete multiple leads."""
        if not HAS_DATABASE:
            return 0

        with db_manager.get_session() as session:
            deleted = (
                session.query(BusinessLead)
                .filter(BusinessLead.id.in_(lead_ids))
                .delete(synchronize_session=False)
            )
            session.commit()
            return deleted

    def bulk_update(self, lead_ids: List[int], updates: Dict[str, Any]) -> int:
        """Update multiple leads."""
        if not HAS_DATABASE:
            return 0

        with db_manager.get_session() as session:
            updates["updated_at"] = datetime.utcnow()
            updated = (
                session.query(BusinessLead)
                .filter(BusinessLead.id.in_(lead_ids))
                .update(updates, synchronize_session=False)
            )
            session.commit()
            return updated

    def get_stats(self) -> Dict[str, Any]:
        """Get lead statistics."""
        if not HAS_DATABASE or db_manager.SessionLocal is None:
            return {}

        with db_manager.get_session() as session:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=now.weekday())
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Total counts
            total_leads = session.query(BusinessLead).count()

            # Contact info stats
            leads_with_email = session.query(BusinessLead).filter(
                BusinessLead.email.isnot(None),
                BusinessLead.email != ''
            ).count()

            leads_with_phone = session.query(BusinessLead).filter(
                BusinessLead.phone.isnot(None),
                BusinessLead.phone != ''
            ).count()

            leads_with_website = session.query(BusinessLead).filter(
                BusinessLead.website.isnot(None),
                BusinessLead.website != ''
            ).count()

            # Social media stats
            leads_with_social = session.query(BusinessLead).filter(
                or_(
                    BusinessLead.social_facebook.isnot(None),
                    BusinessLead.social_instagram.isnot(None),
                    BusinessLead.social_linkedin.isnot(None),
                    BusinessLead.social_twitter.isnot(None),
                )
            ).count()

            # Quality score stats
            avg_quality = session.query(func.avg(BusinessLead.data_quality_score)).scalar() or 0
            high_quality = session.query(BusinessLead).filter(
                BusinessLead.data_quality_score >= 70
            ).count()
            medium_quality = session.query(BusinessLead).filter(
                and_(BusinessLead.data_quality_score >= 40, BusinessLead.data_quality_score < 70)
            ).count()
            low_quality = session.query(BusinessLead).filter(
                BusinessLead.data_quality_score < 40
            ).count()

            # Time-based stats
            leads_today = session.query(BusinessLead).filter(
                BusinessLead.created_at >= today_start
            ).count()
            leads_this_week = session.query(BusinessLead).filter(
                BusinessLead.created_at >= week_start
            ).count()
            leads_this_month = session.query(BusinessLead).filter(
                BusinessLead.created_at >= month_start
            ).count()

            # Top categories
            top_categories = (
                session.query(
                    BusinessLead.category,
                    func.count(BusinessLead.id).label('count')
                )
                .filter(BusinessLead.category.isnot(None))
                .group_by(BusinessLead.category)
                .order_by(func.count(BusinessLead.id).desc())
                .limit(10)
                .all()
            )

            # Top cities
            top_cities = (
                session.query(
                    BusinessLead.city,
                    func.count(BusinessLead.id).label('count')
                )
                .filter(BusinessLead.city.isnot(None))
                .group_by(BusinessLead.city)
                .order_by(func.count(BusinessLead.id).desc())
                .limit(10)
                .all()
            )

            return {
                "total_leads": total_leads,
                "leads_with_email": leads_with_email,
                "leads_with_phone": leads_with_phone,
                "leads_with_website": leads_with_website,
                "leads_with_social": leads_with_social,
                "avg_quality_score": round(avg_quality, 1),
                "high_quality_leads": high_quality,
                "medium_quality_leads": medium_quality,
                "low_quality_leads": low_quality,
                "leads_today": leads_today,
                "leads_this_week": leads_this_week,
                "leads_this_month": leads_this_month,
                "top_categories": [{"category": c, "count": n} for c, n in top_categories],
                "top_cities": [{"city": c, "count": n} for c, n in top_cities],
            }

    def search(self, query: str, limit: int = 50) -> List[LeadResponse]:
        """Search leads by name, email, or address."""
        if not HAS_DATABASE or not query:
            return []

        with db_manager.get_session() as session:
            search_term = f"%{query}%"
            leads = (
                session.query(BusinessLead)
                .filter(
                    or_(
                        BusinessLead.business_name.ilike(search_term),
                        BusinessLead.email.ilike(search_term),
                        BusinessLead.full_address.ilike(search_term),
                        BusinessLead.city.ilike(search_term),
                        BusinessLead.phone.ilike(search_term),
                    )
                )
                .limit(limit)
                .all()
            )
            return [self._lead_to_response(lead) for lead in leads]

    def _apply_filters(self, query, filters: LeadFilters):
        """Apply filters to query."""
        if filters.city:
            query = query.filter(BusinessLead.city.ilike(f"%{filters.city}%"))

        if filters.state:
            query = query.filter(BusinessLead.state.ilike(f"%{filters.state}%"))

        if filters.country:
            query = query.filter(BusinessLead.country.ilike(f"%{filters.country}%"))

        if filters.pincode:
            query = query.filter(BusinessLead.pin_code == filters.pincode)

        if filters.category:
            query = query.filter(BusinessLead.category.ilike(f"%{filters.category}%"))

        if filters.has_email is True:
            query = query.filter(BusinessLead.email.isnot(None), BusinessLead.email != '')
        elif filters.has_email is False:
            query = query.filter(or_(BusinessLead.email.is_(None), BusinessLead.email == ''))

        if filters.has_phone is True:
            query = query.filter(BusinessLead.phone.isnot(None), BusinessLead.phone != '')
        elif filters.has_phone is False:
            query = query.filter(or_(BusinessLead.phone.is_(None), BusinessLead.phone == ''))

        if filters.has_website is True:
            query = query.filter(BusinessLead.website.isnot(None), BusinessLead.website != '')
        elif filters.has_website is False:
            query = query.filter(or_(BusinessLead.website.is_(None), BusinessLead.website == ''))

        if filters.has_facebook is True:
            query = query.filter(BusinessLead.social_facebook.isnot(None))
        if filters.has_instagram is True:
            query = query.filter(BusinessLead.social_instagram.isnot(None))
        if filters.has_linkedin is True:
            query = query.filter(BusinessLead.social_linkedin.isnot(None))

        if filters.min_rating is not None:
            query = query.filter(BusinessLead.rating >= filters.min_rating)
        if filters.max_rating is not None:
            query = query.filter(BusinessLead.rating <= filters.max_rating)

        if filters.min_reviews is not None:
            query = query.filter(BusinessLead.review_count >= filters.min_reviews)
        if filters.max_reviews is not None:
            query = query.filter(BusinessLead.review_count <= filters.max_reviews)

        if filters.min_quality is not None:
            query = query.filter(BusinessLead.data_quality_score >= filters.min_quality)

        # Star rating filters
        if filters.min_star_rating is not None:
            query = query.filter(BusinessLead.star_rating >= filters.min_star_rating)
        if filters.max_star_rating is not None:
            query = query.filter(BusinessLead.star_rating <= filters.max_star_rating)

        # Note: job_id filter removed - field doesn't exist in model

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    BusinessLead.business_name.ilike(search_term),
                    BusinessLead.full_address.ilike(search_term),
                )
            )

        return query

    def _get_distinct_values(self, session, column, limit: int = 100) -> List[str]:
        """Get distinct non-null values for a column."""
        values = (
            session.query(column)
            .filter(column.isnot(None), column != '')
            .distinct()
            .limit(limit)
            .all()
        )
        return [v[0] for v in values if v[0]]

    def _lead_to_response(self, lead) -> LeadResponse:
        """Convert database lead to response schema."""
        return LeadResponse(
            id=lead.id,
            job_id=None,  # job_id not in model
            business_name=lead.business_name,
            phone=lead.phone,
            email=lead.email,
            website=lead.website,
            category=lead.category,
            address=lead.full_address,
            city=lead.city,
            state=lead.state,
            pincode=lead.pin_code,
            country=lead.country,
            rating=lead.rating,
            review_count=lead.review_count,
            price_level=lead.price_level,
            latitude=lead.latitude,
            longitude=lead.longitude,
            maps_url=lead.maps_url,
            place_id=lead.place_id,
            email_2=getattr(lead, 'email_1', None),
            email_3=getattr(lead, 'email_2', None),
            phone_2=getattr(lead, 'phone_1', None),
            phone_3=getattr(lead, 'phone_2', None),
            facebook=lead.social_facebook,
            instagram=lead.social_instagram,
            linkedin=lead.social_linkedin,
            twitter=lead.social_twitter,
            youtube=getattr(lead, 'social_youtube', None),
            contact_person_1=getattr(lead, 'contact_name_1', None),
            contact_title_1=getattr(lead, 'contact_title_1', None),
            contact_email_1=getattr(lead, 'contact_email_1', None),
            contact_person_2=getattr(lead, 'contact_name_2', None),
            contact_title_2=getattr(lead, 'contact_title_2', None),
            contact_email_2=getattr(lead, 'contact_email_2', None),
            employee_count=getattr(lead, 'employees_min', None),
            employee_range=getattr(lead, 'employees', None),
            founded_year=getattr(lead, 'founded_year', None),
            company_type=getattr(lead, 'company_type', None),
            revenue_estimate=getattr(lead, 'revenue', None),
            description=getattr(lead, 'description', None),
            quality_score=lead.data_quality_score,
            data_quality_score=lead.data_quality_score,
            star_rating=getattr(lead, 'star_rating', None),
            search_query=lead.search_query,
            notes=None,  # notes not in model
            tags=None,  # tags not in model
            status=None,  # status not in model
            scraped_at=getattr(lead, 'scraped_at', None),
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )


# Singleton instance
lead_service = LeadService()
