"""API request schemas using Pydantic."""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re


class ScrapeRequest(BaseModel):
    """Request schema for starting a scrape job."""

    search_query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="What to search for (e.g., 'restaurants', 'plumbers')"
    )
    location: Optional[str] = Field(
        None,
        max_length=200,
        description="Location filter (e.g., 'New York, NY')"
    )
    max_results: int = Field(
        100,
        ge=1,
        le=500,
        description="Maximum number of results to scrape"
    )

    # Extraction options
    extract_emails: bool = Field(True, description="Extract email addresses from websites")
    extract_social: bool = Field(True, description="Extract social media links")
    extract_contacts: bool = Field(True, description="Extract contact persons")
    extract_insights: bool = Field(True, description="Extract company insights")
    extract_reviews: bool = Field(False, description="Extract reviews (slower)")
    extract_popular_times: bool = Field(False, description="Extract popular times data")
    enrich_from_website: bool = Field(True, description="Visit business websites for enrichment")

    # Export options
    export_excel: bool = Field(True, description="Export results to Excel")
    export_sheets: bool = Field(False, description="Export to Google Sheets")
    sheets_spreadsheet_id: Optional[str] = Field(None, description="Existing Google Sheets ID")

    # Browser options
    headless: bool = Field(True, description="Run browser in headless mode")

    # Speed options
    fast_mode: bool = Field(False, description="Enable fast mode (reduced delays, 2-3x faster)")
    parallel_browsers: int = Field(1, ge=1, le=5, description="Number of parallel browsers (1-5, more = faster)")

    # Pre-scrape filters (applied during scraping)
    filters: Optional["ScrapeFilters"] = Field(
        None,
        description="Filters to apply during scraping (before saving)"
    )

    @field_validator('search_query')
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Remove potentially dangerous characters from search query."""
        # Remove HTML/script tags
        v = re.sub(r'<[^>]*>', '', v)
        # Remove special characters that could cause issues
        v = v.replace('<', '').replace('>', '').replace('"', '').replace("'", '')
        return v.strip()

    @field_validator('location')
    @classmethod
    def sanitize_location(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize location input."""
        if v is None:
            return v
        v = re.sub(r'<[^>]*>', '', v)
        return v.strip() or None


class ScrapeFilters(BaseModel):
    """
    Pre-scrape filters applied DURING scraping to filter businesses before saving.

    These filters are different from LeadFilters which filter already-saved leads.
    ScrapeFilters determine which scraped businesses are saved to the database.
    """

    # Google rating filters (Google's rating, not our star rating)
    min_google_rating: Optional[float] = Field(
        None, ge=1.0, le=5.0,
        description="Minimum Google rating (1-5)"
    )
    max_google_rating: Optional[float] = Field(
        None, ge=1.0, le=5.0,
        description="Maximum Google rating (1-5)"
    )

    # Review count filters
    min_review_count: Optional[int] = Field(
        None, ge=0,
        description="Minimum number of Google reviews"
    )
    max_review_count: Optional[int] = Field(
        None, ge=0,
        description="Maximum number of Google reviews"
    )

    # Contact requirements - business MUST have these
    require_phone: bool = Field(False, description="Only include businesses with phone")
    require_website: bool = Field(False, description="Only include businesses with website")
    require_email: bool = Field(False, description="Only include businesses with email (from website)")

    # Opportunity filters - find businesses MISSING these (sales opportunities)
    missing_website: bool = Field(False, description="Only include businesses WITHOUT website")
    missing_social_media: bool = Field(False, description="Only include businesses WITHOUT social media")
    missing_email: bool = Field(False, description="Only include businesses WITHOUT email")

    # Social media requirements
    require_facebook: bool = Field(False, description="Only include businesses with Facebook")
    require_instagram: bool = Field(False, description="Only include businesses with Instagram")
    require_linkedin: bool = Field(False, description="Only include businesses with LinkedIn")
    require_any_social: bool = Field(False, description="Only include businesses with any social media")

    # Business status filters
    exclude_permanently_closed: bool = Field(True, description="Exclude permanently closed businesses")
    exclude_temporarily_closed: bool = Field(False, description="Exclude temporarily closed businesses")

    # Filter logic
    logic_operator: str = Field(
        "AND",
        pattern="^(AND|OR)$",
        description="How to combine multiple filters (AND = all must match, OR = any can match)"
    )

    # Preset name (for tracking)
    preset_name: Optional[str] = Field(None, description="Name of filter preset used")


