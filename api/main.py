"""FastAPI backend for Google Maps Scraper Dashboard."""
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import asyncio
import subprocess
import sys
import json
import os

from database import db_manager, BusinessLead, ScrapeJob
from utils import DataExporter
from loguru import logger

# Ensure required directories exist
EXPORTS_DIR = Path("exports")
LOGS_DIR = Path("logs")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize FastAPI app
app = FastAPI(
    title="MapLeads Pro API",
    description="Google Maps Lead Scraper Dashboard API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database connection."""
    db_manager.initialize()
    db_manager.create_tables()
    logger.info("FastAPI server started")

# Pydantic models for requests/responses
class ScrapeRequest(BaseModel):
    search_query: str
    location: Optional[str] = None
    max_results: int = 100
    use_proxies: bool = False
    extract_emails: bool = False
    headless: bool = True

class ExportRequest(BaseModel):
    format: str = "csv"  # csv, json, cold_calling, excel
    filters: Optional[dict] = None
    filename: Optional[str] = None

class BulkScrapeRequest(BaseModel):
    search_query: str
    locations: List[str]
    max_results_per_location: int = 50
    delay_between_locations: int = 60
    extract_emails: bool = False

class JobResponse(BaseModel):
    id: int
    search_query: str
    location: Optional[str]
    max_results: int
    status: str
    leads_scraped: int
    leads_target: int
    error_count: int
    last_error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

class LeadResponse(BaseModel):
    id: int
    business_name: str
    full_address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    pin_code: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    category: Optional[str]
    email: Optional[str]
    rating: Optional[float]
    review_count: Optional[int]
    data_quality_score: int
    scraped_at: datetime

class StatsResponse(BaseModel):
    total_leads: int
    leads_with_phone: int
    leads_with_website: int
    leads_with_email: int
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    average_quality_score: float

# WebSocket manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        try:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")
        except ValueError:
            # Connection was already removed
            pass

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")

manager = ConnectionManager()

# Background scraping tasks
active_processes = {}

async def run_scrape_job(job_id: int, request: ScrapeRequest):
    """Run scraping job in a separate subprocess to avoid asyncio/greenlet conflicts."""
    process = None
    try:
        logger.info(f"Starting background scrape job {job_id} in subprocess")

        # Get the path to the scraper worker script
        worker_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scraper', 'scraper_worker.py')

        # Run scraper in a separate process
        process = subprocess.Popen(
            [
                sys.executable,
                worker_script,
                str(job_id),
                request.search_query,
                request.location or '',
                str(request.max_results),
                str(request.extract_emails).lower()
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )

        active_processes[job_id] = process

        # Wait for process to complete in a non-blocking way
        def wait_for_process():
            stdout, stderr = process.communicate()
            return process.returncode, stdout, stderr

        loop = asyncio.get_event_loop()
        returncode, stdout, stderr = await loop.run_in_executor(None, wait_for_process)

        # Log output
        if stdout:
            for line in stdout.strip().split('\n'):
                if line:
                    logger.info(f"[Job {job_id}] {line}")
        if stderr:
            for line in stderr.strip().split('\n'):
                if line and 'INFO' not in line and 'SUCCESS' not in line:
                    logger.warning(f"[Job {job_id}] {line}")

        if returncode == 0:
            # Get updated job status
            with db_manager.get_session() as session:
                job = session.query(ScrapeJob).filter_by(id=job_id).first()
                results_count = job.leads_scraped if job else 0

            # Broadcast completion
            await manager.broadcast({
                'type': 'job_completed',
                'job_id': job_id,
                'results_count': results_count
            })

            logger.success(f"Background job {job_id} completed: {results_count} results")
        else:
            raise Exception(f"Subprocess exited with code {returncode}")

    except Exception as e:
        logger.error(f"Background job {job_id} failed: {e}")

        # Update job status
        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter_by(id=job_id).first()
            if job and job.status != 'completed':
                job.status = 'failed'
                job.last_error = str(e)
                job.error_count += 1
                session.commit()

        # Broadcast failure
        await manager.broadcast({
            'type': 'job_failed',
            'job_id': job_id,
            'error': str(e)
        })

    finally:
        # Cleanup
        if job_id in active_processes:
            del active_processes[job_id]

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MapLeads Pro API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """Get database statistics."""
    try:
        with db_manager.get_session() as session:
            from sqlalchemy import func

            total_leads = session.query(BusinessLead).count()
            leads_with_phone = session.query(BusinessLead).filter(BusinessLead.phone.isnot(None)).count()
            leads_with_website = session.query(BusinessLead).filter(BusinessLead.website.isnot(None)).count()
            leads_with_email = session.query(BusinessLead).filter(BusinessLead.email.isnot(None)).count()

            total_jobs = session.query(ScrapeJob).count()
            completed_jobs = session.query(ScrapeJob).filter(ScrapeJob.status == 'completed').count()
            failed_jobs = session.query(ScrapeJob).filter(ScrapeJob.status == 'failed').count()

            avg_quality = session.query(func.avg(BusinessLead.data_quality_score)).scalar() or 0

            return StatsResponse(
                total_leads=total_leads,
                leads_with_phone=leads_with_phone,
                leads_with_website=leads_with_website,
                leads_with_email=leads_with_email,
                total_jobs=total_jobs,
                completed_jobs=completed_jobs,
                failed_jobs=failed_jobs,
                average_quality_score=round(avg_quality, 1)
            )

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs", response_model=List[JobResponse])
async def get_jobs(limit: int = 50, status: Optional[str] = None):
    """Get list of scrape jobs."""
    try:
        with db_manager.get_session() as session:
            query = session.query(ScrapeJob).order_by(ScrapeJob.created_at.desc())

            if status:
                query = query.filter(ScrapeJob.status == status)

            jobs = query.limit(limit).all()

            return [
                JobResponse(
                    id=job.id,
                    search_query=job.search_query,
                    location=job.location,
                    max_results=job.max_results,
                    status=job.status,
                    leads_scraped=job.leads_scraped,
                    leads_target=job.leads_target,
                    error_count=job.error_count,
                    last_error=job.last_error,
                    started_at=job.started_at,
                    completed_at=job.completed_at,
                    created_at=job.created_at
                )
                for job in jobs
            ]

    except Exception as e:
        logger.error(f"Error getting jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int):
    """Get specific job details."""
    try:
        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter_by(id=job_id).first()

            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            return JobResponse(
                id=job.id,
                search_query=job.search_query,
                location=job.location,
                max_results=job.max_results,
                status=job.status,
                leads_scraped=job.leads_scraped,
                leads_target=job.leads_target,
                error_count=job.error_count,
                last_error=job.last_error,
                started_at=job.started_at,
                completed_at=job.completed_at,
                created_at=job.created_at
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scrape", response_model=JobResponse)
async def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Start a new scraping job."""
    try:
        # Create job in database
        with db_manager.get_session() as session:
            job = ScrapeJob(
                search_query=request.search_query,
                location=request.location,
                max_results=request.max_results,
                leads_target=request.max_results,
                status='pending',
                started_at=datetime.now()
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            job_id = job.id

        # Start background task
        background_tasks.add_task(run_scrape_job, job_id, request)

        # Broadcast job started
        await manager.broadcast({
            'type': 'job_started',
            'job_id': job_id,
            'search_query': request.search_query
        })

        # Return job info
        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter_by(id=job_id).first()
            return JobResponse(
                id=job.id,
                search_query=job.search_query,
                location=job.location,
                max_results=job.max_results,
                status=job.status,
                leads_scraped=job.leads_scraped,
                leads_target=job.leads_target,
                error_count=job.error_count,
                last_error=job.last_error,
                started_at=job.started_at,
                completed_at=job.completed_at,
                created_at=job.created_at
            )

    except Exception as e:
        logger.error(f"Error starting scrape: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class PaginatedLeadsResponse(BaseModel):
    leads: List[LeadResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

def build_leads_query(session, city, state, pin_code, has_phone, has_website, has_email,
                      category, search_query, min_quality, max_quality, min_rating,
                      max_rating, min_reviews, has_facebook, has_instagram, has_twitter,
                      has_linkedin, price_level, search):
    """Build filtered query for leads."""
    query = session.query(BusinessLead).order_by(BusinessLead.scraped_at.desc())

    # Location filters
    if city:
        query = query.filter(BusinessLead.city.ilike(f"%{city}%"))
    if state:
        query = query.filter(BusinessLead.state.ilike(f"%{state}%"))
    if pin_code:
        query = query.filter(BusinessLead.pin_code == pin_code)

    # Contact filters
    if has_phone:
        query = query.filter(BusinessLead.phone.isnot(None))
    if has_website:
        query = query.filter(BusinessLead.website.isnot(None))
    if has_email:
        query = query.filter(BusinessLead.email.isnot(None))

    # Category filters
    if category:
        query = query.filter(BusinessLead.category.ilike(f"%{category}%"))
    if search_query:
        query = query.filter(BusinessLead.search_query.ilike(f"%{search_query}%"))

    # Quality filters
    if min_quality > 0:
        query = query.filter(BusinessLead.data_quality_score >= min_quality)
    if max_quality < 100:
        query = query.filter(BusinessLead.data_quality_score <= max_quality)
    if min_rating:
        query = query.filter(BusinessLead.rating >= min_rating)
    if max_rating:
        query = query.filter(BusinessLead.rating <= max_rating)
    if min_reviews:
        query = query.filter(BusinessLead.review_count >= min_reviews)

    # Social media filters
    if has_facebook:
        query = query.filter(BusinessLead.social_facebook.isnot(None))
    if has_instagram:
        query = query.filter(BusinessLead.social_instagram.isnot(None))
    if has_twitter:
        query = query.filter(BusinessLead.social_twitter.isnot(None))
    if has_linkedin:
        query = query.filter(BusinessLead.social_linkedin.isnot(None))

    # Price level
    if price_level:
        query = query.filter(BusinessLead.price_level == price_level)

    # General search (searches across multiple fields)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (BusinessLead.business_name.ilike(search_filter)) |
            (BusinessLead.city.ilike(search_filter)) |
            (BusinessLead.category.ilike(search_filter)) |
            (BusinessLead.full_address.ilike(search_filter))
        )

    return query

@app.get("/api/leads", response_model=List[LeadResponse])
async def get_leads(
    limit: int = 1000,
    offset: int = 0,
    # Location filters
    city: Optional[str] = None,
    state: Optional[str] = None,
    pin_code: Optional[str] = None,
    # Contact filters
    has_phone: bool = False,
    has_website: bool = False,
    has_email: bool = False,
    # Category filters
    category: Optional[str] = None,
    search_query: Optional[str] = None,
    # Quality filters
    min_quality: int = 0,
    max_quality: int = 100,
    min_rating: Optional[float] = None,
    max_rating: Optional[float] = None,
    min_reviews: Optional[int] = None,
    # Social media filters
    has_facebook: bool = False,
    has_instagram: bool = False,
    has_twitter: bool = False,
    has_linkedin: bool = False,
    # Price level
    price_level: Optional[str] = None,
    # General search
    search: Optional[str] = None
):
    """Get list of leads with comprehensive filters."""
    try:
        with db_manager.get_session() as session:
            query = build_leads_query(
                session, city, state, pin_code, has_phone, has_website, has_email,
                category, search_query, min_quality, max_quality, min_rating,
                max_rating, min_reviews, has_facebook, has_instagram, has_twitter,
                has_linkedin, price_level, search
            )

            leads = query.limit(limit).offset(offset).all()

            return [
                LeadResponse(
                    id=lead.id,
                    business_name=lead.business_name,
                    full_address=lead.full_address,
                    city=lead.city,
                    state=lead.state,
                    pin_code=lead.pin_code,
                    phone=lead.phone,
                    website=lead.website,
                    category=lead.category,
                    email=lead.email,
                    rating=lead.rating,
                    review_count=lead.review_count,
                    data_quality_score=lead.data_quality_score,
                    scraped_at=lead.scraped_at
                )
                for lead in leads
            ]

    except Exception as e:
        logger.error(f"Error getting leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads/paginated", response_model=PaginatedLeadsResponse)
async def get_leads_paginated(
    page: int = 1,
    per_page: int = 50,
    # Location filters
    city: Optional[str] = None,
    state: Optional[str] = None,
    pin_code: Optional[str] = None,
    # Contact filters
    has_phone: bool = False,
    has_website: bool = False,
    has_email: bool = False,
    # Category filters
    category: Optional[str] = None,
    search_query: Optional[str] = None,
    # Quality filters
    min_quality: int = 0,
    max_quality: int = 100,
    min_rating: Optional[float] = None,
    max_rating: Optional[float] = None,
    min_reviews: Optional[int] = None,
    # Social media filters
    has_facebook: bool = False,
    has_instagram: bool = False,
    has_twitter: bool = False,
    has_linkedin: bool = False,
    # Price level
    price_level: Optional[str] = None,
    # General search
    search: Optional[str] = None
):
    """Get paginated list of leads with total count for server-side pagination."""
    try:
        # Validate pagination params
        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 50
        if per_page > 500:
            per_page = 500  # Max 500 per page

        offset = (page - 1) * per_page

        with db_manager.get_session() as session:
            query = build_leads_query(
                session, city, state, pin_code, has_phone, has_website, has_email,
                category, search_query, min_quality, max_quality, min_rating,
                max_rating, min_reviews, has_facebook, has_instagram, has_twitter,
                has_linkedin, price_level, search
            )

            # Get total count
            total = query.count()

            # Get paginated results
            leads = query.limit(per_page).offset(offset).all()

            # Calculate total pages
            total_pages = (total + per_page - 1) // per_page if total > 0 else 1

            return PaginatedLeadsResponse(
                leads=[
                    LeadResponse(
                        id=lead.id,
                        business_name=lead.business_name,
                        full_address=lead.full_address,
                        city=lead.city,
                        state=lead.state,
                        pin_code=lead.pin_code,
                        phone=lead.phone,
                        website=lead.website,
                        category=lead.category,
                        email=lead.email,
                        rating=lead.rating,
                        review_count=lead.review_count,
                        data_quality_score=lead.data_quality_score,
                        scraped_at=lead.scraped_at
                    )
                    for lead in leads
                ],
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages
            )

    except Exception as e:
        logger.error(f"Error getting paginated leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export")
async def export_leads(request: ExportRequest):
    """Export leads to file."""
    try:
        exporter = DataExporter()

        # Get count of leads being exported
        with db_manager.get_session() as session:
            query = session.query(BusinessLead)

            # Apply same filters
            if request.filters:
                if request.filters.get('has_phone'):
                    query = query.filter(BusinessLead.phone.isnot(None))
                if request.filters.get('has_website'):
                    query = query.filter(BusinessLead.website.isnot(None))
                if request.filters.get('has_email'):
                    query = query.filter(BusinessLead.email.isnot(None))
                if request.filters.get('city'):
                    query = query.filter(BusinessLead.city == request.filters['city'])
                if request.filters.get('min_quality_score'):
                    query = query.filter(BusinessLead.data_quality_score >= request.filters['min_quality_score'])

            count = query.count()

        if request.format == 'csv':
            filepath = exporter.export_to_csv(filters=request.filters, filename=request.filename)
        elif request.format == 'json':
            filepath = exporter.export_to_json(filters=request.filters, filename=request.filename)
        elif request.format == 'cold_calling':
            filepath = exporter.export_cold_calling_format(filters=request.filters, filename=request.filename)
        elif request.format == 'excel':
            filepath = exporter.export_to_excel(filters=request.filters, filename=request.filename)
        else:
            raise HTTPException(status_code=400, detail="Invalid format. Use: csv, json, cold_calling, or excel")

        if not filepath:
            raise HTTPException(status_code=404, detail="No data to export")

        # Get filename for response
        export_filename = Path(filepath).name

        return {
            "filepath": filepath,
            "filename": export_filename,
            "status": "success",
            "count": count,
            "download_url": f"/api/export/download/{export_filename}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_bulk_scrape_sequential(job_configs: List[dict], delay_between: int):
    """Run bulk scrape jobs sequentially with delays between them."""
    for i, config in enumerate(job_configs):
        # Add delay between jobs (except for the first one)
        if i > 0 and delay_between > 0:
            logger.info(f"Waiting {delay_between}s before starting job {config['job_id']}...")
            await asyncio.sleep(delay_between)

        # Run the scrape job
        await run_scrape_job(config['job_id'], config['request'])

@app.post("/api/bulk-scrape")
async def start_bulk_scrape(request: BulkScrapeRequest, background_tasks: BackgroundTasks):
    """Start bulk scraping for multiple locations."""
    try:
        job_ids = []
        job_configs = []

        for location in request.locations:
            # Create a job for each location
            with db_manager.get_session() as session:
                job = ScrapeJob(
                    search_query=request.search_query,
                    location=location,
                    max_results=request.max_results_per_location,
                    leads_target=request.max_results_per_location,
                    status='pending',
                    started_at=datetime.now()
                )
                session.add(job)
                session.commit()
                session.refresh(job)
                job_ids.append(job.id)

                # Store config for background processing
                job_configs.append({
                    'job_id': job.id,
                    'request': ScrapeRequest(
                        search_query=request.search_query,
                        location=location,
                        max_results=request.max_results_per_location,
                        use_proxies=False
                    )
                })

        # Start all jobs in a single background task that handles delays
        background_tasks.add_task(
            run_bulk_scrape_sequential,
            job_configs,
            request.delay_between_locations
        )

        return {
            "status": "success",
            "message": f"Started {len(job_ids)} scraping jobs",
            "job_ids": job_ids
        }

    except Exception as e:
        logger.error(f"Error starting bulk scrape: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics")
async def get_analytics():
    """Get analytics data for dashboard."""
    try:
        with db_manager.get_session() as session:
            from sqlalchemy import func
            from datetime import datetime, timedelta

            # Top categories
            top_categories = session.query(
                BusinessLead.category,
                func.count(BusinessLead.id).label('count')
            ).filter(
                BusinessLead.category.isnot(None)
            ).group_by(
                BusinessLead.category
            ).order_by(
                func.count(BusinessLead.id).desc()
            ).limit(10).all()

            # Quality distribution
            quality_ranges = [
                session.query(func.count(BusinessLead.id)).filter(
                    BusinessLead.data_quality_score >= 80
                ).scalar() or 0,
                session.query(func.count(BusinessLead.id)).filter(
                    BusinessLead.data_quality_score >= 60,
                    BusinessLead.data_quality_score < 80
                ).scalar() or 0,
                session.query(func.count(BusinessLead.id)).filter(
                    BusinessLead.data_quality_score >= 40,
                    BusinessLead.data_quality_score < 60
                ).scalar() or 0,
                session.query(func.count(BusinessLead.id)).filter(
                    BusinessLead.data_quality_score < 40
                ).scalar() or 0
            ]

            # Activity timeline (last 7 days)
            activity_timeline = []
            for i in range(6, -1, -1):
                date = datetime.now().date() - timedelta(days=i)
                count = session.query(func.count(BusinessLead.id)).filter(
                    func.date(BusinessLead.scraped_at) == date
                ).scalar() or 0
                activity_timeline.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'count': count
                })

            return {
                "top_categories": [
                    {"category": cat, "count": count}
                    for cat, count in top_categories
                ],
                "quality_distribution": quality_ranges,
                "activity_timeline": activity_timeline
            }

    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/leads/{lead_id}")
async def delete_lead(lead_id: int):
    """Delete a specific lead."""
    try:
        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter_by(id=lead_id).first()

            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            session.delete(lead)
            session.commit()

            return {"status": "success", "message": "Lead deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== PHASE 1 & 2 NEW ENDPOINTS ====================

@app.get("/api/export/download/{filename}")
async def download_export(filename: str):
    """Download an exported file."""
    try:
        # Security: Only allow files from exports directory
        filepath = EXPORTS_DIR / filename

        # Prevent directory traversal attacks
        if not filepath.resolve().is_relative_to(EXPORTS_DIR.resolve()):
            raise HTTPException(status_code=403, detail="Access denied")

        if not filepath.exists():
            raise HTTPException(status_code=404, detail="File not found")

        # Determine media type based on extension
        media_type = "text/csv" if filename.endswith(".csv") else "application/json"

        return FileResponse(
            path=str(filepath),
            filename=filename,
            media_type=media_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/files")
async def list_export_files():
    """List all exported files available for download."""
    try:
        files = []
        for filepath in EXPORTS_DIR.glob("*"):
            if filepath.is_file():
                stat = filepath.stat()
                files.append({
                    "filename": filepath.name,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        # Sort by creation time, newest first
        files.sort(key=lambda x: x["created_at"], reverse=True)

        return {"files": files, "total": len(files)}

    except Exception as e:
        logger.error(f"Error listing export files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads/{lead_id}")
async def get_lead_details(lead_id: int):
    """Get detailed information for a specific lead."""
    try:
        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter_by(id=lead_id).first()

            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            return lead.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lead details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class LeadUpdateRequest(BaseModel):
    business_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    full_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pin_code: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None

@app.put("/api/leads/{lead_id}")
async def update_lead(lead_id: int, request: LeadUpdateRequest):
    """Update a specific lead."""
    try:
        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter_by(id=lead_id).first()

            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            # Update only provided fields
            update_data = request.dict(exclude_unset=True)
            for field, value in update_data.items():
                if value is not None and hasattr(lead, field):
                    setattr(lead, field, value)

            # Recalculate quality score
            lead.calculate_quality_score()

            session.commit()
            session.refresh(lead)

            return {"status": "success", "message": "Lead updated", "lead": lead.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: int, background_tasks: BackgroundTasks):
    """Retry a failed job."""
    try:
        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter_by(id=job_id).first()

            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            if job.status not in ['failed', 'completed']:
                raise HTTPException(status_code=400, detail="Can only retry failed or completed jobs")

            # Reset job status
            job.status = 'pending'
            job.leads_scraped = 0
            job.error_count = 0
            job.last_error = None
            job.started_at = datetime.now()
            job.completed_at = None
            session.commit()

            # Create scrape request
            scrape_req = ScrapeRequest(
                search_query=job.search_query,
                location=job.location,
                max_results=job.max_results,
                use_proxies=False
            )

            # Start background task
            background_tasks.add_task(run_scrape_job, job_id, scrape_req)

            return {"status": "success", "message": f"Job {job_id} queued for retry"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/jobs/{job_id}/pause")
async def pause_job(job_id: int):
    """Pause a running job."""
    try:
        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter_by(id=job_id).first()

            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            if job.status != 'running':
                raise HTTPException(status_code=400, detail="Can only pause running jobs")

            job.status = 'paused'
            session.commit()

            # Also try to stop the active scraper
            if job_id in active_scrapers:
                # Signal to stop (the scraper should check this)
                pass

            await manager.broadcast({
                'type': 'job_paused',
                'job_id': job_id
            })

            return {"status": "success", "message": f"Job {job_id} paused"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/jobs/{job_id}/resume")
async def resume_job(job_id: int, background_tasks: BackgroundTasks):
    """Resume a paused job."""
    try:
        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter_by(id=job_id).first()

            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            if job.status != 'paused':
                raise HTTPException(status_code=400, detail="Can only resume paused jobs")

            job.status = 'running'
            session.commit()

            # Create scrape request for remaining results
            remaining_results = job.max_results - job.leads_scraped
            scrape_req = ScrapeRequest(
                search_query=job.search_query,
                location=job.location,
                max_results=remaining_results,
                use_proxies=False
            )

            # Start background task
            background_tasks.add_task(run_scrape_job, job_id, scrape_req)

            await manager.broadcast({
                'type': 'job_resumed',
                'job_id': job_id
            })

            return {"status": "success", "message": f"Job {job_id} resumed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: int):
    """Delete a job."""
    try:
        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter_by(id=job_id).first()

            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            if job.status == 'running':
                raise HTTPException(status_code=400, detail="Cannot delete running job. Pause it first.")

            session.delete(job)
            session.commit()

            return {"status": "success", "message": f"Job {job_id} deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ExportSelectedRequest(BaseModel):
    lead_ids: List[int]
    format: str = "csv"
    filename: Optional[str] = None

@app.post("/api/export/selected")
async def export_selected_leads(request: ExportSelectedRequest):
    """Export specific leads by their IDs."""
    try:
        if not request.lead_ids:
            raise HTTPException(status_code=400, detail="No lead IDs provided")

        with db_manager.get_session() as session:
            leads = session.query(BusinessLead).filter(
                BusinessLead.id.in_(request.lead_ids)
            ).all()

            if not leads:
                raise HTTPException(status_code=404, detail="No leads found with provided IDs")

            # Convert to dictionaries
            data = [lead.to_dict() for lead in leads]

        exporter = DataExporter()

        if request.format == 'csv':
            filepath = exporter.export_to_csv(data=data, filename=request.filename)
        elif request.format == 'json':
            filepath = exporter.export_to_json(data=data, filename=request.filename)
        elif request.format == 'excel':
            filepath = exporter.export_to_excel(data=data, filename=request.filename)
        else:
            raise HTTPException(status_code=400, detail="Invalid format. Use: csv, json, or excel")

        if not filepath:
            raise HTTPException(status_code=500, detail="Export failed")

        # Return filename for download
        filename = Path(filepath).name

        return {
            "status": "success",
            "filepath": filepath,
            "filename": filename,
            "count": len(leads),
            "download_url": f"/api/export/download/{filename}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting selected leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== PHASE 3: SETTINGS ENDPOINTS ====================

class SettingsRequest(BaseModel):
    max_requests_per_hour: Optional[int] = None
    delay_between_requests_min: Optional[float] = None
    delay_between_requests_max: Optional[float] = None
    headless_mode: Optional[bool] = None
    auto_deduplicate: Optional[bool] = None

# In-memory settings store (in production, use database or config file)
app_settings = {
    "max_requests_per_hour": 100,
    "delay_between_requests_min": 3.0,
    "delay_between_requests_max": 8.0,
    "headless_mode": True,
    "auto_deduplicate": True
}

@app.get("/api/settings")
async def get_settings():
    """Get current application settings."""
    return {"settings": app_settings}

@app.post("/api/settings")
async def save_settings(request: SettingsRequest):
    """Save application settings."""
    try:
        update_data = request.dict(exclude_unset=True)

        for key, value in update_data.items():
            if value is not None and key in app_settings:
                app_settings[key] = value

        return {"status": "success", "message": "Settings saved", "settings": app_settings}

    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """System health check endpoint."""
    try:
        import psutil

        # Get system stats
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Check database connection
        db_status = "healthy"
        try:
            from sqlalchemy import text
            with db_manager.get_session() as session:
                session.execute(text("SELECT 1"))
        except Exception:
            db_status = "unhealthy"

        return {
            "status": "healthy",
            "database": db_status,
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2)
            },
            "active_scrapers": len(active_scrapers),
            "websocket_connections": len(manager.active_connections)
        }

    except ImportError:
        # psutil not installed
        return {
            "status": "healthy",
            "database": "unknown",
            "system": "psutil not installed",
            "active_scrapers": len(active_scrapers),
            "websocket_connections": len(manager.active_connections)
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e)
        }

# ==================== SMART FILTER PRESETS ====================

FILTER_PRESETS = {
    "high_quality": {
        "name": "High Quality Leads",
        "description": "Leads with quality score >= 80%",
        "filters": {"min_quality": 80}
    },
    "cold_call_ready": {
        "name": "Cold Call Ready",
        "description": "Leads with phone numbers and quality >= 60%",
        "filters": {"has_phone": True, "min_quality": 60}
    },
    "email_campaign": {
        "name": "Email Campaign Ready",
        "description": "Leads with email addresses",
        "filters": {"has_email": True}
    },
    "complete_contact": {
        "name": "Complete Contact Info",
        "description": "Leads with phone, email, and website",
        "filters": {"has_phone": True, "has_email": True, "has_website": True}
    },
    "social_media": {
        "name": "Has Social Media",
        "description": "Leads with at least one social media profile",
        "filters": {"has_facebook": True}  # Could be OR'd with other social
    },
    "top_rated": {
        "name": "Top Rated",
        "description": "Businesses with rating >= 4.0 and 50+ reviews",
        "filters": {"min_rating": 4.0, "min_reviews": 50}
    }
}

@app.get("/api/filter-presets")
async def get_filter_presets():
    """Get available filter presets."""
    return {"presets": FILTER_PRESETS}


# ==================== NEW FEATURE ENDPOINTS ====================

# Import new modules
try:
    from utils.google_sheets_exporter import get_sheets_exporter
    from utils.lead_scoring import get_lead_scorer
    from utils.email_verification import get_email_verifier
    from utils.notifications import get_notification_service
    from utils.crm_integrations import get_crm_manager
    from utils.airtable_notion_exporter import get_export_manager
    from scraper.scheduler import get_scheduler, ScheduledTask
    from config.settings import settings
    NEW_FEATURES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Some new features not available: {e}")
    NEW_FEATURES_AVAILABLE = False


# ==================== GOOGLE SHEETS EXPORT ====================

class GoogleSheetsExportRequest(BaseModel):
    spreadsheet_url: Optional[str] = None
    spreadsheet_name: Optional[str] = None
    sheet_name: str = "Leads"
    filters: Optional[dict] = None
    share_with: Optional[List[str]] = None

@app.post("/api/export/google-sheets")
async def export_to_google_sheets(request: GoogleSheetsExportRequest):
    """Export leads to Google Sheets."""
    try:
        sheets_exporter = get_sheets_exporter()

        # Authenticate (try service account first)
        if not sheets_exporter._authenticated:
            if not sheets_exporter.authenticate_service_account():
                return {"success": False, "error": "Google Sheets not authenticated. Please configure credentials."}

        result = sheets_exporter.export_to_sheets(
            spreadsheet_url=request.spreadsheet_url,
            spreadsheet_name=request.spreadsheet_name,
            sheet_name=request.sheet_name,
            filters=request.filters,
            share_with=request.share_with
        )

        return result

    except Exception as e:
        logger.error(f"Error exporting to Google Sheets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LEAD SCORING ====================

class LeadScoreRequest(BaseModel):
    lead_id: Optional[int] = None
    filters: Optional[dict] = None

@app.post("/api/leads/score")
async def score_leads(request: LeadScoreRequest):
    """Score leads using AI-powered algorithm."""
    try:
        scorer = get_lead_scorer()

        if request.lead_id:
            # Score single lead
            with db_manager.get_session() as session:
                lead = session.query(BusinessLead).filter_by(id=request.lead_id).first()
                if not lead:
                    raise HTTPException(status_code=404, detail="Lead not found")
                lead_dict = lead.to_dict()

            score_result = scorer.calculate_score(lead_dict)
            return {"success": True, "lead_id": request.lead_id, "score": score_result}
        else:
            # Batch score all leads
            result = scorer.score_and_save(filters=request.filters)
            return {"success": True, "results": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scoring leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads/{lead_id}/score")
async def get_lead_score(lead_id: int):
    """Get detailed score for a specific lead."""
    try:
        scorer = get_lead_scorer()

        with db_manager.get_session() as session:
            lead = session.query(BusinessLead).filter_by(id=lead_id).first()
            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")
            lead_dict = lead.to_dict()

        score_result = scorer.calculate_score(lead_dict)
        return {"success": True, "lead_id": lead_id, "score": score_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lead score: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EMAIL VERIFICATION ====================

class EmailVerifyRequest(BaseModel):
    email: Optional[str] = None
    lead_id: Optional[int] = None
    level: str = "domain"  # syntax, domain, smtp, api

@app.post("/api/verify/email")
async def verify_email(request: EmailVerifyRequest):
    """Verify an email address."""
    try:
        verifier = get_email_verifier()

        if request.email:
            result = await verifier.verify_email(request.email, request.level)
            return {"success": True, "verification": result}
        elif request.lead_id:
            with db_manager.get_session() as session:
                lead = session.query(BusinessLead).filter_by(id=request.lead_id).first()
                if not lead or not lead.email:
                    raise HTTPException(status_code=404, detail="Lead or email not found")
                email = lead.email

            result = await verifier.verify_email(email, request.level)
            return {"success": True, "lead_id": request.lead_id, "verification": result}
        else:
            raise HTTPException(status_code=400, detail="Provide email or lead_id")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying email: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/verify/batch")
async def verify_emails_batch(filters: Optional[dict] = None):
    """Verify emails for all leads matching filters."""
    try:
        verifier = get_email_verifier()
        result = await verifier.verify_leads(filters=filters, level="domain")
        return {"success": True, "results": result}

    except Exception as e:
        logger.error(f"Error batch verifying emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SCHEDULED SCRAPING ====================

class ScheduleTaskRequest(BaseModel):
    task_id: str
    search_query: str
    location: Optional[str] = None
    max_results: int = 100
    schedule_type: str = "interval"  # interval, cron, once
    interval_hours: int = 24
    cron_expression: Optional[str] = None
    run_at: Optional[datetime] = None
    notify_on_complete: bool = True

@app.post("/api/scheduler/tasks")
async def create_scheduled_task(request: ScheduleTaskRequest):
    """Create a new scheduled scraping task."""
    try:
        scheduler = get_scheduler()

        if not scheduler._running:
            scheduler.start()

        task = ScheduledTask(
            task_id=request.task_id,
            search_query=request.search_query,
            location=request.location,
            max_results=request.max_results,
            schedule_type=request.schedule_type,
            interval_hours=request.interval_hours,
            cron_expression=request.cron_expression,
            run_at=request.run_at,
            notify_on_complete=request.notify_on_complete
        )

        success = scheduler.add_task(task)

        if success:
            return {"success": True, "task": task.to_dict()}
        else:
            raise HTTPException(status_code=400, detail="Failed to add task")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating scheduled task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scheduler/tasks")
async def list_scheduled_tasks():
    """List all scheduled tasks."""
    try:
        scheduler = get_scheduler()
        tasks = scheduler.list_tasks()
        status = scheduler.get_status()
        return {"success": True, "tasks": tasks, "scheduler_status": status}

    except Exception as e:
        logger.error(f"Error listing scheduled tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/scheduler/tasks/{task_id}")
async def delete_scheduled_task(task_id: str):
    """Delete a scheduled task."""
    try:
        scheduler = get_scheduler()
        success = scheduler.remove_task(task_id)

        if success:
            return {"success": True, "message": f"Task {task_id} removed"}
        else:
            raise HTTPException(status_code=404, detail="Task not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting scheduled task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scheduler/tasks/{task_id}/run")
async def run_task_now(task_id: str):
    """Run a scheduled task immediately."""
    try:
        scheduler = get_scheduler()
        success = scheduler.run_task_now(task_id)

        if success:
            return {"success": True, "message": f"Task {task_id} triggered"}
        else:
            raise HTTPException(status_code=404, detail="Task not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CRM INTEGRATIONS ====================

class CRMPushRequest(BaseModel):
    crm: str  # hubspot, salesforce
    filters: Optional[dict] = None
    as_type: str = "contacts"  # contacts, companies, leads

@app.post("/api/crm/push")
async def push_to_crm(request: CRMPushRequest):
    """Push leads to CRM."""
    try:
        crm_manager = get_crm_manager()

        if request.crm == "hubspot":
            if not crm_manager.hubspot:
                crm_manager.configure_hubspot(settings.hubspot_access_token)

            if request.as_type == "contacts":
                result = await crm_manager.hubspot.push_leads_as_contacts(filters=request.filters)
            else:
                result = await crm_manager.hubspot.push_leads_as_companies(filters=request.filters)

        elif request.crm == "salesforce":
            if not crm_manager.salesforce:
                crm_manager.configure_salesforce(
                    settings.salesforce_username,
                    settings.salesforce_password,
                    settings.salesforce_security_token
                )

            result = await crm_manager.salesforce.push_as_leads(filters=request.filters)

        else:
            raise HTTPException(status_code=400, detail="Invalid CRM. Use: hubspot, salesforce")

        return {"success": True, "crm": request.crm, "results": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pushing to CRM: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AIRTABLE/NOTION EXPORT ====================

class AirtableExportRequest(BaseModel):
    base_id: str
    table_name: str = "Leads"
    filters: Optional[dict] = None

@app.post("/api/export/airtable")
async def export_to_airtable(request: AirtableExportRequest):
    """Export leads to Airtable."""
    try:
        export_manager = get_export_manager()

        if not export_manager.airtable:
            export_manager.configure_airtable(settings.airtable_api_key, request.base_id)

        result = await export_manager.airtable.export_leads(
            base_id=request.base_id,
            table_name=request.table_name,
            filters=request.filters
        )

        return {"success": True, "results": result}

    except Exception as e:
        logger.error(f"Error exporting to Airtable: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class NotionExportRequest(BaseModel):
    database_id: str
    filters: Optional[dict] = None

@app.post("/api/export/notion")
async def export_to_notion(request: NotionExportRequest):
    """Export leads to Notion."""
    try:
        export_manager = get_export_manager()

        if not export_manager.notion:
            export_manager.configure_notion(settings.notion_api_key, request.database_id)

        result = await export_manager.notion.export_leads(
            database_id=request.database_id,
            filters=request.filters
        )

        return {"success": True, "results": result}

    except Exception as e:
        logger.error(f"Error exporting to Notion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== NOTIFICATIONS ====================

class NotificationTestRequest(BaseModel):
    channel: str  # slack, discord, email
    message: str = "Test notification from MapLeads Pro"

@app.post("/api/notifications/test")
async def test_notification(request: NotificationTestRequest):
    """Send a test notification."""
    try:
        notification_service = get_notification_service(
            slack_token=settings.slack_token,
            slack_channel=settings.slack_channel,
            discord_webhook_url=settings.discord_webhook_url,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user,
            smtp_password=settings.smtp_password,
            email_from=settings.email_from,
            email_to=settings.email_recipients
        )

        if request.channel == "slack":
            result = await notification_service.send_slack(request.message)
        elif request.channel == "discord":
            result = await notification_service.send_discord("Test", request.message)
        elif request.channel == "email":
            result = await notification_service.send_email("Test Notification", request.message)
        else:
            raise HTTPException(status_code=400, detail="Invalid channel")

        return {"success": result, "channel": request.channel}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== INTEGRATIONS STATUS ====================

@app.get("/api/integrations/status")
async def get_integrations_status():
    """Get status of all integrations."""
    try:
        return {"success": True, "integrations": settings.get_integrations_status()}

    except Exception as e:
        logger.error(f"Error getting integrations status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Serve the new dashboard
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/dashboard")
async def dashboard():
    """Serve the professional dashboard."""
    return FileResponse("frontend/dashboard.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)

    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()

            # Echo or handle messages
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
