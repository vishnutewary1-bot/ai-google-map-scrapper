"""API response schemas using Pydantic."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class JobResponse(BaseModel):
    """Response schema for a scrape job."""

    job_id: int = Field(..., description="Job ID")
    status: str = Field(..., description="Job status")
    search_query: Optional[str] = Field(None, description="Search query")
    location: Optional[str] = Field(None, description="Location filter")
    max_results: Optional[int] = Field(None, description="Max results requested")
    results_count: Optional[int] = Field(None, description="Actual results count")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    excel_path: Optional[str] = Field(None, description="Path to Excel export")
    sheets_url: Optional[str] = Field(None, description="Google Sheets URL")

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Response schema for list of jobs."""

    jobs: List[JobResponse] = Field(default_factory=list)
    total: int = Field(0, description="Total number of jobs")
    offset: int = Field(0, description="Offset for pagination")
    limit: int = Field(50, description="Limit for pagination")


class LeadResponse(BaseModel):
    """Response schema for a single lead."""

    id: int
    job_id: Optional[int] = None

    # Basic info
    business_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    category: Optional[str] = None

    # Address
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    country: Optional[str] = None

    # Ratings
    rating: Optional[float] = None
    review_count: Optional[int] = None
    price_level: Optional[str] = None

    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    maps_url: Optional[str] = None
    place_id: Optional[str] = None

    # Additional emails/phones
    email_2: Optional[str] = None
    email_3: Optional[str] = None
    phone_2: Optional[str] = None
    phone_3: Optional[str] = None

    # Social media
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    linkedin: Optional[str] = None
    twitter: Optional[str] = None
    youtube: Optional[str] = None

    # Contact persons
    contact_person_1: Optional[str] = None
    contact_title_1: Optional[str] = None
    contact_email_1: Optional[str] = None
    contact_person_2: Optional[str] = None
    contact_title_2: Optional[str] = None
    contact_email_2: Optional[str] = None

    # Company insights
    employee_count: Optional[int] = None
    employee_range: Optional[str] = None
    founded_year: Optional[int] = None
    company_type: Optional[str] = None
    revenue_estimate: Optional[str] = None
    description: Optional[str] = None

    # Metadata
    quality_score: Optional[int] = None
    data_quality_score: Optional[int] = None
    star_rating: Optional[int] = None
    search_query: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None

    # Timestamps
    scraped_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    """Response schema for list of leads."""

    leads: List[LeadResponse] = Field(default_factory=list)
    total: int = Field(0, description="Total number of leads matching filters")
    offset: int = Field(0, description="Offset for pagination")
    limit: int = Field(100, description="Limit for pagination")

    # Aggregations
    cities: Optional[List[str]] = Field(None, description="Available cities")
    states: Optional[List[str]] = Field(None, description="Available states")
    categories: Optional[List[str]] = Field(None, description="Available categories")


class ExportResponse(BaseModel):
    """Response schema for export operations."""

    success: bool = Field(..., description="Whether export succeeded")
    format: str = Field(..., description="Export format")
    filename: Optional[str] = Field(None, description="Exported filename")
    filepath: Optional[str] = Field(None, description="Full file path")
    download_url: Optional[str] = Field(None, description="Download URL")
    sheets_url: Optional[str] = Field(None, description="Google Sheets URL")
    crm_url: Optional[str] = Field(None, description="CRM record URL")
    records_exported: int = Field(0, description="Number of records exported")
    error: Optional[str] = Field(None, description="Error message if failed")


class StatsResponse(BaseModel):
    """Response schema for statistics."""

    total_leads: int = Field(0, description="Total leads in database")
    total_jobs: int = Field(0, description="Total scrape jobs")

    # Lead statistics
    leads_with_email: int = Field(0, description="Leads with email")
    leads_with_phone: int = Field(0, description="Leads with phone")
    leads_with_website: int = Field(0, description="Leads with website")
    leads_with_social: int = Field(0, description="Leads with any social media")

    # Quality breakdown
    avg_quality_score: float = Field(0.0, description="Average quality score")
    high_quality_leads: int = Field(0, description="Leads with score >= 70")
    medium_quality_leads: int = Field(0, description="Leads with score 40-69")
    low_quality_leads: int = Field(0, description="Leads with score < 40")

    # Top categories
    top_categories: List[Dict[str, Any]] = Field(default_factory=list)

    # Top cities
    top_cities: List[Dict[str, Any]] = Field(default_factory=list)

    # Recent activity
    leads_today: int = Field(0)
    leads_this_week: int = Field(0)
    leads_this_month: int = Field(0)

    # Job statistics
    jobs_completed: int = Field(0)
    jobs_failed: int = Field(0)
    jobs_running: int = Field(0)


