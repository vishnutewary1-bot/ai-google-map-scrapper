"""Scraping service - business logic for scrape operations."""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scraper import UnifiedGoogleMapsScraper, ScrapeConfig
from api.schemas.requests import ScrapeRequest, BulkScrapeRequest
from api.schemas.responses import JobResponse

# Database imports
try:
    from database import db_manager
    from database.models import ScrapeJob
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False
    db_manager = None
    ScrapeJob = None


class ScrapeService:
    """Service for managing scrape operations."""

    def __init__(self):
        """Initialize the scrape service."""
        self._active_scrapers: Dict[int, UnifiedGoogleMapsScraper] = {}

    def create_job(self, request: ScrapeRequest) -> JobResponse:
        """
        Create a new scrape job in the database.

        Args:
            request: Scrape request parameters

        Returns:
            JobResponse with job details
        """
        if not HAS_DATABASE:
            raise RuntimeError("Database not available")

        with db_manager.get_session() as session:
            job = ScrapeJob(
                search_query=request.search_query,
                location=request.location,
                max_results=request.max_results,
                status='pending',
                created_at=datetime.utcnow(),
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            return JobResponse(
                job_id=job.id,
                status=job.status,
                search_query=job.search_query,
                location=job.location,
                max_results=job.max_results,
                created_at=job.created_at,
            )

    def run_scrape(
        self,
        job_id: int,
        request: ScrapeRequest,
        on_progress: Optional[callable] = None
    ):
        """
        Run a scraping job.

        Args:
            job_id: Database job ID
            request: Scrape request parameters
            on_progress: Callback for progress updates
        """
        scraper = UnifiedGoogleMapsScraper()
        self._active_scrapers[job_id] = scraper

        try:
            config = ScrapeConfig(
                search_query=request.search_query,
                location=request.location,
                max_results=request.max_results,
                extract_emails=request.extract_emails,
                extract_social=request.extract_social,
                extract_contacts=request.extract_contacts,
                extract_insights=request.extract_insights,
                extract_reviews=request.extract_reviews,
                extract_popular_times=request.extract_popular_times,
                enrich_from_website=request.enrich_from_website,
                export_excel=request.export_excel,
                export_sheets=request.export_sheets,
                sheets_spreadsheet_id=request.sheets_spreadsheet_id,
                headless=request.headless,
                on_progress=on_progress,
            )

            result = scraper.scrape(config, job_id=job_id)

            # Update job with results
            if HAS_DATABASE:
                self._update_job_results(job_id, result)

            return result

        except Exception as e:
            logger.error(f"Scrape job {job_id} failed: {e}")
            if HAS_DATABASE:
                self._update_job_error(job_id, str(e))
            raise

        finally:
            scraper.close()
            self._active_scrapers.pop(job_id, None)

    def run_bulk_scrape(
        self,
        job_id: int,
        request: BulkScrapeRequest,
        on_progress: Optional[callable] = None
    ):
        """
        Run bulk scraping for multiple queries.

        Args:
            job_id: Main job ID for tracking
            request: Bulk scrape request
            on_progress: Progress callback
        """
        import time

        all_results = []
        total_searches = len(request.searches)

        for i, search_request in enumerate(request.searches):
            try:
                logger.info(f"Bulk scrape {i + 1}/{total_searches}: {search_request.search_query}")

                # Create sub-job
                sub_job = self.create_job(search_request)

                # Run scrape
                result = self.run_scrape(sub_job.job_id, search_request, on_progress)
                all_results.append(result)

                # Delay between searches
                if i < total_searches - 1:
                    logger.info(f"Waiting {request.delay_between}s before next search...")
                    time.sleep(request.delay_between)

            except Exception as e:
                logger.error(f"Bulk scrape item {i + 1} failed: {e}")
                all_results.append({"error": str(e)})

        return all_results

    def get_job(self, job_id: int) -> Optional[JobResponse]:
        """Get job by ID."""
        if not HAS_DATABASE:
            return None

        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
            if not job:
                return None

            return JobResponse(
                job_id=job.id,
                status=job.status,
                search_query=job.search_query,
                location=job.location,
                max_results=job.max_results,
                results_count=job.leads_scraped,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                error_message=job.last_error,
            )

    def list_jobs(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List all jobs with pagination."""
        if not HAS_DATABASE:
            return {"jobs": [], "total": 0, "limit": limit, "offset": offset}

        with db_manager.get_session() as session:
            total = session.query(ScrapeJob).count()
            jobs = (
                session.query(ScrapeJob)
                .order_by(ScrapeJob.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            return {
                "jobs": [
                    JobResponse(
                        job_id=job.id,
                        status=job.status,
                        search_query=job.search_query,
                        location=job.location,
                        max_results=job.max_results,
                        results_count=job.leads_scraped,
                        created_at=job.created_at,
                        started_at=job.started_at,
                        completed_at=job.completed_at,
                        error_message=job.last_error,
                    )
                    for job in jobs
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    def retry_job(self, job_id: int, background_tasks) -> JobResponse:
        """Retry a failed job."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status not in ("failed", "completed"):
            raise ValueError(f"Job {job_id} cannot be retried (status: {job.status})")

        # Reset job status
        if HAS_DATABASE:
            with db_manager.get_session() as session:
                db_job = session.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
                if db_job:
                    db_job.status = "pending"
                    db_job.error_message = None
                    db_job.started_at = None
                    db_job.completed_at = None
                    session.commit()

        # Create request from job data
        request = ScrapeRequest(
            search_query=job.search_query,
            location=job.location,
            max_results=job.max_results or 100,
        )

        # Add to background tasks
        background_tasks.add_task(self.run_scrape, job_id, request)

        return JobResponse(
            job_id=job_id,
            status="pending",
            search_query=job.search_query,
            location=job.location,
        )

    def delete_job(self, job_id: int) -> bool:
        """Delete a job and its leads."""
        if not HAS_DATABASE:
            return False

        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
            if not job:
                return False

            # Note: BusinessLead doesn't have job_id, so we can't delete associated leads
            # Delete job only
            session.delete(job)
            session.commit()

            return True

    def cancel_job(self, job_id: int) -> bool:
        """Cancel a running job."""
        scraper = self._active_scrapers.get(job_id)
        if scraper:
            scraper.close()
            self._active_scrapers.pop(job_id, None)

            if HAS_DATABASE:
                with db_manager.get_session() as session:
                    job = session.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
                    if job:
                        job.status = "cancelled"
                        job.completed_at = datetime.utcnow()
                        session.commit()

            return True

        return False

    def _update_job_results(self, job_id: int, result):
        """Update job with scrape results."""
        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
            if job:
                job.status = "completed" if result.success else "failed"
                job.leads_scraped = result.total_saved
                job.completed_at = datetime.utcnow()
                if hasattr(result, 'sheets_url') and result.sheets_url:
                    job.google_sheet_url = result.sheets_url
                session.commit()

    def _update_job_error(self, job_id: int, error: str):
        """Update job with error message."""
        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.last_error = error[:500]  # Limit error message length
                job.completed_at = datetime.utcnow()
                session.commit()


# Singleton instance
scrape_service = ScrapeService()