class BulkScrapeRequest(BaseModel):
    """Request schema for bulk scraping multiple queries."""

    searches: List["ScrapeRequest"] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of scrape requests"
    )
    delay_between: int = Field(
        60,
        ge=10,
        le=300,
        description="Delay between searches in seconds"
    )


class LeadFilters(BaseModel):
    """Filters for querying leads."""

    # Location filters
    city: Optional[str] = Field(None, description="Filter by city")
    state: Optional[str] = Field(None, description="Filter by state")
    country: Optional[str] = Field(None, description="Filter by country")
    pincode: Optional[str] = Field(None, description="Filter by postal code")

    # Category filter
    category: Optional[str] = Field(None, description="Filter by business category")

    # Contact filters
    has_email: Optional[bool] = Field(None, description="Filter by has email")
    has_phone: Optional[bool] = Field(None, description="Filter by has phone")
    has_website: Optional[bool] = Field(None, description="Filter by has website")

    # Social media filters
    has_facebook: Optional[bool] = Field(None, description="Filter by has Facebook")
    has_instagram: Optional[bool] = Field(None, description="Filter by has Instagram")
    has_linkedin: Optional[bool] = Field(None, description="Filter by has LinkedIn")

    # Rating filters
    min_rating: Optional[float] = Field(None, ge=0, le=5, description="Minimum rating")
    max_rating: Optional[float] = Field(None, ge=0, le=5, description="Maximum rating")

    # Review count filters
    min_reviews: Optional[int] = Field(None, ge=0, description="Minimum review count")
    max_reviews: Optional[int] = Field(None, ge=0, description="Maximum review count")

    # Quality score filter
    min_quality: Optional[int] = Field(None, ge=0, le=100, description="Minimum quality score")

    # Star rating filter
    min_star_rating: Optional[int] = Field(None, ge=1, le=5, description="Minimum star rating (1-5)")
    max_star_rating: Optional[int] = Field(None, ge=1, le=5, description="Maximum star rating (1-5)")

    # Search filter
    search: Optional[str] = Field(None, max_length=200, description="Search in name/address")

    # Job filter
    job_id: Optional[int] = Field(None, description="Filter by scrape job ID")

    # Date filters
    scraped_after: Optional[str] = Field(None, description="Filter by scrape date (ISO format)")
    scraped_before: Optional[str] = Field(None, description="Filter by scrape date (ISO format)")


class LeadUpdateRequest(BaseModel):
    """Request schema for updating a lead."""

    business_name: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    website: Optional[str] = Field(None, max_length=500)
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=20)
    category: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = Field(None, max_length=2000)
    tags: Optional[List[str]] = Field(None, description="List of tags")
    status: Optional[str] = Field(None, pattern="^(new|contacted|qualified|converted|lost)$")

    # Social media
    facebook: Optional[str] = Field(None, max_length=500)
    instagram: Optional[str] = Field(None, max_length=500)
    linkedin: Optional[str] = Field(None, max_length=500)
    twitter: Optional[str] = Field(None, max_length=500)

    # Contact persons
    contact_person_1: Optional[str] = Field(None, max_length=200)
    contact_title_1: Optional[str] = Field(None, max_length=100)
    contact_email_1: Optional[str] = Field(None, max_length=255)


class ExportRequest(BaseModel):
    """Request schema for exporting leads."""

    format: str = Field(
        "excel",
        pattern="^(csv|json|excel|cold_calling|email_campaign)$",
        description="Export format"
    )
    filters: Optional[LeadFilters] = Field(None, description="Filters to apply")
    lead_ids: Optional[List[int]] = Field(None, description="Specific lead IDs to export")
    columns: Optional[List[str]] = Field(None, description="Columns to include")

    # Google Sheets export
    export_to_sheets: bool = Field(False, description="Also export to Google Sheets")
    sheets_spreadsheet_id: Optional[str] = Field(None, description="Existing spreadsheet ID")

    # CRM export
    export_to_crm: Optional[str] = Field(
        None,
        pattern="^(hubspot|salesforce|airtable|notion)$",
        description="CRM to export to"
    )

    # Cloud storage export
    upload_to_s3: bool = Field(False, description="Upload to AWS S3")
    upload_to_gcs: bool = Field(False, description="Upload to Google Cloud Storage")


