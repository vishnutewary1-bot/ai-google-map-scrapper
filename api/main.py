"""FastAPI backend for Google Maps Scraper Dashboard."""
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import asyncio
import json

from database import db_manager, BusinessLead, ScrapeJob
from scraper.google_maps_scraper_v2 import EnhancedGoogleMapsScraper
from utils import DataExporter
from loguru import logger

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

class ExportRequest(BaseModel):
    format: str = "csv"  # csv, json, cold_calling
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
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")

manager = ConnectionManager()

# Background scraping tasks
active_scrapers = {}

async def run_scrape_job(job_id: int, request: ScrapeRequest):
    """Run scraping job in background."""
    try:
        logger.info(f"Starting background scrape job {job_id}")

        # Create scraper
        scraper = EnhancedGoogleMapsScraper(use_proxies=request.use_proxies)
        active_scrapers[job_id] = scraper

        # Initialize
        await scraper.initialize()

        # Run scraping
        results = await scraper.search_and_scrape(
            search_query=request.search_query,
            location=request.location,
            max_results=request.max_results,
            job_id=job_id
        )

        # Broadcast completion
        await manager.broadcast({
            'type': 'job_completed',
            'job_id': job_id,
            'results_count': len(results)
        })

        logger.success(f"Background job {job_id} completed: {len(results)} results")

    except Exception as e:
        logger.error(f"Background job {job_id} failed: {e}")

        # Update job status
        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter_by(id=job_id).first()
            if job:
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
        if job_id in active_scrapers:
            await active_scrapers[job_id].close()
            del active_scrapers[job_id]

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

@app.get("/api/leads", response_model=List[LeadResponse])
async def get_leads(
    limit: int = 50,
    offset: int = 0,
    city: Optional[str] = None,
    state: Optional[str] = None,
    has_phone: bool = False,
    has_website: bool = False,
    has_email: bool = False,
    min_quality: int = 0
):
    """Get list of leads with filters."""
    try:
        with db_manager.get_session() as session:
            query = session.query(BusinessLead).order_by(BusinessLead.scraped_at.desc())

            # Apply filters
            if city:
                query = query.filter(BusinessLead.city == city)
            if state:
                query = query.filter(BusinessLead.state == state)
            if has_phone:
                query = query.filter(BusinessLead.phone.isnot(None))
            if has_website:
                query = query.filter(BusinessLead.website.isnot(None))
            if has_email:
                query = query.filter(BusinessLead.email.isnot(None))
            if min_quality > 0:
                query = query.filter(BusinessLead.data_quality_score >= min_quality)

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
        else:
            raise HTTPException(status_code=400, detail="Invalid format")

        if not filepath:
            raise HTTPException(status_code=404, detail="No data to export")

        return {"filepath": filepath, "status": "success", "count": count}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bulk-scrape")
async def start_bulk_scrape(request: BulkScrapeRequest, background_tasks: BackgroundTasks):
    """Start bulk scraping for multiple locations."""
    try:
        job_ids = []

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

        # Start background tasks for each location
        for i, job_id in enumerate(job_ids):
            # Add delay between jobs
            if i > 0 and request.delay_between_locations > 0:
                await asyncio.sleep(request.delay_between_locations)

            scrape_req = ScrapeRequest(
                search_query=request.search_query,
                location=request.locations[i],
                max_results=request.max_results_per_location,
                use_proxies=False
            )
            background_tasks.add_task(run_scrape_job, job_id, scrape_req)

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
