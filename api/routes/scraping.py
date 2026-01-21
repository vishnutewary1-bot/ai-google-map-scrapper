"""Scraping API routes."""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger

from api.schemas.requests import ScrapeRequest, BulkScrapeRequest
from api.schemas.responses import JobResponse, JobListResponse
from api.services.scrape_service import scrape_service
from api.routes.websocket import broadcast_job_update

router = APIRouter()


@router.post("/scrape", response_model=JobResponse)
async def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Start a new scrape job.

    The scrape runs in the background. Use the job ID to check status
    or connect via WebSocket for real-time updates.
    """
    try:
        # Create job in database
        job = scrape_service.create_job(request)

        # Define progress callback for WebSocket updates
        def on_progress(current: int, total: int, status: str):
            broadcast_job_update(job.job_id, "progress", {
                "current": current,
                "total": total,
                "status": status,
            })

        # Run scrape in background
        background_tasks.add_task(
            scrape_service.run_scrape,
            job.job_id,
            request,
            on_progress
        )

        return JobResponse(
            job_id=job.job_id,
            status="started",
            search_query=request.search_query,
            location=request.location,
            max_results=request.max_results,
        )

    except Exception as e:
        logger.error(f"Failed to start scrape: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-scrape", response_model=JobResponse)
async def bulk_scrape(request: BulkScrapeRequest, background_tasks: BackgroundTasks):
    """
    Start a bulk scraping job for multiple queries.

    Each query will be processed sequentially with delays between them.
    """
    try:
        # Create main tracking job
        first_request = request.searches[0]
        job = scrape_service.create_job(first_request)

        # Run bulk scrape in background
        background_tasks.add_task(
            scrape_service.run_bulk_scrape,
            job.job_id,
            request,
        )

        return JobResponse(
            job_id=job.job_id,
            status="started",
            search_query=f"Bulk: {len(request.searches)} queries",
        )

    except Exception as e:
        logger.error(f"Failed to start bulk scrape: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(limit: int = 50, offset: int = 0):
    """List all scrape jobs with pagination."""
    try:
        result = scrape_service.list_jobs(limit=limit, offset=offset)
        return JobListResponse(**result)
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int):
    """Get details of a specific job."""
    job = scrape_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: int, background_tasks: BackgroundTasks):
    """Retry a failed or completed job."""
    try:
        return scrape_service.retry_job(job_id, background_tasks)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to retry job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: int):
    """Cancel a running job."""
    success = scrape_service.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or not running")
    return {"success": True, "message": "Job cancelled"}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: int):
    """Delete a job and all its associated leads."""
    success = scrape_service.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "message": "Job deleted"}
