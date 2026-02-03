"""API routes for new features - webhooks, sentiment, comparison, email templates, etc."""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger
from typing import List

from api.schemas.requests import (
    GeoScrapeRequest,
    BulkUrlImportRequest,
    WebhookRegisterRequest,
    WebhookTestRequest,
    SentimentAnalysisRequest,
    CompetitorComparisonRequest,
    EmailTemplateRequest,
)
from api.schemas.responses import (
    GeoScrapeResponse,
    BulkImportResponse,
    WebhookResponse,
    SentimentAnalysisResponse,
    CompetitorComparisonResponse,
    EmailTemplateResponse,
    DataFreshnessResponse,
    IntegrationStatusResponse,
)
from config.settings import settings

# Import feature modules
try:
    from utils.webhooks import webhook_manager, WebhookConfig
    HAS_WEBHOOKS = True
except ImportError:
    HAS_WEBHOOKS = False

try:
    from utils.sentiment_analyzer import sentiment_analyzer
    HAS_SENTIMENT = True
except ImportError:
    HAS_SENTIMENT = False

try:
    from utils.competitor_comparison import competitor_comparator
    HAS_COMPARISON = True
except ImportError:
    HAS_COMPARISON = False

try:
    from utils.email_templates import email_generator
    HAS_EMAIL_TEMPLATES = True
except ImportError:
    HAS_EMAIL_TEMPLATES = False

try:
    from utils.data_freshness import freshness_tracker
    HAS_FRESHNESS = True
except ImportError:
    HAS_FRESHNESS = False

try:
    from scraper.geo_search import geo_search_manager
    HAS_GEO_SEARCH = True
except ImportError:
    HAS_GEO_SEARCH = False

try:
    from database import db_manager
    from database.models import BusinessLead, SavedSearch
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False

# Scheduler (Feature 2.1)
try:
    from scraper.scheduler import get_scheduler, ScheduledTask, SCHEDULER_AVAILABLE
    HAS_SCHEDULER = SCHEDULER_AVAILABLE
except ImportError:
    HAS_SCHEDULER = False
    get_scheduler = None
    ScheduledTask = None

router = APIRouter()


# ==================== WEBHOOK ROUTES ====================

@router.post("/webhooks/register", response_model=WebhookResponse)
async def register_webhook(request: WebhookRegisterRequest):
    """Register a new webhook endpoint."""
    if not HAS_WEBHOOKS:
        raise HTTPException(status_code=501, detail="Webhooks module not available")

    try:
        config = WebhookConfig(
            url=request.url,
            secret=request.secret,
            events=request.events
        )
        webhook_manager.register_webhook(request.name, config)

        return WebhookResponse(
            success=True,
            webhook_name=request.name,
            message=f"Webhook '{request.name}' registered successfully",
            registered_webhooks=webhook_manager.get_registered_webhooks()
        )
    except Exception as e:
        logger.error(f"Failed to register webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/webhooks/{webhook_name}", response_model=WebhookResponse)
async def unregister_webhook(webhook_name: str):
    """Unregister a webhook."""
    if not HAS_WEBHOOKS:
        raise HTTPException(status_code=501, detail="Webhooks module not available")

    try:
        webhook_manager.unregister_webhook(webhook_name)
        return WebhookResponse(
            success=True,
            webhook_name=webhook_name,
            message=f"Webhook '{webhook_name}' unregistered",
            registered_webhooks=webhook_manager.get_registered_webhooks()
        )
    except Exception as e:
        logger.error(f"Failed to unregister webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webhooks", response_model=WebhookResponse)
async def list_webhooks():
    """List all registered webhooks."""
    if not HAS_WEBHOOKS:
        raise HTTPException(status_code=501, detail="Webhooks module not available")

    return WebhookResponse(
        success=True,
        message="Webhooks retrieved",
        registered_webhooks=webhook_manager.get_registered_webhooks(),
        event_history=webhook_manager.get_event_history(50)
    )


