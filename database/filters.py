"""Shared database filter logic - single source of truth for lead filtering.

This module consolidates filter logic that was previously duplicated in:
- api/services/lead_service.py (_apply_filters method)
- utils/exporter.py (_fetch_from_database method)
- api/routes/features.py (multiple filter applications)
"""

from typing import Optional, Dict, Any
from sqlalchemy import or_, and_
from loguru import logger


class LeadFilters:
    """
    Utility class for applying consistent filters to BusinessLead queries.

    This centralizes all filter logic to ensure consistency across the application.
    """

    @staticmethod
    def apply_filters(query, filters: Dict[str, Any], BusinessLead):
        """
        Apply filters to a BusinessLead query.

        Args:
            query: SQLAlchemy query object
            filters: Dictionary of filter parameters
            BusinessLead: The BusinessLead model class

        Returns:
            Filtered query

        Supported filters:
            - has_phone: bool - Filter by presence of phone
            - has_website: bool - Filter by presence of website
            - has_email: bool - Filter by presence of email
            - has_social: bool - Filter by presence of any social media
            - city: str - Filter by city (exact match)
            - state: str - Filter by state (exact match)
            - country: str - Filter by country (exact match)
            - category: str - Filter by category (exact match)
            - min_quality_score / max_quality_score: int - Quality score range
            - min_rating / max_rating: float - Rating range
            - min_reviews / max_reviews: int - Review count range
            - search_query: str - Filter by search query used
            - founded_after / founded_before: int - Founded year range
            - has_employees: bool - Has employee count
            - has_revenue: bool - Has revenue estimate
            - limit: int - Limit results
            - order_by: str - 'quality', 'rating', 'reviews', 'newest'
            - search: str - Full-text search on name and address
        """
        if not filters:
            return query

        # Boolean presence filters
        if filters.get('has_phone'):
            query = query.filter(BusinessLead.phone.isnot(None), BusinessLead.phone != '')

        if filters.get('has_website'):
            query = query.filter(BusinessLead.website.isnot(None), BusinessLead.website != '')

        if filters.get('has_email'):
            query = query.filter(
                or_(
                    and_(BusinessLead.email.isnot(None), BusinessLead.email != ''),
                    and_(BusinessLead.email_1.isnot(None), BusinessLead.email_1 != '')
                )
            )

        if filters.get('has_social'):
            query = query.filter(
                or_(
                    BusinessLead.social_facebook.isnot(None),
                    BusinessLead.social_instagram.isnot(None),
                    BusinessLead.social_linkedin.isnot(None),
                    BusinessLead.social_twitter.isnot(None),
                )
            )

        # Individual social media filters
        if filters.get('has_facebook'):
            query = query.filter(BusinessLead.social_facebook.isnot(None))
        if filters.get('has_instagram'):
            query = query.filter(BusinessLead.social_instagram.isnot(None))
        if filters.get('has_linkedin'):
            query = query.filter(BusinessLead.social_linkedin.isnot(None))
        if filters.get('has_twitter'):
            query = query.filter(BusinessLead.social_twitter.isnot(None))

        # Location filters
        if filters.get('city'):
            query = query.filter(BusinessLead.city == filters['city'])

        if filters.get('state'):
            query = query.filter(BusinessLead.state == filters['state'])

        if filters.get('country'):
            query = query.filter(BusinessLead.country == filters['country'])

        if filters.get('pincode'):
            query = query.filter(BusinessLead.pin_code == filters['pincode'])

        # Category filter
        if filters.get('category'):
            query = query.filter(BusinessLead.category == filters['category'])

        # Quality score filters
        if filters.get('min_quality_score'):
            query = query.filter(
                BusinessLead.data_quality_score >= filters['min_quality_score']
            )

        if filters.get('max_quality_score'):
            query = query.filter(
                BusinessLead.data_quality_score <= filters['max_quality_score']
            )

        # Rating filters
        if filters.get('min_rating') is not None:
            query = query.filter(BusinessLead.rating >= filters['min_rating'])

        if filters.get('max_rating') is not None:
            query = query.filter(BusinessLead.rating <= filters['max_rating'])

        # Review count filters
        if filters.get('min_reviews') is not None:
            query = query.filter(BusinessLead.review_count >= filters['min_reviews'])

        if filters.get('max_reviews') is not None:
            query = query.filter(BusinessLead.review_count <= filters['max_reviews'])

        # Search query filter
        if filters.get('search_query'):
            query = query.filter(BusinessLead.search_query == filters['search_query'])

        # Founded year filters
        if filters.get('founded_after'):
            query = query.filter(BusinessLead.founded_year >= filters['founded_after'])

        if filters.get('founded_before'):
            query = query.filter(BusinessLead.founded_year <= filters['founded_before'])

        # Business data presence filters
        if filters.get('has_employees'):
            query = query.filter(BusinessLead.employees.isnot(None))

        if filters.get('has_revenue'):
            query = query.filter(BusinessLead.revenue.isnot(None))

        # Full-text search filter
        if filters.get('search'):
            search_term = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    BusinessLead.business_name.ilike(search_term),
                    BusinessLead.full_address.ilike(search_term),
                    BusinessLead.city.ilike(search_term),
                    BusinessLead.email.ilike(search_term),
                    BusinessLead.phone.ilike(search_term),
                )
            )

        # Limit results
        if filters.get('limit'):
            query = query.limit(filters['limit'])

        # Ordering
        order_by = filters.get('order_by')
        if order_by == 'quality':
            query = query.order_by(BusinessLead.data_quality_score.desc())
        elif order_by == 'rating':
            query = query.order_by(BusinessLead.rating.desc())
        elif order_by == 'reviews':
            query = query.order_by(BusinessLead.review_count.desc())
        elif order_by == 'newest':
            query = query.order_by(BusinessLead.scraped_at.desc())

        return query

    @staticmethod
    def apply_filters_from_schema(query, filters, BusinessLead):
        """
        Apply filters from a Pydantic schema object (LeadFilters).

        This is a convenience method for use with the API layer.

        Args:
            query: SQLAlchemy query object
            filters: LeadFilters Pydantic schema instance
            BusinessLead: The BusinessLead model class

        Returns:
            Filtered query
        """
        if not filters:
            return query

        # Convert schema to dict, handling None values
        filter_dict = {}

        # Location filters
        if filters.city:
            filter_dict['city'] = filters.city
        if filters.state:
            filter_dict['state'] = filters.state
        if filters.country:
            filter_dict['country'] = filters.country
        if filters.pincode:
            filter_dict['pincode'] = filters.pincode

        # Category filter
        if filters.category:
            filter_dict['category'] = filters.category

        # Boolean presence filters
        if filters.has_email is not None:
            filter_dict['has_email'] = filters.has_email
        if filters.has_phone is not None:
            filter_dict['has_phone'] = filters.has_phone
        if filters.has_website is not None:
            filter_dict['has_website'] = filters.has_website

        # Social media filters
        if getattr(filters, 'has_facebook', None) is True:
            filter_dict['has_facebook'] = True
        if getattr(filters, 'has_instagram', None) is True:
            filter_dict['has_instagram'] = True
        if getattr(filters, 'has_linkedin', None) is True:
            filter_dict['has_linkedin'] = True

        # Rating filters
        if filters.min_rating is not None:
            filter_dict['min_rating'] = filters.min_rating
        if filters.max_rating is not None:
            filter_dict['max_rating'] = filters.max_rating

        # Review count filters
        if filters.min_reviews is not None:
            filter_dict['min_reviews'] = filters.min_reviews
        if filters.max_reviews is not None:
            filter_dict['max_reviews'] = filters.max_reviews

        # Quality filter
        if filters.min_quality is not None:
            filter_dict['min_quality_score'] = filters.min_quality

        # Search filter
        if filters.search:
            filter_dict['search'] = filters.search

        return LeadFilters.apply_filters(query, filter_dict, BusinessLead)


def apply_filters(query, filters: Dict[str, Any], BusinessLead):
    """
    Convenience function to apply filters to a query.

    Args:
        query: SQLAlchemy query object
        filters: Dictionary of filter parameters
        BusinessLead: The BusinessLead model class

    Returns:
        Filtered query
    """
    return LeadFilters.apply_filters(query, filters, BusinessLead)
