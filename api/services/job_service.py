"""Job service - centralized job status management.

This module consolidates job status update logic that was previously
scattered across scrape_service.py and unified_scraper.py.
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

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


class JobService:
    """Centralized service for managing scrape job status."""

    def get_job(self, job_id: int) -> Optional[JobResponse]:
        """
        Get a job by ID.

        Args:
            job_id: The job ID

        Returns:
            JobResponse or None if not found
        """
        if not HAS_DATABASE:
            return None

        with db_manager.get_session() as session:
            job = session.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
            if not job:
                return None

            return self._job_to_response(job)

    def get_jobs(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[JobResponse]:
        """
        Get list of jobs with optional filtering.

        Args:
            limit: Maximum jobs to return
            offset: Pagination offset
            status: Filter by status ('pending', 'running', 'completed', 'failed', 'cancelled')

        Returns:
            List of JobResponse objects
        """
        if not HAS_DATABASE:
            return []

        with db_manager.get_session() as session:
            query = session.query(ScrapeJob)

            if status:
                query = query.filter(ScrapeJob.status == status)

            jobs = (
                query
                .order_by(ScrapeJob.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            return [self._job_to_response(job) for job in jobs]

    def update_status(
        self,
        job_id: int,
        status: str,
        error_message: Optional[str] = None,
        leads_scraped: Optional[int] = None,
        progress: Optional[int] = None,
        google_sheet_url: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update job status.

        Args:
            job_id: The job ID to update
            status: New status ('pending', 'running', 'completed', 'failed', 'cancelled')
            error_message: Optional error message for failed jobs
            leads_scraped: Number of leads scraped
            progress: Progress percentage (0-100)
            google_sheet_url: Google Sheets URL if exported
            extra_data: Additional data to store

        Returns:
            True if update was successful, False otherwise
        """
        if not HAS_DATABASE:
            logger.warning("Database not available, cannot update job status")
            return False

        try:
            with db_manager.get_session() as session:
                job = session.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
                if not job:
                    logger.warning(f"Job {job_id} not found")
                    return False

                # Update status
                job.status = status

                # Update completion time for terminal states
                if status in ('completed', 'failed', 'cancelled'):
                    job.completed_at = datetime.utcnow()

                # Update error message
                if error_message:
                    # Truncate to avoid database issues
                    job.last_error = error_message[:500] if len(error_message) > 500 else error_message

                # Update leads count
                if leads_scraped is not None:
                    job.leads_scraped = leads_scraped

                # Update progress
                if progress is not None and hasattr(job, 'progress'):
                    job.progress = progress

                # Update Google Sheets URL
                if google_sheet_url and hasattr(job, 'google_sheet_url'):
                    job.google_sheet_url = google_sheet_url

                session.commit()
                logger.debug(f"Updated job {job_id} status to {status}")
                return True

        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
            return False

    def start_job(self, job_id: int) -> bool:
        """
        Mark job as running.

        Args:
            job_id: The job ID

        Returns:
            True if successful
        """
        return self.update_status(job_id, status='running')

    def complete_job(
        self,
        job_id: int,
        leads_scraped: int,
        google_sheet_url: Optional[str] = None
    ) -> bool:
        """
        Mark job as completed.

        Args:
            job_id: The job ID
            leads_scraped: Number of leads scraped
            google_sheet_url: Optional Google Sheets URL

        Returns:
            True if successful
        """
        return self.update_status(
            job_id,
            status='completed',
            leads_scraped=leads_scraped,
            google_sheet_url=google_sheet_url
        )

    def fail_job(self, job_id: int, error_message: str) -> bool:
        """
        Mark job as failed.

        Args:
            job_id: The job ID
            error_message: Error description

        Returns:
            True if successful
        """
        return self.update_status(
            job_id,
            status='failed',
            error_message=error_message
        )

    def cancel_job(self, job_id: int) -> bool:
        """
        Mark job as cancelled.

        Args:
            job_id: The job ID

        Returns:
            True if successful
        """
        return self.update_status(job_id, status='cancelled')

    def update_progress(self, job_id: int, progress: int, leads_scraped: int = 0) -> bool:
        """
        Update job progress during scraping.

        Args:
            job_id: The job ID
            progress: Progress percentage (0-100)
            leads_scraped: Current leads count

        Returns:
            True if successful
        """
        return self.update_status(
            job_id,
            status='running',
            progress=progress,
            leads_scraped=leads_scraped
        )

    def delete_job(self, job_id: int) -> bool:
        """
        Delete a job.

        Args:
            job_id: The job ID to delete

        Returns:
            True if deleted, False otherwise
        """
        if not HAS_DATABASE:
            return False

        try:
            with db_manager.get_session() as session:
                job = session.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
                if not job:
                    return False

                session.delete(job)
                session.commit()
                logger.info(f"Deleted job {job_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False

    def _job_to_response(self, job) -> JobResponse:
        """Convert database job to response schema."""
        return JobResponse(
            job_id=job.id,
            status=job.status,
            search_query=job.search_query,
            location=job.location,
            max_results=job.max_results,
            leads_scraped=job.leads_scraped,
            google_sheet_url=getattr(job, 'google_sheet_url', None),
            error_message=getattr(job, 'last_error', None),
            progress=getattr(job, 'progress', None),
            created_at=job.created_at,
            started_at=getattr(job, 'started_at', None),
            completed_at=job.completed_at,
        )


# Singleton instance
job_service = JobService()


# Convenience functions for use from other modules
def update_job_status(
    job_id: int,
    status: str,
    **kwargs
) -> bool:
    """Update job status (convenience function)."""
    return job_service.update_status(job_id, status, **kwargs)


def complete_job(job_id: int, leads_scraped: int, **kwargs) -> bool:
    """Mark job as completed (convenience function)."""
    return job_service.complete_job(job_id, leads_scraped, **kwargs)


def fail_job(job_id: int, error_message: str) -> bool:
    """Mark job as failed (convenience function)."""
    return job_service.fail_job(job_id, error_message)