class WebSocketMessage(BaseModel):
    """Schema for WebSocket messages."""

    type: str = Field(..., description="Message type (progress, completed, error)")
    job_id: int = Field(..., description="Job ID")
    data: Dict[str, Any] = Field(default_factory=dict, description="Message data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Response schema for health check."""

    status: str = Field("healthy", description="Service status")
    version: str = Field("2.0.0", description="API version")
    database: str = Field("connected", description="Database status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SentimentAnalysisResponse(BaseModel):
    """Response schema for sentiment analysis."""

    enabled: bool = Field(..., description="Whether sentiment analysis is enabled")
    total_analyzed: int = Field(0, description="Number of reviews analyzed")
    positive_count: int = Field(0, description="Number of positive reviews")
    negative_count: int = Field(0, description="Number of negative reviews")
    neutral_count: int = Field(0, description="Number of neutral reviews")
    average_polarity: float = Field(0.0, description="Average polarity score")
    average_subjectivity: float = Field(0.0, description="Average subjectivity score")
    overall_sentiment: str = Field("neutral", description="Overall sentiment label")
    sentiment_score: int = Field(50, description="Sentiment score 0-100")
    key_phrases: Dict[str, List[str]] = Field(default_factory=dict, description="Key phrases")
    error: Optional[str] = Field(None, description="Error message if any")


class CompetitorComparisonResponse(BaseModel):
    """Response schema for competitor comparison."""

    businesses_compared: int = Field(..., description="Number of businesses compared")
    winner_summary: Dict[str, Any] = Field(default_factory=dict, description="Winner in each category")
    detailed_comparison: Dict[str, Any] = Field(default_factory=dict, description="Detailed comparison data")
    insights: List[str] = Field(default_factory=list, description="Comparison insights")
    chart_data: Dict[str, Any] = Field(default_factory=dict, description="Data for charts")


class EmailTemplateResponse(BaseModel):
    """Response schema for cold email templates."""

    success: bool = Field(..., description="Whether generation succeeded")
    template_type: str = Field(..., description="Type of template generated")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body")
    personalization_score: float = Field(0.0, description="Personalization quality score")
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")
    error: Optional[str] = Field(None, description="Error message if failed")


class WebhookResponse(BaseModel):
    """Response schema for webhook operations."""

    success: bool = Field(..., description="Whether operation succeeded")
    webhook_name: Optional[str] = Field(None, description="Webhook name")
    message: str = Field(..., description="Result message")
    registered_webhooks: Optional[List[Dict[str, Any]]] = Field(None, description="List of webhooks")
    event_history: Optional[List[Dict[str, Any]]] = Field(None, description="Recent events")


class DataFreshnessResponse(BaseModel):
    """Response schema for data freshness check."""

    lead_id: int = Field(..., description="Lead ID")
    business_name: str = Field(..., description="Business name")
    freshness_status: str = Field(..., description="Freshness status (fresh, recent, stale, expired)")
    last_verified_at: Optional[datetime] = Field(None, description="Last verification timestamp")
    days_since_verified: Optional[int] = Field(None, description="Days since last verification")
    needs_refresh: bool = Field(False, description="Whether data needs refresh")
    changes_detected: Optional[Dict[str, Any]] = Field(None, description="Changes since last check")


class GeoScrapeResponse(BaseModel):
    """Response schema for geo-coordinate scraping."""

    job_id: int = Field(..., description="Job ID")
    status: str = Field(..., description="Job status")
    center_coordinates: Dict[str, float] = Field(..., description="Center lat/lng")
    radius_km: float = Field(..., description="Search radius")
    grid_points: int = Field(..., description="Number of grid points searched")
    total_leads_found: Optional[int] = Field(None, description="Total leads found")


class BulkImportResponse(BaseModel):
    """Response schema for bulk URL import."""

    job_id: int = Field(..., description="Job ID")
    status: str = Field(..., description="Job status")
    urls_submitted: int = Field(..., description="Number of URLs submitted")
    urls_valid: int = Field(..., description="Number of valid URLs")
    urls_invalid: List[str] = Field(default_factory=list, description="Invalid URLs")


class IntegrationStatusResponse(BaseModel):
    """Response schema for integration status."""

    integrations: Dict[str, Dict[str, Any]] = Field(..., description="Status of all integrations")
    new_features: Dict[str, Dict[str, Any]] = Field(..., description="Status of new features")
