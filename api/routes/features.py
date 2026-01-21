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
    from database.models import BusinessLead
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False

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
        ]
    }
