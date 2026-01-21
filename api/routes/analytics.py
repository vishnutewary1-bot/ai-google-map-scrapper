"""Analytics API routes."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.schemas.responses import StatsResponse
from api.services.lead_service import lead_service

# Database imports for job stats
try:
    from database import db_manager
    from database.models import ScrapeJob
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get comprehensive statistics about leads and jobs."""
    try:
        # Get lead stats
        lead_stats = lead_service.get_stats()

        # Get job stats
        job_stats = _get_job_stats()

        return StatsResponse(
            total_leads=lead_stats.get("total_leads", 0),
            leads_with_email=lead_stats.get("leads_with_email", 0),
            leads_with_phone=lead_stats.get("leads_with_phone", 0),
            leads_with_website=lead_stats.get("leads_with_website", 0),
            leads_with_social=lead_stats.get("leads_with_social", 0),
            avg_quality_score=lead_stats.get("avg_quality_score", 0.0),
            high_quality_leads=lead_stats.get("high_quality_leads", 0),
            medium_quality_leads=lead_stats.get("medium_quality_leads", 0),
            low_quality_leads=lead_stats.get("low_quality_leads", 0),
            top_categories=lead_stats.get("top_categories", []),
            top_cities=lead_stats.get("top_cities", []),
            leads_today=lead_stats.get("leads_today", 0),
            leads_this_week=lead_stats.get("leads_this_week", 0),
            leads_this_month=lead_stats.get("leads_this_month", 0),
            total_jobs=job_stats.get("total_jobs", 0),
            jobs_completed=job_stats.get("jobs_completed", 0),
            jobs_failed=job_stats.get("jobs_failed", 0),
            jobs_running=job_stats.get("jobs_running", 0),
        )

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/quality")
async def get_quality_analytics():
    """Get detailed quality score analytics."""
    try:
        stats = lead_service.get_stats()
        return {
            "avg_quality_score": stats.get("avg_quality_score", 0),
            "high_quality_leads": stats.get("high_quality_leads", 0),
            "medium_quality_leads": stats.get("medium_quality_leads", 0),
            "low_quality_leads": stats.get("low_quality_leads", 0),
            "quality_distribution": {
                "high": stats.get("high_quality_leads", 0),
                "medium": stats.get("medium_quality_leads", 0),
                "low": stats.get("low_quality_leads", 0),
            }
        }
    except Exception as e:
        logger.error(f"Failed to get quality analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/geographic")
async def get_geographic_analytics():
    """Get geographic distribution analytics."""
    try:
        stats = lead_service.get_stats()
        return {
            "top_cities": stats.get("top_cities", []),
            "total_cities": len(stats.get("top_cities", [])),
        }
    except Exception as e:
        logger.error(f"Failed to get geographic analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/categories")
async def get_category_analytics():
    """Get category distribution analytics."""
    try:
        stats = lead_service.get_stats()
        return {
            "top_categories": stats.get("top_categories", []),
            "total_categories": len(stats.get("top_categories", [])),
        }
    except Exception as e:
        logger.error(f"Failed to get category analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/contact-coverage")
async def get_contact_coverage():
    """Get contact information coverage analytics."""
    try:
        stats = lead_service.get_stats()
        total = stats.get("total_leads", 1)  # Avoid division by zero

        return {
            "total_leads": total,
            "email_coverage": {
                "count": stats.get("leads_with_email", 0),
                "percentage": round(stats.get("leads_with_email", 0) / total * 100, 1),
            },
            "phone_coverage": {
                "count": stats.get("leads_with_phone", 0),
                "percentage": round(stats.get("leads_with_phone", 0) / total * 100, 1),
            },
            "website_coverage": {
                "count": stats.get("leads_with_website", 0),
                "percentage": round(stats.get("leads_with_website", 0) / total * 100, 1),
            },
            "social_coverage": {
                "count": stats.get("leads_with_social", 0),
                "percentage": round(stats.get("leads_with_social", 0) / total * 100, 1),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get contact coverage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/timeline")
async def get_timeline_analytics():
    """Get lead acquisition timeline analytics."""
    try:
        stats = lead_service.get_stats()
        return {
            "leads_today": stats.get("leads_today", 0),
            "leads_this_week": stats.get("leads_this_week", 0),
            "leads_this_month": stats.get("leads_this_month", 0),
        }
    except Exception as e:
        logger.error(f"Failed to get timeline analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_job_stats() -> dict:
    """Get job statistics."""
    if not HAS_DATABASE or db_manager is None or db_manager.SessionLocal is None:
        return {}

    try:
        with db_manager.get_session() as session:
            total = session.query(ScrapeJob).count()
            completed = session.query(ScrapeJob).filter(
                ScrapeJob.status == "completed"
            ).count()
            failed = session.query(ScrapeJob).filter(
                ScrapeJob.status == "failed"
            ).count()
            running = session.query(ScrapeJob).filter(
                ScrapeJob.status == "running"
            ).count()

            return {
                "total_jobs": total,
                "jobs_completed": completed,
                "jobs_failed": failed,
                "jobs_running": running,
            }
    except Exception as e:
        logger.error(f"Failed to get job stats: {e}")
        return {}
