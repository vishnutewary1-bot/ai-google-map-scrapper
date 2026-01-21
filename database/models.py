"""Database models for Google Maps Scraper - Enhanced with 60+ columns."""
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, JSON, Text, Index, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class BusinessLead(Base):
    """
    Enhanced model for storing scraped business leads from Google Maps.

    Total columns: 60+ for comprehensive lead data including:
    - Core business information
    - Contact details (multiple emails, phones)
    - Social media links
    - Company insights (employees, revenue, founded year)
    - Review breakdown
    - Business hours
    - Popular times
    - Photos
    - Data freshness tracking
    - Sentiment analysis
    - Metadata
    """

    __tablename__ = "business_leads"

    # ==================== PRIMARY KEY ====================
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ==================== CORE BUSINESS INFO ====================
    business_name = Column(String(500), nullable=False)
    category = Column(String(200), nullable=True)
    subcategories = Column(JSON, nullable=True)  # Array of subcategories
    business_type = Column(String(100), nullable=True)  # Restaurant, Hotel, etc.

    # ==================== LOCATION DATA ====================
    full_address = Column(Text, nullable=True)
    street = Column(String(500), nullable=True)
    city = Column(String(200), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    pin_code = Column(String(20), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # ==================== CONTACT - PRIMARY ====================
    phone = Column(String(50), nullable=True)  # Primary phone
    website = Column(String(1000), nullable=True)
    email = Column(String(200), nullable=True)  # Primary email

    # ==================== CONTACT - MULTIPLE PHONES ====================
    phone_1 = Column(String(50), nullable=True)
    phone_2 = Column(String(50), nullable=True)
    phone_3 = Column(String(50), nullable=True)

    # ==================== CONTACT - MULTIPLE EMAILS ====================
    email_1 = Column(String(200), nullable=True)
    email_2 = Column(String(200), nullable=True)
    email_3 = Column(String(200), nullable=True)

    # ==================== CONTACT PERSONS ====================
    contact_name_1 = Column(String(200), nullable=True)
    contact_title_1 = Column(String(200), nullable=True)
    contact_email_1 = Column(String(200), nullable=True)
    contact_name_2 = Column(String(200), nullable=True)
    contact_title_2 = Column(String(200), nullable=True)
    contact_email_2 = Column(String(200), nullable=True)
    contact_name_3 = Column(String(200), nullable=True)
    contact_title_3 = Column(String(200), nullable=True)
    contact_email_3 = Column(String(200), nullable=True)

    # ==================== SOCIAL MEDIA LINKS ====================
    social_facebook = Column(String(500), nullable=True)
    social_instagram = Column(String(500), nullable=True)
    social_twitter = Column(String(500), nullable=True)
    social_linkedin = Column(String(500), nullable=True)
    social_youtube = Column(String(500), nullable=True)
    social_tiktok = Column(String(500), nullable=True)
    social_pinterest = Column(String(500), nullable=True)
    social_whatsapp = Column(String(500), nullable=True)

    # ==================== COMPANY INSIGHTS ====================
    employees = Column(String(100), nullable=True)  # "50-100" or "100+"
    employees_min = Column(Integer, nullable=True)
    employees_max = Column(Integer, nullable=True)
    founded_year = Column(Integer, nullable=True)
    revenue = Column(String(100), nullable=True)  # "$1M - $10M"
    revenue_min = Column(Float, nullable=True)
    revenue_max = Column(Float, nullable=True)
    company_type = Column(String(50), nullable=True)  # LLC, Inc., etc.
    industry = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)  # Company description

    # ==================== RATINGS & REVIEWS ====================
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    reviews_1_star = Column(Integer, nullable=True)
    reviews_2_star = Column(Integer, nullable=True)
    reviews_3_star = Column(Integer, nullable=True)
    reviews_4_star = Column(Integer, nullable=True)
    reviews_5_star = Column(Integer, nullable=True)
    price_level = Column(String(10), nullable=True)  # $, $$, $$$, $$$$

    # ==================== REVIEWS DATA (NEW) ====================
    reviews = Column(JSON, nullable=True)  # Full review data
    review_highlights = Column(JSON, nullable=True)  # Key phrases from reviews

    # ==================== BUSINESS HOURS ====================
    hours_monday = Column(String(100), nullable=True)
    hours_tuesday = Column(String(100), nullable=True)
    hours_wednesday = Column(String(100), nullable=True)
    hours_thursday = Column(String(100), nullable=True)
    hours_friday = Column(String(100), nullable=True)
    hours_saturday = Column(String(100), nullable=True)
    hours_sunday = Column(String(100), nullable=True)
    is_open_now = Column(Boolean, nullable=True)

    # ==================== POPULAR TIMES (NEW) ====================
    popular_times = Column(JSON, nullable=True)  # Full popular times data
    busiest_day = Column(String(20), nullable=True)
    busiest_hour = Column(String(20), nullable=True)
    quietest_day = Column(String(20), nullable=True)
    quietest_hour = Column(String(20), nullable=True)
    typical_time_spent = Column(String(50), nullable=True)
    live_busyness = Column(Integer, nullable=True)  # Current busyness %

    # ==================== PHOTOS (NEW) ====================
    photos = Column(JSON, nullable=True)  # List of photo URLs
    photo_count = Column(Integer, nullable=True)
    main_photo = Column(String(1000), nullable=True)

    # ==================== GOOGLE MAPS METADATA ====================
    place_id = Column(String(200), unique=True, nullable=True)  # Google's unique ID
    maps_url = Column(String(1000), nullable=True)
    cid = Column(String(50), nullable=True)  # Google CID

    # ==================== SCRAPING METADATA ====================
    scraped_at = Column(DateTime, default=func.now(), nullable=False)
    search_query = Column(String(500), nullable=True)
    data_quality_score = Column(Integer, default=0)  # 0-100 completeness score
    data_source = Column(String(100), default='google_maps')  # Source of data

    # ==================== DATA FRESHNESS (NEW) ====================
    last_verified_at = Column(DateTime, nullable=True)
    verification_count = Column(Integer, default=0)
    data_changed = Column(Boolean, default=False)  # Changed since last scrape
    change_history = Column(JSON, nullable=True)  # Track what changed

    # ==================== SENTIMENT ANALYSIS (NEW) ====================
    sentiment_score = Column(Integer, nullable=True)  # 0-100
    sentiment_label = Column(String(20), nullable=True)  # positive, negative, neutral
    sentiment_analysis = Column(JSON, nullable=True)  # Full analysis data

    # ==================== LEAD SCORING ====================
    lead_score = Column(String(5), nullable=True)  # A+, A, B, C, D, F
    lead_score_numeric = Column(Integer, nullable=True)  # 0-100

    # ==================== JOB RELATIONSHIP ====================
    job_id = Column(Integer, ForeignKey('scrape_jobs.id'), nullable=True, index=True)

    # ==================== TIMESTAMPS ====================
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # ==================== LEGACY FIELD (for backward compatibility) ====================
    owner_name = Column(String(200), nullable=True)

    # ==================== INDEXES ====================
    __table_args__ = (
        Index('idx_place_id', 'place_id'),
        Index('idx_phone', 'phone'),
        Index('idx_city_state', 'city', 'state'),
        Index('idx_category', 'category'),
        Index('idx_scraped_at', 'scraped_at'),
        Index('idx_search_query', 'search_query'),
        Index('idx_email', 'email'),
        Index('idx_rating', 'rating'),
        Index('idx_review_count', 'review_count'),
        Index('idx_founded_year', 'founded_year'),
        Index('idx_data_quality', 'data_quality_score'),
        Index('idx_sentiment_score', 'sentiment_score'),
        Index('idx_lead_score', 'lead_score'),
        Index('idx_last_verified', 'last_verified_at'),
    )

    def __repr__(self):
        return f"<BusinessLead(id={self.id}, name='{self.business_name}', city='{self.city}')>"

    def to_dict(self):
        """Convert model to dictionary with all fields."""
        return {
            # Core
            'id': self.id,
            'business_name': self.business_name,
            'category': self.category,
            'subcategories': self.subcategories,
            'business_type': self.business_type,

            # Location
            'full_address': self.full_address,
            'street': self.street,
            'city': self.city,
            'state': self.state,
            'country': self.country,
            'pin_code': self.pin_code,
            'latitude': self.latitude,
            'longitude': self.longitude,

            # Primary contact
            'phone': self.phone,
            'website': self.website,
            'email': self.email,

            # Multiple phones
            'phone_1': self.phone_1,
            'phone_2': self.phone_2,
            'phone_3': self.phone_3,

            # Multiple emails
            'email_1': self.email_1,
            'email_2': self.email_2,
            'email_3': self.email_3,

            # Contact persons
            'contact_name_1': self.contact_name_1,
            'contact_title_1': self.contact_title_1,
            'contact_email_1': self.contact_email_1,
            'contact_name_2': self.contact_name_2,
            'contact_title_2': self.contact_title_2,
            'contact_email_2': self.contact_email_2,
            'contact_name_3': self.contact_name_3,
            'contact_title_3': self.contact_title_3,
            'contact_email_3': self.contact_email_3,

            # Social media
            'social_facebook': self.social_facebook,
            'social_instagram': self.social_instagram,
            'social_twitter': self.social_twitter,
            'social_linkedin': self.social_linkedin,
            'social_youtube': self.social_youtube,
            'social_tiktok': self.social_tiktok,
            'social_pinterest': self.social_pinterest,
            'social_whatsapp': self.social_whatsapp,

            # Company insights
            'employees': self.employees,
            'employees_min': self.employees_min,
            'employees_max': self.employees_max,
            'founded_year': self.founded_year,
            'revenue': self.revenue,
            'revenue_min': self.revenue_min,
            'revenue_max': self.revenue_max,
            'company_type': self.company_type,
            'industry': self.industry,
            'description': self.description,

            # Ratings
            'rating': self.rating,
            'review_count': self.review_count,
            'reviews_1_star': self.reviews_1_star,
            'reviews_2_star': self.reviews_2_star,
            'reviews_3_star': self.reviews_3_star,
            'reviews_4_star': self.reviews_4_star,
            'reviews_5_star': self.reviews_5_star,
            'price_level': self.price_level,
            'reviews': self.reviews,
            'review_highlights': self.review_highlights,

            # Hours
            'hours_monday': self.hours_monday,
            'hours_tuesday': self.hours_tuesday,
            'hours_wednesday': self.hours_wednesday,
            'hours_thursday': self.hours_thursday,
            'hours_friday': self.hours_friday,
            'hours_saturday': self.hours_saturday,
            'hours_sunday': self.hours_sunday,
            'is_open_now': self.is_open_now,

            # Popular times
            'popular_times': self.popular_times,
            'busiest_day': self.busiest_day,
            'busiest_hour': self.busiest_hour,
            'quietest_day': self.quietest_day,
            'quietest_hour': self.quietest_hour,
            'typical_time_spent': self.typical_time_spent,
            'live_busyness': self.live_busyness,

            # Photos
            'photos': self.photos,
            'photo_count': self.photo_count,
            'main_photo': self.main_photo,

            # Metadata
            'place_id': self.place_id,
            'maps_url': self.maps_url,
            'cid': self.cid,
            'scraped_at': self.scraped_at.isoformat() if self.scraped_at else None,
            'search_query': self.search_query,
            'data_quality_score': self.data_quality_score,
            'data_source': self.data_source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,

            # Data freshness
            'last_verified_at': self.last_verified_at.isoformat() if self.last_verified_at else None,
            'verification_count': self.verification_count,
            'data_changed': self.data_changed,

            # Sentiment
            'sentiment_score': self.sentiment_score,
            'sentiment_label': self.sentiment_label,

            # Lead scoring
            'lead_score': self.lead_score,
            'lead_score_numeric': self.lead_score_numeric,

            # Legacy
            'owner_name': self.owner_name,
        }

    def to_export_dict(self):
        """Convert to dictionary optimized for export (39 columns as specified)."""
        return {
            'name': self.business_name,
            'site': self.website,
            'employees': self.employees,
            'founded_year': self.founded_year,
            'phone': self.phone,
            'revenue': self.revenue,
            'subtypes': ','.join(self.subcategories) if self.subcategories else None,
            'type': self.business_type,
            'category': self.category,
            'full_address': self.full_address,
            'street': self.street,
            'city': self.city,
            'state': self.state,
            'country': self.country,
            'rating': self.rating,
            'reviews': self.review_count,
            'reviews_1': self.reviews_1_star,
            'reviews_2': self.reviews_2_star,
            'reviews_3': self.reviews_3_star,
            'reviews_4': self.reviews_4_star,
            'reviews_5': self.reviews_5_star,
            'email_1': self.email_1 or self.email,
            'email_2': self.email_2,
            'email_3': self.email_3,
            'email_name_1': self.contact_name_1,
            'email_name_2': self.contact_name_2,
            'email_name_3': self.contact_name_3,
            'email_title_1': self.contact_title_1,
            'email_title_2': self.contact_title_2,
            'email_title_3': self.contact_title_3,
            'phone_1': self.phone_1 or self.phone,
            'phone_2': self.phone_2,
            'phone_3': self.phone_3,
            'facebook': self.social_facebook,
            'instagram': self.social_instagram,
            'linkedin': self.social_linkedin,
            'twitter': self.social_twitter,
            'youtube': self.social_youtube,
            'place_id': self.place_id,
            'lead_score': self.lead_score,
            'sentiment_score': self.sentiment_score,
            'main_photo': self.main_photo,
        }

    def calculate_quality_score(self):
        """Calculate data quality score based on field completeness."""
        # Weighted fields for quality score
        weighted_fields = {
            # High weight (core contact info)
            'business_name': 10,
            'phone': 10,
            'email': 10,
            'website': 8,

            # Medium weight (location)
            'full_address': 6,
            'city': 5,
            'state': 4,
            'country': 3,

            # Medium weight (business info)
            'category': 5,
            'rating': 4,
            'review_count': 4,

            # Lower weight (enriched data)
            'social_facebook': 3,
            'social_instagram': 3,
            'social_linkedin': 3,
            'employees': 4,
            'founded_year': 3,
            'revenue': 4,

            # Contact persons
            'contact_name_1': 3,
            'email_1': 3,
            'phone_1': 3,

            # New fields
            'photos': 2,
            'popular_times': 2,

            # Metadata
            'place_id': 2,
            'description': 2,
        }

        total_weight = sum(weighted_fields.values())
        earned_weight = 0

        for field, weight in weighted_fields.items():
            value = getattr(self, field, None)
            if value:
                earned_weight += weight

        self.data_quality_score = int((earned_weight / total_weight) * 100)
        return self.data_quality_score

    def has_social_media(self) -> bool:
        """Check if any social media link exists."""
        return any([
            self.social_facebook,
            self.social_instagram,
            self.social_twitter,
            self.social_linkedin,
            self.social_youtube,
        ])

    def has_contact_info(self) -> bool:
        """Check if contact information exists."""
        return any([self.phone, self.email, self.website])

    def get_all_phones(self) -> list:
        """Get all phone numbers as a list."""
        phones = []
        for p in [self.phone, self.phone_1, self.phone_2, self.phone_3]:
            if p and p not in phones:
                phones.append(p)
        return phones

    def get_all_emails(self) -> list:
        """Get all emails as a list."""
        emails = []
        for e in [self.email, self.email_1, self.email_2, self.email_3]:
            if e and e not in emails:
                emails.append(e)
        return emails

    def get_freshness_status(self) -> str:
        """Get data freshness status."""
        if not self.scraped_at:
            return "unknown"

        age = datetime.utcnow() - self.scraped_at
        if age.days <= 7:
            return "fresh"
        elif age.days <= 30:
            return "recent"
        elif age.days <= 90:
            return "stale"
        else:
            return "outdated"


class ScrapeJob(Base):
    """Model for tracking scraping jobs."""

    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Job Configuration
    search_query = Column(String(500), nullable=False)
    location = Column(String(200), nullable=True)
    max_results = Column(Integer, default=100)

    # Geo search parameters (NEW)
    geo_latitude = Column(Float, nullable=True)
    geo_longitude = Column(Float, nullable=True)
    geo_radius_km = Column(Float, nullable=True)

    # Enhanced options
    extract_emails = Column(Boolean, default=True)
    extract_social = Column(Boolean, default=True)
    extract_insights = Column(Boolean, default=True)
    extract_reviews = Column(Boolean, default=False)
    extract_photos = Column(Boolean, default=True)
    extract_popular_times = Column(Boolean, default=False)
    use_proxies = Column(Boolean, default=False)
    headless_mode = Column(Boolean, default=True)

    # Job Status
    status = Column(String(50), default='pending')  # pending, running, completed, failed, cancelled, paused
    leads_scraped = Column(Integer, default=0)
    leads_target = Column(Integer, default=0)

    # Progress tracking
    current_page = Column(Integer, default=0)
    current_item = Column(String(500), nullable=True)

    # Error Tracking
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Duration tracking
    duration_seconds = Column(Integer, nullable=True)

    # Resume State (JSON for checkpoint data)
    resume_state = Column(JSON, nullable=True)

    # Google Sheet URL (for direct export to sheets)
    google_sheet_url = Column(String(500), nullable=True)

    # Webhook notifications (NEW)
    webhook_url = Column(String(500), nullable=True)
    webhook_sent = Column(Boolean, default=False)

    # Relationship to leads
    leads = relationship("BusinessLead", backref="job", lazy="dynamic")

    def __repr__(self):
        return f"<ScrapeJob(id={self.id}, query='{self.search_query}', status='{self.status}')>"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'search_query': self.search_query,
            'location': self.location,
            'max_results': self.max_results,
            'geo_latitude': self.geo_latitude,
            'geo_longitude': self.geo_longitude,
            'geo_radius_km': self.geo_radius_km,
            'extract_emails': self.extract_emails,
            'extract_social': self.extract_social,
            'extract_insights': self.extract_insights,
            'extract_reviews': self.extract_reviews,
            'extract_photos': self.extract_photos,
            'extract_popular_times': self.extract_popular_times,
            'use_proxies': self.use_proxies,
            'headless_mode': self.headless_mode,
            'status': self.status,
            'leads_scraped': self.leads_scraped,
            'leads_target': self.leads_target,
            'current_page': self.current_page,
            'current_item': self.current_item,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'duration_seconds': self.duration_seconds,
            'progress_percent': self.get_progress_percent(),
            'google_sheet_url': self.google_sheet_url,
        }

    def get_progress_percent(self) -> int:
        """Calculate progress percentage."""
        if self.leads_target <= 0:
            return 0
        return min(100, int((self.leads_scraped / self.leads_target) * 100))


