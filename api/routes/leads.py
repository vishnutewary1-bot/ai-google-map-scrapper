"""Leads API routes."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from api.schemas.requests import LeadFilters, LeadUpdateRequest
from api.schemas.responses import LeadResponse, LeadListResponse
from api.services.lead_service import lead_service

router = APIRouter()


@router.get("/leads", response_model=LeadListResponse)
async def get_leads(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    # Location filters
    city: Optional[str] = None,
    state: Optional[str] = None,
    country: Optional[str] = None,
    pincode: Optional[str] = None,
    # Category filter
    category: Optional[str] = None,
    # Contact filters
    has_email: Optional[bool] = None,
    has_phone: Optional[bool] = None,
    has_website: Optional[bool] = None,
    # Social media filters
    has_facebook: Optional[bool] = None,
    has_instagram: Optional[bool] = None,
    has_linkedin: Optional[bool] = None,
    # Rating filters
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    max_rating: Optional[float] = Query(None, ge=0, le=5),
    # Review filters
    min_reviews: Optional[int] = Query(None, ge=0),
    max_reviews: Optional[int] = Query(None, ge=0),
    # Quality filter
    min_quality: Optional[int] = Query(None, ge=0, le=100),
    # Star rating filter
    min_star_rating: Optional[int] = Query(None, ge=1, le=5),
    max_star_rating: Optional[int] = Query(None, ge=1, le=5),
    # Search filter
    search: Optional[str] = None,
    # Job filter
    job_id: Optional[int] = None,
    # Include aggregations
    include_aggregations: bool = False,
):
    """
    Get leads with filtering and pagination.

    Returns a list of leads matching the specified filters.
    """
    try:
        filters = LeadFilters(
            city=city,
            state=state,
            country=country,
            pincode=pincode,
            category=category,
            has_email=has_email,
            has_phone=has_phone,
            has_website=has_website,
            has_facebook=has_facebook,
            has_instagram=has_instagram,
            has_linkedin=has_linkedin,
            min_rating=min_rating,
            max_rating=max_rating,
            min_reviews=min_reviews,
            max_reviews=max_reviews,
            min_quality=min_quality,
            min_star_rating=min_star_rating,
            max_star_rating=max_star_rating,
            search=search,
            job_id=job_id,
        )

        return lead_service.get_leads(
            filters=filters,
            limit=limit,
            offset=offset,
            include_aggregations=include_aggregations,
        )

    except Exception as e:
        logger.error(f"Failed to get leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: int):
    """Get a single lead by ID."""
    lead = lead_service.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.put("/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(lead_id: int, request: LeadUpdateRequest):
    """Update a lead."""
    try:
        lead = lead_service.update_lead(lead_id, request)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return lead
    except Exception as e:
        logger.error(f"Failed to update lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: int):
    """Delete a lead."""
    success = lead_service.delete_lead(lead_id)
    if not success:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"success": True, "message": "Lead deleted"}


@router.post("/leads/bulk-delete")
async def bulk_delete_leads(lead_ids: List[int]):
    """Delete multiple leads."""
    try:
        deleted = lead_service.bulk_delete(lead_ids)
        return {"success": True, "deleted": deleted}
    except Exception as e:
        logger.error(f"Failed to bulk delete leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leads/bulk-update")
async def bulk_update_leads(lead_ids: List[int], updates: LeadUpdateRequest):
    """Update multiple leads with the same values."""
    try:
        update_dict = updates.model_dump(exclude_unset=True)
        updated = lead_service.bulk_update(lead_ids, update_dict)
        return {"success": True, "updated": updated}
    except Exception as e:
        logger.error(f"Failed to bulk update leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/search/{query}")
async def search_leads(query: str, limit: int = 50):
    """Search leads by name, email, or address."""
    try:
        leads = lead_service.search(query, limit=limit)
        return {"leads": leads, "total": len(leads)}
    except Exception as e:
        logger.error(f"Failed to search leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/cities")
async def get_cities():
    """Get list of unique cities."""
    try:
        response = lead_service.get_leads(limit=1, include_aggregations=True)
        return {"cities": response.cities or []}
    except Exception as e:
        logger.error(f"Failed to get cities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/categories")
async def get_categories():
    """Get list of unique categories."""
    try:
        response = lead_service.get_leads(limit=1, include_aggregations=True)
        return {"categories": response.categories or []}
    except Exception as e:
        logger.error(f"Failed to get categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))
