"""API schemas package."""

from .requests import (
    ScrapeRequest,
    BulkScrapeRequest,
    LeadFilters,
    LeadUpdateRequest,
    ExportRequest,
)
from .responses import (
    JobResponse,
    JobListResponse,
    LeadResponse,
    LeadListResponse,
    ExportResponse,
    StatsResponse,
)

__all__ = [
    # Requests
    'ScrapeRequest',
    'BulkScrapeRequest',
    'LeadFilters',
    'LeadUpdateRequest',
    'ExportRequest',

    # Responses
    'JobResponse',
    'JobListResponse',
    'LeadResponse',
    'LeadListResponse',
    'ExportResponse',
    'StatsResponse',
]