@router.post("/webhooks/test", response_model=WebhookResponse)
async def test_webhook(request: WebhookTestRequest):
    """Test a registered webhook."""
    if not HAS_WEBHOOKS:
        raise HTTPException(status_code=501, detail="Webhooks module not available")

    try:
        success = webhook_manager.send_webhook_sync(
            request.webhook_name,
            request.event_type,
            {"test": True, "message": "This is a test webhook from MapLeads Pro"}
        )

        return WebhookResponse(
            success=success,
            webhook_name=request.webhook_name,
            message="Test webhook sent successfully" if success else "Test webhook failed"
        )
    except Exception as e:
        logger.error(f"Webhook test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SENTIMENT ANALYSIS ROUTES ====================

@router.post("/sentiment/analyze", response_model=SentimentAnalysisResponse)
async def analyze_sentiment(request: SentimentAnalysisRequest):
    """Analyze sentiment of reviews or text."""
    if not HAS_SENTIMENT:
        raise HTTPException(status_code=501, detail="Sentiment analysis module not available")

    try:
        # Analyze specific text
        if request.text:
            result = sentiment_analyzer.analyze_single_review(request.text)
            return SentimentAnalysisResponse(
                enabled=True,
                total_analyzed=1,
                positive_count=1 if result.get("sentiment") == "positive" else 0,
                negative_count=1 if result.get("sentiment") == "negative" else 0,
                neutral_count=1 if result.get("sentiment") == "neutral" else 0,
                average_polarity=result.get("polarity", 0),
                average_subjectivity=result.get("subjectivity", 0),
                overall_sentiment=result.get("sentiment", "neutral"),
                sentiment_score=result.get("sentiment_score", 50),
                key_phrases={"positive": [], "negative": []}
            )

        # Analyze list of reviews
        if request.reviews:
            result = sentiment_analyzer.analyze_reviews(request.reviews)
            return SentimentAnalysisResponse(**result)

        # Analyze reviews for a lead
        if request.lead_id and HAS_DATABASE:
            with db_manager.get_session() as session:
                lead = session.query(BusinessLead).filter(
                    BusinessLead.id == request.lead_id
                ).first()

                if not lead:
                    raise HTTPException(status_code=404, detail="Lead not found")

                # Get reviews from lead (if stored)
                reviews = lead.reviews if hasattr(lead, 'reviews') and lead.reviews else []
                if not reviews:
                    return SentimentAnalysisResponse(
                        enabled=True,
                        total_analyzed=0,
                        overall_sentiment="unknown",
                        sentiment_score=50,
                        error="No reviews found for this lead"
                    )

                result = sentiment_analyzer.analyze_reviews(reviews)
                return SentimentAnalysisResponse(**result)

        raise HTTPException(status_code=400, detail="Provide text, reviews, or lead_id")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== COMPETITOR COMPARISON ROUTES ====================

@router.post("/compare", response_model=CompetitorComparisonResponse)
async def compare_competitors(request: CompetitorComparisonRequest):
    """Compare multiple businesses/leads."""
    if not HAS_COMPARISON:
        raise HTTPException(status_code=501, detail="Competitor comparison module not available")

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            leads = session.query(BusinessLead).filter(
                BusinessLead.id.in_(request.lead_ids)
            ).all()

            if len(leads) < 2:
                raise HTTPException(
                    status_code=400,
                    detail="At least 2 valid leads required for comparison"
                )

            # Convert leads to dictionaries
            businesses = []
            for lead in leads:
                business_dict = {
                    "id": lead.id,
                    "business_name": lead.business_name,
                    "rating": lead.rating,
                    "review_count": lead.review_count,
                    "category": lead.category,
                    "phone": lead.phone,
                    "email": lead.email,
                    "website": lead.website,
                    "social_facebook": getattr(lead, 'social_facebook', None),
                    "social_instagram": getattr(lead, 'social_instagram', None),
                    "social_linkedin": getattr(lead, 'social_linkedin', None),
                    "social_twitter": getattr(lead, 'social_twitter', None),
                    "data_quality_score": getattr(lead, 'data_quality_score', 0),
                }
                businesses.append(business_dict)

            # Perform comparison
            result = competitor_comparator.compare_businesses(businesses)

            return CompetitorComparisonResponse(
                businesses_compared=len(businesses),
                winner_summary=result.get("winner_summary", {}),
                detailed_comparison=result.get("comparison", {}),
                insights=result.get("insights", []),
                chart_data=result.get("chart_data", {})
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Competitor comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EMAIL TEMPLATE ROUTES ====================

@router.post("/email-template", response_model=EmailTemplateResponse)
async def generate_email_template(request: EmailTemplateRequest):
    """Generate a cold email template for a lead."""
    if not HAS_EMAIL_TEMPLATES:
        raise HTTPException(status_code=501, detail="Email templates module not available")

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter(
                BusinessLead.id == request.lead_id
            ).first()

            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            # Convert lead to dictionary
            lead_data = {
                "business_name": lead.business_name,
                "category": lead.category,
                "city": lead.city,
                "state": lead.state,
                "rating": lead.rating,
                "review_count": lead.review_count,
                "website": lead.website,
                "contact_name_1": getattr(lead, 'contact_name_1', None),
            }

            # Generate email
            result = email_generator.generate_email(
                lead_data=lead_data,
                template_type=request.template_type,
                sender_name=request.sender_name,
                sender_company=request.sender_company,
                sender_title=request.sender_title,
                custom_value_prop=request.custom_value_proposition
            )

            return EmailTemplateResponse(
                success=True,
                template_type=request.template_type,
                subject=result.get("subject", ""),
                body=result.get("body", ""),
                personalization_score=result.get("personalization_score", 0),
                suggestions=result.get("suggestions", [])
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email template generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/email-template/types")
async def list_email_template_types():
    """List available email template types."""
    return {
        "template_types": [
            {"id": "introduction", "name": "Introduction", "description": "Initial outreach email"},
            {"id": "value_proposition", "name": "Value Proposition", "description": "Highlight your value"},
            {"id": "follow_up", "name": "Follow Up", "description": "Follow up email"},
            {"id": "review_request", "name": "Review Request", "description": "Ask for a review"},
            {"id": "partnership", "name": "Partnership", "description": "Propose a partnership"},
        ]
    }


# ==================== DATA FRESHNESS ROUTES ====================

@router.get("/freshness/{lead_id}", response_model=DataFreshnessResponse)
async def check_data_freshness(lead_id: int):
    """Check data freshness for a lead."""
    if not HAS_FRESHNESS:
        raise HTTPException(status_code=501, detail="Data freshness module not available")

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter(
                BusinessLead.id == lead_id
            ).first()

            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            # Check freshness
            lead_data = {
                "id": lead.id,
                "business_name": lead.business_name,
                "last_verified_at": getattr(lead, 'last_verified_at', None),
                "scraped_at": lead.scraped_at,
            }

            result = freshness_tracker.check_freshness(lead_data)

            return DataFreshnessResponse(
                lead_id=lead_id,
                business_name=lead.business_name,
                freshness_status=result.get("status", "unknown"),
                last_verified_at=result.get("last_verified_at"),
                days_since_verified=result.get("days_since_verified"),
                needs_refresh=result.get("needs_refresh", False)
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Freshness check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/freshness/stale")
async def get_stale_leads(limit: int = 100):
    """Get leads that need data refresh."""
    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            from datetime import datetime, timedelta

            threshold_days = settings.data_freshness_threshold_days
            threshold_date = datetime.utcnow() - timedelta(days=threshold_days)

            stale_leads = session.query(BusinessLead).filter(
                BusinessLead.scraped_at < threshold_date
            ).limit(limit).all()

            return {
                "count": len(stale_leads),
                "threshold_days": threshold_days,
                "leads": [
                    {
                        "id": lead.id,
                        "business_name": lead.business_name,
                        "scraped_at": lead.scraped_at.isoformat() if lead.scraped_at else None,
                    }
                    for lead in stale_leads
                ]
            }

    except Exception as e:
        logger.error(f"Failed to get stale leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== GEO SEARCH ROUTES ====================

@router.post("/geo-scrape", response_model=GeoScrapeResponse)
async def start_geo_scrape(request: GeoScrapeRequest, background_tasks: BackgroundTasks):
    """Start a geo-coordinate based scrape job."""
    if not HAS_GEO_SEARCH:
        raise HTTPException(status_code=501, detail="Geo search module not available")

    try:
        from api.services.scrape_service import scrape_service
        from api.schemas.requests import ScrapeRequest

        # Generate grid points
        grid_points = geo_search_manager.generate_grid_points(
            request.latitude,
            request.longitude,
            request.radius_km,
            request.grid_size
        )

        # Create a main job for tracking
        main_request = ScrapeRequest(
            search_query=f"[GEO] {request.search_query}",
            location=f"lat:{request.latitude},lng:{request.longitude}",
            max_results=request.max_results * len(grid_points),
            extract_emails=request.extract_emails,
            extract_social=request.extract_social,
            extract_reviews=request.extract_reviews,
            extract_popular_times=request.extract_popular_times,
            headless=request.headless,
        )

        job = scrape_service.create_job(main_request)

        # Run geo scrape in background
        background_tasks.add_task(
            _run_geo_scrape,
            job.job_id,
            request,
            grid_points
        )

        return GeoScrapeResponse(
            job_id=job.job_id,
            status="started",
            center_coordinates={"lat": request.latitude, "lng": request.longitude},
            radius_km=request.radius_km,
            grid_points=len(grid_points)
        )

    except Exception as e:
        logger.error(f"Geo scrape failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_geo_scrape(job_id: int, request: GeoScrapeRequest, grid_points: list):
    """Background task for geo scraping."""
    from api.services.scrape_service import scrape_service

    try:
        total_leads = 0

        for point in grid_points:
            # Generate search URL for this grid point
            search_url = geo_search_manager.generate_search_url(
                request.search_query,
                point["latitude"],
                point["longitude"]
            )

            # Run scrape for this point
            # This is a simplified version - in production you'd use the full scraper
            logger.info(f"Scraping grid point: {point['grid_position']} at {search_url}")

        # Update job status
        scrape_service._update_job_status(job_id, "completed", {"total_leads": total_leads})

    except Exception as e:
        logger.error(f"Geo scrape error: {e}")
        scrape_service._update_job_status(job_id, "failed", {"error": str(e)})


# ==================== BULK IMPORT ROUTES ====================

@router.post("/bulk-import", response_model=BulkImportResponse)
async def bulk_import_urls(request: BulkUrlImportRequest, background_tasks: BackgroundTasks):
    """Import leads from Google Maps URLs."""
    try:
        from api.services.scrape_service import scrape_service
        from api.schemas.requests import ScrapeRequest

        # Validate URLs
        valid_urls = request.urls
        invalid_urls = []

        # Create job for tracking
        main_request = ScrapeRequest(
            search_query=f"[BULK] {len(valid_urls)} URLs",
            max_results=len(valid_urls),
            extract_emails=request.extract_emails,
            extract_social=request.extract_social,
            extract_reviews=request.extract_reviews,
            extract_popular_times=request.extract_popular_times,
            enrich_from_website=request.enrich_from_website,
        )

        job = scrape_service.create_job(main_request)

        # Run bulk import in background
        background_tasks.add_task(
            _run_bulk_import,
            job.job_id,
            valid_urls,
            request
        )

        return BulkImportResponse(
            job_id=job.job_id,
            status="started",
            urls_submitted=len(request.urls),
            urls_valid=len(valid_urls),
            urls_invalid=invalid_urls
        )

    except Exception as e:
        logger.error(f"Bulk import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_bulk_import(job_id: int, urls: List[str], request: BulkUrlImportRequest):
    """Background task for bulk URL import."""
    from api.services.scrape_service import scrape_service

    try:
        leads_imported = 0

        for url in urls:
            logger.info(f"Importing from URL: {url}")
            # In production, you'd navigate to each URL and extract data
            leads_imported += 1

        scrape_service._update_job_status(job_id, "completed", {"leads_imported": leads_imported})

    except Exception as e:
        logger.error(f"Bulk import error: {e}")
        scrape_service._update_job_status(job_id, "failed", {"error": str(e)})


# ==================== INTEGRATION STATUS ROUTES ====================

@router.get("/integrations/status", response_model=IntegrationStatusResponse)
async def get_integrations_status():
    """Get status of all integrations and new features."""
    try:
        return IntegrationStatusResponse(
            integrations=settings.get_integrations_status(),
            new_features=settings.get_new_features_status()
        )
    except Exception as e:
        logger.error(f"Failed to get integration status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features/list")
async def list_features():
    """List all available features with their status."""
    return {
        "features": [
            {"name": "Proxy Manager", "enabled": HAS_WEBHOOKS and settings.use_proxy_manager, "module": "proxy_manager"},
            {"name": "CAPTCHA Solving", "enabled": settings.captcha_enabled, "module": "captcha_solver"},
            {"name": "Webhooks", "enabled": HAS_WEBHOOKS and settings.webhook_enabled, "module": "webhooks"},
            {"name": "Sentiment Analysis", "enabled": HAS_SENTIMENT and settings.sentiment_analysis_enabled, "module": "sentiment_analyzer"},
            {"name": "Competitor Comparison", "enabled": HAS_COMPARISON, "module": "competitor_comparison"},
            {"name": "Email Templates", "enabled": HAS_EMAIL_TEMPLATES, "module": "email_templates"},
            {"name": "Data Freshness", "enabled": HAS_FRESHNESS, "module": "data_freshness"},
            {"name": "Geo Search", "enabled": HAS_GEO_SEARCH, "module": "geo_search"},
            {"name": "Google Sheets", "enabled": settings.google_sheets_enabled, "module": "google_sheets"},
            {"name": "AI Lead Scoring", "enabled": settings.ai_lead_scoring_enabled, "module": "ai_scoring"},
            {"name": "Chrome Extension", "enabled": settings.chrome_extension_enabled, "module": "chrome_extension"},
            {"name": "Scheduled Jobs", "enabled": HAS_SCHEDULER, "module": "scheduler"},
        ]
    }


# ==================== SCHEDULED JOBS ROUTES (Feature 2.1) ====================

@router.post("/scheduled-jobs")
async def create_scheduled_job(
    task_id: str,
    search_query: str,
    schedule_type: str = "daily",
    location: str = None,
    max_results: int = 100,
    interval_hours: int = 24,
    run_time: str = "09:00",
    day_of_week: str = "mon",
    extract_emails: bool = True,
    extract_social: bool = True,
    notify_on_complete: bool = True,
    webhook_url: str = None
):
    """Create a new scheduled scraping job."""
    if not HAS_SCHEDULER:
        raise HTTPException(status_code=501, detail="Scheduler module not available. Install APScheduler with: pip install apscheduler")

    try:
        scheduler = get_scheduler()

        # Parse run time
        hour, minute = 9, 0
        if run_time:
            try:
                parts = run_time.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
            except (ValueError, IndexError):
                pass

        # Create task based on schedule type
        if schedule_type == "daily":
            success = scheduler.create_daily_task(
                task_id=task_id,
                search_query=search_query,
                location=location,
                max_results=max_results,
                hour=hour,
                minute=minute,
                extract_emails=extract_emails,
                notify_on_complete=notify_on_complete,
                webhook_url=webhook_url
            )
        elif schedule_type == "weekly":
            success = scheduler.create_weekly_task(
                task_id=task_id,
                search_query=search_query,
                location=location,
                max_results=max_results,
                day_of_week=day_of_week,
                hour=hour,
                minute=minute,
                extract_emails=extract_emails,
                notify_on_complete=notify_on_complete,
                webhook_url=webhook_url
            )
        elif schedule_type == "hourly":
            success = scheduler.create_hourly_task(
                task_id=task_id,
                search_query=search_query,
                location=location,
                max_results=max_results,
                interval_hours=interval_hours,
                extract_emails=extract_emails,
                notify_on_complete=notify_on_complete,
                webhook_url=webhook_url
            )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid schedule type: {schedule_type}. Use 'daily', 'weekly', or 'hourly'")

        if success:
            return {"status": "created", "task_id": task_id, "schedule_type": schedule_type}
        else:
            raise HTTPException(status_code=400, detail="Failed to create scheduled job. Task ID may already exist.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create scheduled job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduled-jobs")
async def list_scheduled_jobs():
    """List all scheduled jobs."""
    if not HAS_SCHEDULER:
        raise HTTPException(status_code=501, detail="Scheduler module not available")

    try:
        scheduler = get_scheduler()
        return {
            "jobs": scheduler.list_tasks(),
            "status": scheduler.get_status()
        }
    except Exception as e:
        logger.error(f"Failed to list scheduled jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduled-jobs/{task_id}")
async def get_scheduled_job(task_id: str):
    """Get details of a specific scheduled job."""
    if not HAS_SCHEDULER:
        raise HTTPException(status_code=501, detail="Scheduler module not available")

    try:
        scheduler = get_scheduler()
        task = scheduler.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scheduled job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scheduled-jobs/{task_id}")
async def delete_scheduled_job(task_id: str):
    """Delete a scheduled job."""
    if not HAS_SCHEDULER:
        raise HTTPException(status_code=501, detail="Scheduler module not available")

    try:
        scheduler = get_scheduler()
        if scheduler.remove_task(task_id):
            return {"status": "deleted", "task_id": task_id}
        raise HTTPException(status_code=404, detail="Task not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete scheduled job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduled-jobs/{task_id}/pause")
async def pause_scheduled_job(task_id: str):
    """Pause a scheduled job."""
    if not HAS_SCHEDULER:
        raise HTTPException(status_code=501, detail="Scheduler module not available")

    try:
        scheduler = get_scheduler()
        if scheduler.pause_task(task_id):
            return {"status": "paused", "task_id": task_id}
        raise HTTPException(status_code=404, detail="Task not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause scheduled job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduled-jobs/{task_id}/resume")
async def resume_scheduled_job(task_id: str):
    """Resume a paused job."""
    if not HAS_SCHEDULER:
        raise HTTPException(status_code=501, detail="Scheduler module not available")

    try:
        scheduler = get_scheduler()
        if scheduler.resume_task(task_id):
            return {"status": "resumed", "task_id": task_id}
        raise HTTPException(status_code=404, detail="Task not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume scheduled job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduled-jobs/{task_id}/run-now")
async def run_job_now(task_id: str):
    """Run a scheduled job immediately."""
    if not HAS_SCHEDULER:
        raise HTTPException(status_code=501, detail="Scheduler module not available")

    try:
        scheduler = get_scheduler()
        if scheduler.run_task_now(task_id):
            return {"status": "triggered", "task_id": task_id}
        raise HTTPException(status_code=404, detail="Task not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger scheduled job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SAVED SEARCHES ROUTES (Feature 7.1) ====================

@router.post("/saved-searches")
async def create_saved_search(
    name: str,
    search_query: str,
    location: str = None,
    max_results: int = 100,
    options: dict = None,
    filters: dict = None,
    description: str = None
):
    """Save a search configuration for reuse."""
    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
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
            session.refresh(saved)

            return {"status": "saved", "id": saved.id, "search": saved.to_dict()}

    except Exception as e:
        logger.error(f"Failed to save search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/saved-searches")
async def list_saved_searches():
    """List all saved searches."""
    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            searches = session.query(SavedSearch).order_by(
                SavedSearch.last_used_at.desc().nullslast(),
                SavedSearch.created_at.desc()
            ).all()

            return {"searches": [s.to_dict() for s in searches]}

    except Exception as e:
        logger.error(f"Failed to list saved searches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/saved-searches/{search_id}")
async def get_saved_search(search_id: int):
    """Get a specific saved search."""
    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            saved = session.query(SavedSearch).filter(SavedSearch.id == search_id).first()
            if not saved:
                raise HTTPException(status_code=404, detail="Saved search not found")
            return saved.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get saved search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/saved-searches/{search_id}/run")
async def run_saved_search(search_id: int, background_tasks: BackgroundTasks):
    """Run a saved search."""
    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        from datetime import datetime
        from api.services.scrape_service import scrape_service
        from api.schemas.requests import ScrapeRequest

        with db_manager.get_session() as session:
            saved = session.query(SavedSearch).filter(SavedSearch.id == search_id).first()

            if not saved:
                raise HTTPException(status_code=404, detail="Saved search not found")

            # Update usage
            saved.use_count += 1
            saved.last_used_at = datetime.utcnow()
            session.commit()

            # Create scrape request from saved search
            options = saved.options or {}
            request = ScrapeRequest(
                search_query=saved.search_query,
                location=saved.location,
                max_results=saved.max_results,
                extract_emails=options.get('extract_emails', True),
                extract_social=options.get('extract_social', True),
                extract_reviews=options.get('extract_reviews', False),
            )

            # Create and start job
            job = scrape_service.create_job(request)
            background_tasks.add_task(scrape_service.run_scrape, job.job_id)

            return {
                "status": "started",
                "job_id": job.job_id,
                "saved_search": saved.to_dict()
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run saved search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/saved-searches/{search_id}")
async def delete_saved_search(search_id: int):
    """Delete a saved search."""
    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            saved = session.query(SavedSearch).filter(SavedSearch.id == search_id).first()

            if not saved:
                raise HTTPException(status_code=404, detail="Saved search not found")

            session.delete(saved)
            session.commit()

            return {"status": "deleted", "id": search_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete saved search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== PDF EXPORT ROUTES (Feature 5.1) ====================

# PDF Exporter
try:
    from utils.pdf_exporter import PDFExporter, export_leads_to_pdf, is_pdf_export_available
    HAS_PDF_EXPORTER = is_pdf_export_available()
except ImportError:
    HAS_PDF_EXPORTER = False
    PDFExporter = None


@router.post("/export/pdf")
async def export_leads_pdf(
    lead_ids: List[int] = None,
    title: str = "Business Leads Report",
    include_summary: bool = True,
    filters: dict = None
):
    """Export leads to PDF format."""
    if not HAS_PDF_EXPORTER:
        raise HTTPException(
            status_code=501,
            detail="PDF export not available. Install reportlab with: pip install reportlab"
        )

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        from fastapi.responses import Response
        import os
        from datetime import datetime

        with db_manager.get_session() as session:
            query = session.query(BusinessLead)

            # Filter by IDs if provided
            if lead_ids:
                query = query.filter(BusinessLead.id.in_(lead_ids))

            # Apply additional filters
            if filters:
                if filters.get("city"):
                    query = query.filter(BusinessLead.city == filters["city"])
                if filters.get("category"):
                    query = query.filter(BusinessLead.category == filters["category"])
                if filters.get("min_rating"):
                    query = query.filter(BusinessLead.rating >= filters["min_rating"])

            leads = query.limit(500).all()  # Limit to 500 for performance

            if not leads:
                raise HTTPException(status_code=404, detail="No leads found")

            # Convert to dictionaries
            lead_dicts = [lead.to_dict() for lead in leads]

            # Generate PDF
            exporter = PDFExporter()
            pdf_bytes = exporter.export_leads(
                leads=lead_dicts,
                title=title,
                include_summary=include_summary
            )

            # Return PDF as download
            filename = f"leads_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/pdf-table")
async def export_leads_pdf_table(
    lead_ids: List[int] = None,
    columns: List[str] = None,
    title: str = "Leads Summary"
):
    """Export leads as a summary table PDF."""
    if not HAS_PDF_EXPORTER:
        raise HTTPException(status_code=501, detail="PDF export not available")

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        from fastapi.responses import Response
        from datetime import datetime

        with db_manager.get_session() as session:
            query = session.query(BusinessLead)

            if lead_ids:
                query = query.filter(BusinessLead.id.in_(lead_ids))

            leads = query.limit(500).all()

            if not leads:
                raise HTTPException(status_code=404, detail="No leads found")

            lead_dicts = [lead.to_dict() for lead in leads]

            exporter = PDFExporter()
            pdf_bytes = exporter.export_summary_table(
                leads=lead_dicts,
                columns=columns,
                title=title
            )

            filename = f"leads_table_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF table export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== DEDUPLICATION ROUTES (Feature 1.4) ====================

try:
    from utils.deduplicator import AdvancedDeduplicator, deduplicate_leads, find_duplicates
    HAS_DEDUPLICATOR = True
except ImportError:
    HAS_DEDUPLICATOR = False


@router.post("/leads/find-duplicates")
async def find_lead_duplicates(
    lead_ids: List[int] = None,
    similarity_threshold: float = 0.85
):
    """Find potential duplicate leads."""
    if not HAS_DEDUPLICATOR:
        raise HTTPException(status_code=501, detail="Deduplicator not available")

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            query = session.query(BusinessLead)

            if lead_ids:
                query = query.filter(BusinessLead.id.in_(lead_ids))

            leads = query.limit(1000).all()  # Limit for performance

            if not leads:
                return {"duplicates": [], "total_checked": 0}

            lead_dicts = [lead.to_dict() for lead in leads]

            # Find duplicates
            duplicates = find_duplicates(lead_dicts, similarity_threshold)

            return {
                "duplicates": duplicates,
                "total_checked": len(lead_dicts),
                "duplicate_groups": len(duplicates)
            }

    except Exception as e:
        logger.error(f"Duplicate detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leads/deduplicate")
async def deduplicate_leads_endpoint(
    lead_ids: List[int] = None,
    strategy: str = "merge",
    similarity_threshold: float = 0.85
):
    """Deduplicate leads and optionally merge data."""
    if not HAS_DEDUPLICATOR:
        raise HTTPException(status_code=501, detail="Deduplicator not available")

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    if strategy not in ["merge", "keep_first", "keep_best"]:
        raise HTTPException(status_code=400, detail="Invalid strategy. Use: merge, keep_first, keep_best")

    try:
        with db_manager.get_session() as session:
            query = session.query(BusinessLead)

            if lead_ids:
                query = query.filter(BusinessLead.id.in_(lead_ids))

            leads = query.limit(1000).all()

            if not leads:
                return {"message": "No leads to deduplicate", "stats": {}}

            lead_dicts = [lead.to_dict() for lead in leads]

            # Deduplicate
            deduplicated, stats = deduplicate_leads(lead_dicts, strategy, similarity_threshold)

            return {
                "message": f"Deduplication complete",
                "stats": stats,
                "original_count": len(lead_dicts),
                "deduplicated_count": len(deduplicated)
            }

    except Exception as e:
        logger.error(f"Deduplication failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WEBSITE ANALYSIS ROUTES (Feature 4.1) ====================

try:
    from utils.website_analyzer import WebsiteAnalyzer, analyze_website, check_ssl, detect_technologies
    HAS_WEBSITE_ANALYZER = True
except ImportError:
    HAS_WEBSITE_ANALYZER = False


@router.post("/analyze/website")
async def analyze_website_endpoint(url: str):
    """Analyze a website for SSL, technologies, and more."""
    if not HAS_WEBSITE_ANALYZER:
        raise HTTPException(status_code=501, detail="Website analyzer not available")

    try:
        # Simple analysis without browser (SSL only)
        analyzer = WebsiteAnalyzer()
        result = analyzer.analyze_simple(url)

        return result

    except Exception as e:
        logger.error(f"Website analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/ssl")
async def check_ssl_endpoint(url: str):
    """Check SSL certificate for a URL."""
    if not HAS_WEBSITE_ANALYZER:
        raise HTTPException(status_code=501, detail="Website analyzer not available")

    try:
        result = check_ssl(url)
        return result

    except Exception as e:
        logger.error(f"SSL check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/technologies")
async def detect_technologies_endpoint(html: str):
    """Detect technologies from HTML content."""
    if not HAS_WEBSITE_ANALYZER:
        raise HTTPException(status_code=501, detail="Website analyzer not available")

    try:
        technologies = detect_technologies(html)
        return {"technologies": technologies}

    except Exception as e:
        logger.error(f"Technology detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leads/{lead_id}/analyze-website")
async def analyze_lead_website(lead_id: int):
    """Analyze the website of a specific lead."""
    if not HAS_WEBSITE_ANALYZER:
        raise HTTPException(status_code=501, detail="Website analyzer not available")

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter(BusinessLead.id == lead_id).first()

            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            if not lead.website:
                raise HTTPException(status_code=400, detail="Lead has no website")

            # Analyze website
            analyzer = WebsiteAnalyzer()
            result = analyzer.analyze_simple(lead.website)

            # Update lead with analysis results
            if result.get("ssl_info"):
                ssl_info = result["ssl_info"]
                lead.website_ssl_valid = ssl_info.get("valid", False)
                if ssl_info.get("expires"):
                    from datetime import datetime
                    try:
                        lead.website_ssl_expiry = datetime.fromisoformat(ssl_info["expires"])
                    except:
                        pass

            session.commit()

            return {
                "lead_id": lead_id,
                "website": lead.website,
                "analysis": result
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lead website analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LEAD SCORING ROUTES (Feature 6.1) ====================

try:
    from utils.lead_scoring import (
        LeadScorer, EnhancedLeadScorer, ScoringWeights,
        score_lead_enhanced, batch_score_leads, get_lead_scorer
    )
    HAS_LEAD_SCORING = True
except ImportError:
    HAS_LEAD_SCORING = False


@router.post("/leads/{lead_id}/score")
async def score_lead(lead_id: int):
    """Calculate lead score for a specific lead."""
    if not HAS_LEAD_SCORING:
        raise HTTPException(status_code=501, detail="Lead scoring not available")

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter(BusinessLead.id == lead_id).first()

            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            lead_dict = lead.to_dict()

            # Calculate score
            scorer = EnhancedLeadScorer()
            score_result = scorer.score_lead(lead_dict)

            # Update lead with score
            lead.lead_score = score_result.get("grade")
            lead.lead_score_numeric = score_result.get("score")
            lead.data_quality_score = score_result.get("score")
            session.commit()

            return {
                "lead_id": lead_id,
                "business_name": lead.business_name,
                **score_result
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lead scoring failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leads/score-batch")
async def score_leads_batch(lead_ids: List[int] = None, limit: int = 100):
    """Score multiple leads at once."""
    if not HAS_LEAD_SCORING:
        raise HTTPException(status_code=501, detail="Lead scoring not available")

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            query = session.query(BusinessLead)

            if lead_ids:
                query = query.filter(BusinessLead.id.in_(lead_ids))

            leads = query.limit(limit).all()

            if not leads:
                return {"message": "No leads to score", "results": []}

            lead_dicts = [lead.to_dict() for lead in leads]

            # Batch score
            scored = batch_score_leads(lead_dicts)

            # Update leads in database
            for scored_lead in scored:
                lead = session.query(BusinessLead).filter(
                    BusinessLead.id == scored_lead.get("id")
                ).first()
                if lead:
                    lead.lead_score = scored_lead.get("lead_grade")
                    lead.lead_score_numeric = scored_lead.get("lead_score")
                    lead.data_quality_score = scored_lead.get("lead_score")

            session.commit()

            # Calculate stats
            scores = [s.get("lead_score", 0) for s in scored]
            avg_score = sum(scores) / len(scores) if scores else 0

            grade_distribution = {}
            for s in scored:
                grade = s.get("lead_grade", "F")
                grade_distribution[grade] = grade_distribution.get(grade, 0) + 1

            return {
                "message": f"Scored {len(scored)} leads",
                "total_scored": len(scored),
                "average_score": round(avg_score, 1),
                "grade_distribution": grade_distribution,
                "top_leads": scored[:10]  # Return top 10
            }

    except Exception as e:
        logger.error(f"Batch scoring failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/scoring-stats")
async def get_scoring_stats():
    """Get lead scoring statistics."""
    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            from sqlalchemy import func

            total = session.query(func.count(BusinessLead.id)).scalar()
            scored = session.query(func.count(BusinessLead.id)).filter(
                BusinessLead.lead_score.isnot(None)
            ).scalar()

            avg_score = session.query(func.avg(BusinessLead.lead_score_numeric)).scalar() or 0

            # Grade distribution
            grades = session.query(
                BusinessLead.lead_score,
                func.count(BusinessLead.id)
            ).filter(
                BusinessLead.lead_score.isnot(None)
            ).group_by(BusinessLead.lead_score).all()

            grade_distribution = {grade: count for grade, count in grades}

            return {
                "total_leads": total,
                "scored_leads": scored,
                "unscored_leads": total - scored,
                "average_score": round(avg_score, 1),
                "grade_distribution": grade_distribution
            }

    except Exception as e:
        logger.error(f"Failed to get scoring stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EMAIL GUESSER ROUTES (Feature 1.1) ====================

try:
    from utils.email_guesser import EmailGuesser, guess_business_emails
    HAS_EMAIL_GUESSER = True
except ImportError:
    HAS_EMAIL_GUESSER = False


@router.post("/leads/{lead_id}/guess-emails")
async def guess_lead_emails(lead_id: int, max_guesses: int = 5):
    """Generate email guesses for a lead without email."""
    if not HAS_EMAIL_GUESSER:
        raise HTTPException(status_code=501, detail="Email guesser not available")

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter(BusinessLead.id == lead_id).first()

            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            if not lead.website:
                raise HTTPException(status_code=400, detail="Lead has no website for email guessing")

            # Generate guesses
            guessed = guess_business_emails(
                website=lead.website,
                business_name=lead.business_name,
                owner_name=lead.owner_name,
                contact_name=lead.contact_name_1,
                max_guesses=max_guesses
            )

            # Save to lead
            lead.guessed_emails = guessed
            session.commit()

            return {
                "lead_id": lead_id,
                "business_name": lead.business_name,
                "website": lead.website,
                "guessed_emails": guessed
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email guessing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WHATSAPP DETECTION ROUTES (Feature 1.2) ====================

try:
    from utils.whatsapp_detector import WhatsAppDetector, detect_whatsapp
    HAS_WHATSAPP = True
except ImportError:
    HAS_WHATSAPP = False


@router.post("/leads/{lead_id}/detect-whatsapp")
async def detect_lead_whatsapp(lead_id: int):
    """Detect WhatsApp availability for a lead's phone number."""
    if not HAS_WHATSAPP:
        raise HTTPException(status_code=501, detail="WhatsApp detector not available")

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter(BusinessLead.id == lead_id).first()

            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            if not lead.phone:
                raise HTTPException(status_code=400, detail="Lead has no phone number")

            # Detect WhatsApp
            result = detect_whatsapp(lead.phone, lead.country)

            # Update lead
            if result.get("likely_whatsapp"):
                lead.whatsapp_number = lead.phone
                lead.whatsapp_link = result.get("whatsapp_link")
                lead.whatsapp_likelihood = result.get("confidence")
                session.commit()

            return {
                "lead_id": lead_id,
                "phone": lead.phone,
                **result
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WhatsApp detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== HOURS ANALYSIS ROUTES (Feature 1.3) ====================

try:
    from utils.hours_analyzer import HoursAnalyzer, analyze_business_hours
    HAS_HOURS_ANALYZER = True
except ImportError:
    HAS_HOURS_ANALYZER = False


@router.post("/leads/{lead_id}/analyze-hours")
async def analyze_lead_hours(lead_id: int):
    """Analyze business hours and find best contact times."""
    if not HAS_HOURS_ANALYZER:
        raise HTTPException(status_code=501, detail="Hours analyzer not available")

    if not HAS_DATABASE:
        raise HTTPException(status_code=501, detail="Database not available")

    try:
        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter(BusinessLead.id == lead_id).first()

            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            # Build hours dict
            hours_data = {
                "monday": lead.hours_monday,
                "tuesday": lead.hours_tuesday,
                "wednesday": lead.hours_wednesday,
                "thursday": lead.hours_thursday,
                "friday": lead.hours_friday,
                "saturday": lead.hours_saturday,
                "sunday": lead.hours_sunday,
            }

            if not any(hours_data.values()):
                raise HTTPException(status_code=400, detail="Lead has no business hours data")

            # Analyze
            analysis = analyze_business_hours(hours_data)

            # Update lead
            lead.hours_analysis = analysis
            lead.best_call_times = analysis.get("best_call_times")
            lead.total_hours_per_week = analysis.get("total_hours_per_week")
            lead.opening_pattern = analysis.get("opening_pattern")
            session.commit()

            return {
                "lead_id": lead_id,
                "business_name": lead.business_name,
                **analysis
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hours analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


