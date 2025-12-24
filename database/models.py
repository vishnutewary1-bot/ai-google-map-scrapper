"""Database models for Google Maps Scraper."""
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, JSON, Text, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class BusinessLead(Base):
    """Model for storing scraped business leads from Google Maps."""

    __tablename__ = "business_leads"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Core Fields (Always Extracted)
    business_name = Column(String(500), nullable=False)
    full_address = Column(Text, nullable=True)
    city = Column(String(200), nullable=True)
    state = Column(String(100), nullable=True)
    pin_code = Column(String(20), nullable=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(1000), nullable=True)
    category = Column(String(200), nullable=True)
    subcategories = Column(JSON, nullable=True)  # Array of subcategories

    # Extended Fields (Optional)
    email = Column(String(200), nullable=True)
    owner_name = Column(String(200), nullable=True)

    # Social Media Links
    social_facebook = Column(String(500), nullable=True)
    social_instagram = Column(String(500), nullable=True)
    social_twitter = Column(String(500), nullable=True)
    social_linkedin = Column(String(500), nullable=True)
    social_youtube = Column(String(500), nullable=True)

    # Business Hours
    hours_monday = Column(String(100), nullable=True)
    hours_tuesday = Column(String(100), nullable=True)
    hours_wednesday = Column(String(100), nullable=True)
    hours_thursday = Column(String(100), nullable=True)
    hours_friday = Column(String(100), nullable=True)
    hours_saturday = Column(String(100), nullable=True)
    hours_sunday = Column(String(100), nullable=True)
    is_open_now = Column(Boolean, nullable=True)

    # Metadata Fields
    place_id = Column(String(200), unique=True, nullable=True)  # Google's unique ID
    maps_url = Column(String(1000), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    scraped_at = Column(DateTime, default=func.now(), nullable=False)
    search_query = Column(String(500), nullable=True)
    data_quality_score = Column(Integer, default=0)  # 0-100 completeness score

    # Additional metadata
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    price_level = Column(String(10), nullable=True)  # $, $$, $$$, $$$$

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Indexes for faster queries
    __table_args__ = (
        Index('idx_place_id', 'place_id'),
        Index('idx_phone', 'phone'),
        Index('idx_city_state', 'city', 'state'),
        Index('idx_category', 'category'),
        Index('idx_scraped_at', 'scraped_at'),
        Index('idx_search_query', 'search_query'),
    )

    def __repr__(self):
        return f"<BusinessLead(id={self.id}, name='{self.business_name}', city='{self.city}')>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'business_name': self.business_name,
            'full_address': self.full_address,
            'city': self.city,
            'state': self.state,
            'pin_code': self.pin_code,
            'phone': self.phone,
            'website': self.website,
            'category': self.category,
            'subcategories': self.subcategories,
            'email': self.email,
            'owner_name': self.owner_name,
            'social_facebook': self.social_facebook,
            'social_instagram': self.social_instagram,
            'social_twitter': self.social_twitter,
            'social_linkedin': self.social_linkedin,
            'social_youtube': self.social_youtube,
            'hours_monday': self.hours_monday,
            'hours_tuesday': self.hours_tuesday,
            'hours_wednesday': self.hours_wednesday,
            'hours_thursday': self.hours_thursday,
            'hours_friday': self.hours_friday,
            'hours_saturday': self.hours_saturday,
            'hours_sunday': self.hours_sunday,
            'is_open_now': self.is_open_now,
            'place_id': self.place_id,
            'maps_url': self.maps_url,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'scraped_at': self.scraped_at.isoformat() if self.scraped_at else None,
            'search_query': self.search_query,
            'data_quality_score': self.data_quality_score,
            'rating': self.rating,
            'review_count': self.review_count,
            'price_level': self.price_level,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def calculate_quality_score(self):
        """Calculate data quality score based on field completeness."""
        fields = [
            self.business_name,
            self.full_address,
            self.city,
            self.state,
            self.pin_code,
            self.phone,
            self.website,
            self.category,
            self.email,
            self.place_id,
        ]

        filled_fields = sum(1 for field in fields if field)
        total_fields = len(fields)
        self.data_quality_score = int((filled_fields / total_fields) * 100)
        return self.data_quality_score


class ScrapeJob(Base):
    """Model for tracking scraping jobs."""

    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Job Configuration
    search_query = Column(String(500), nullable=False)
    location = Column(String(200), nullable=True)
    max_results = Column(Integer, default=100)

    # Job Status
    status = Column(String(50), default='pending')  # pending, running, completed, failed, paused
    leads_scraped = Column(Integer, default=0)
    leads_target = Column(Integer, default=0)

    # Error Tracking
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Resume State (JSON for checkpoint data)
    resume_state = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<ScrapeJob(id={self.id}, query='{self.search_query}', status='{self.status}')>"