class ExportHistory(Base):
    """Model for tracking export history."""

    __tablename__ = "export_history"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Export details
    filename = Column(String(500), nullable=False)
    format = Column(String(50), nullable=False)  # csv, json, excel, google_sheets, cold_calling, email_campaign
    record_count = Column(Integer, default=0)
    file_size = Column(Integer, nullable=True)  # Size in bytes

    # Cloud upload (NEW)
    cloud_provider = Column(String(50), nullable=True)  # s3, gcs
    cloud_url = Column(String(1000), nullable=True)

    # Filters used
    filters = Column(JSON, nullable=True)

    # Status
    status = Column(String(50), default='completed')  # pending, completed, failed
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)

    def __repr__(self):
        return f"<ExportHistory(id={self.id}, file='{self.filename}', records={self.record_count})>"


class WebhookHistory(Base):
    """Model for tracking webhook notifications."""

    __tablename__ = "webhook_history"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Webhook details
    webhook_name = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False)
    url = Column(String(500), nullable=True)

    # Payload
    payload = Column(JSON, nullable=True)

    # Response
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)

    # Status
    success = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Timestamps
    sent_at = Column(DateTime, default=func.now(), nullable=False)

    def __repr__(self):
        return f"<WebhookHistory(id={self.id}, event='{self.event_type}', success={self.success})>"