class GeoScrapeRequest(BaseModel):
    """Request schema for geo-coordinate based scraping."""

    search_query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="What to search for (e.g., 'restaurants', 'plumbers')"
    )
    latitude: float = Field(..., ge=-90, le=90, description="Center latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Center longitude")
    radius_km: float = Field(5.0, ge=0.1, le=50, description="Search radius in kilometers")
    grid_size: int = Field(3, ge=1, le=5, description="Grid size for coverage (NxN)")
    max_results: int = Field(100, ge=1, le=500, description="Maximum results per grid point")

    # Extraction options
    extract_emails: bool = Field(True, description="Extract email addresses")
    extract_social: bool = Field(True, description="Extract social media links")
    extract_reviews: bool = Field(False, description="Extract reviews")
    extract_popular_times: bool = Field(False, description="Extract popular times")
    extract_photos: bool = Field(False, description="Extract photo URLs")

    # Browser options
    headless: bool = Field(True, description="Run browser in headless mode")


class BulkUrlImportRequest(BaseModel):
    """Request schema for importing from Google Maps URLs."""

    urls: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of Google Maps URLs to scrape"
    )

    # Extraction options
    extract_emails: bool = Field(True, description="Extract email addresses")
    extract_social: bool = Field(True, description="Extract social media links")
    extract_reviews: bool = Field(False, description="Extract reviews")
    extract_popular_times: bool = Field(False, description="Extract popular times")
    extract_photos: bool = Field(False, description="Extract photo URLs")
    enrich_from_website: bool = Field(True, description="Visit websites for enrichment")

    @field_validator('urls')
    @classmethod
    def validate_urls(cls, v: List[str]) -> List[str]:
        """Validate that URLs are Google Maps URLs."""
        valid_urls = []
        for url in v:
            if 'google.com/maps' in url or 'maps.google.com' in url or 'goo.gl/maps' in url:
                valid_urls.append(url.strip())
        if not valid_urls:
            raise ValueError("No valid Google Maps URLs provided")
        return valid_urls


class WebhookRegisterRequest(BaseModel):
    """Request schema for registering a webhook."""

    name: str = Field(..., min_length=1, max_length=100, description="Webhook name")
    url: str = Field(..., description="Webhook URL")
    secret: Optional[str] = Field(None, description="HMAC secret for signing")
    events: List[str] = Field(
        default=["job.completed", "lead.created"],
        description="Events to trigger webhook"
    )


class WebhookTestRequest(BaseModel):
    """Request schema for testing a webhook."""

    webhook_name: str = Field(..., description="Name of registered webhook to test")
    event_type: str = Field("test", description="Event type for test")


class SentimentAnalysisRequest(BaseModel):
    """Request schema for sentiment analysis."""

    lead_id: Optional[int] = Field(None, description="Analyze reviews for a specific lead")
    text: Optional[str] = Field(None, description="Analyze specific text")
    reviews: Optional[List[dict]] = Field(None, description="Analyze list of reviews")


class CompetitorComparisonRequest(BaseModel):
    """Request schema for competitor comparison."""

    lead_ids: List[int] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Lead IDs to compare"
    )


class EmailTemplateRequest(BaseModel):
    """Request schema for generating cold email templates."""

    lead_id: int = Field(..., description="Lead ID to generate email for")
    template_type: str = Field(
        "introduction",
        pattern="^(introduction|value_proposition|follow_up|review_request|partnership)$",
        description="Type of email template"
    )
    sender_name: str = Field(..., description="Sender's name")
    sender_company: str = Field(..., description="Sender's company name")
    sender_title: Optional[str] = Field(None, description="Sender's job title")
    custom_value_proposition: Optional[str] = Field(None, description="Custom value proposition")
