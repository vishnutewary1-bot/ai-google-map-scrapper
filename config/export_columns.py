"""Export column definitions - single source of truth for all export formats.

This module centralizes all column definitions that were previously
scattered across multiple files (exporter.py, models.py, etc.).

Column format: (export_name, db_field, display_name, width)
"""

# Standard 39-column export format
EXPORT_COLUMNS = [
    # Core business info
    ('name', 'business_name', 'Business Name', 30),
    ('site', 'website', 'Website', 35),
    ('employees', 'employees', 'Employees', 15),
    ('founded_year', 'founded_year', 'Founded', 10),
    ('phone', 'phone', 'Phone', 18),
    ('revenue', 'revenue', 'Revenue', 18),
    ('subtypes', 'subcategories', 'Subtypes', 25),
    ('type', 'business_type', 'Type', 20),
    ('category', 'category', 'Category', 20),

    # Location
    ('full_address', 'full_address', 'Full Address', 45),
    ('street', 'street', 'Street', 30),
    ('city', 'city', 'City', 18),
    ('state', 'state', 'State', 15),
    ('country', 'country', 'Country', 15),

    # Ratings & Reviews
    ('rating', 'rating', 'Rating', 10),
    ('reviews', 'review_count', 'Reviews', 12),
    ('reviews_1', 'reviews_1_star', '1 Star', 10),
    ('reviews_2', 'reviews_2_star', '2 Star', 10),
    ('reviews_3', 'reviews_3_star', '3 Star', 10),
    ('reviews_4', 'reviews_4_star', '4 Star', 10),
    ('reviews_5', 'reviews_5_star', '5 Star', 10),

    # Emails
    ('email_1', 'email_1', 'Email 1', 30),
    ('email_2', 'email_2', 'Email 2', 30),
    ('email_3', 'email_3', 'Email 3', 30),

    # Email contact names
    ('email_name_1', 'contact_name_1', 'Contact Name 1', 22),
    ('email_name_2', 'contact_name_2', 'Contact Name 2', 22),
    ('email_name_3', 'contact_name_3', 'Contact Name 3', 22),

    # Email contact titles
    ('email_title_1', 'contact_title_1', 'Contact Title 1', 20),
    ('email_title_2', 'contact_title_2', 'Contact Title 2', 20),
    ('email_title_3', 'contact_title_3', 'Contact Title 3', 20),

    # Multiple phones
    ('phone_1', 'phone_1', 'Phone 1', 18),
    ('phone_2', 'phone_2', 'Phone 2', 18),
    ('phone_3', 'phone_3', 'Phone 3', 18),

    # Social media
    ('facebook', 'social_facebook', 'Facebook', 35),
    ('instagram', 'social_instagram', 'Instagram', 35),
    ('linkedin', 'social_linkedin', 'LinkedIn', 35),
    ('twitter', 'social_twitter', 'Twitter', 35),
    ('youtube', 'social_youtube', 'YouTube', 35),

    # Metadata
    ('place_id', 'place_id', 'Place ID', 25),
]

# Extended columns for full export (50+ columns)
FULL_EXPORT_COLUMNS = EXPORT_COLUMNS + [
    ('maps_url', 'maps_url', 'Maps URL', 50),
    ('latitude', 'latitude', 'Latitude', 12),
    ('longitude', 'longitude', 'Longitude', 12),
    ('pin_code', 'pin_code', 'PIN Code', 12),
    ('price_level', 'price_level', 'Price Level', 12),
    ('data_quality_score', 'data_quality_score', 'Quality Score', 12),
    ('scraped_at', 'scraped_at', 'Scraped At', 20),
    ('search_query', 'search_query', 'Search Query', 25),
    ('description', 'description', 'Description', 50),
    ('hours_monday', 'hours_monday', 'Mon Hours', 15),
    ('hours_tuesday', 'hours_tuesday', 'Tue Hours', 15),
    ('hours_wednesday', 'hours_wednesday', 'Wed Hours', 15),
    ('hours_thursday', 'hours_thursday', 'Thu Hours', 15),
    ('hours_friday', 'hours_friday', 'Fri Hours', 15),
    ('hours_saturday', 'hours_saturday', 'Sat Hours', 15),
    ('hours_sunday', 'hours_sunday', 'Sun Hours', 15),
]

# Cold calling optimized format
COLD_CALLING_COLUMNS = [
    ('name', 'business_name', 'Business Name', 30),
    ('phone_1', 'phone_1', 'Phone 1', 18),
    ('phone_2', 'phone_2', 'Phone 2', 18),
    ('phone_3', 'phone_3', 'Phone 3', 18),
    ('contact_name', 'contact_name_1', 'Contact Name', 22),
    ('contact_title', 'contact_title_1', 'Contact Title', 20),
    ('city', 'city', 'City', 18),
    ('state', 'state', 'State', 15),
    ('category', 'category', 'Category', 20),
    ('website', 'website', 'Website', 35),
    ('rating', 'rating', 'Rating', 10),
    ('reviews', 'review_count', 'Reviews', 12),
]

# Email campaign optimized format
EMAIL_CAMPAIGN_COLUMNS = [
    ('name', 'business_name', 'Business Name', 30),
    ('email_1', 'email_1', 'Email 1', 30),
    ('email_2', 'email_2', 'Email 2', 30),
    ('email_3', 'email_3', 'Email 3', 30),
    ('contact_name_1', 'contact_name_1', 'Contact Name 1', 22),
    ('contact_name_2', 'contact_name_2', 'Contact Name 2', 22),
    ('contact_title_1', 'contact_title_1', 'Contact Title 1', 20),
    ('website', 'website', 'Website', 35),
    ('city', 'city', 'City', 18),
    ('state', 'state', 'State', 15),
    ('category', 'category', 'Category', 20),
    ('employees', 'employees', 'Employees', 15),
    ('revenue', 'revenue', 'Revenue', 18),
]

# Social media focused format
SOCIAL_MEDIA_COLUMNS = [
    ('name', 'business_name', 'Business Name', 30),
    ('facebook', 'social_facebook', 'Facebook', 40),
    ('instagram', 'social_instagram', 'Instagram', 40),
    ('linkedin', 'social_linkedin', 'LinkedIn', 40),
    ('twitter', 'social_twitter', 'Twitter', 40),
    ('youtube', 'social_youtube', 'YouTube', 40),
    ('website', 'website', 'Website', 35),
    ('city', 'city', 'City', 18),
    ('category', 'category', 'Category', 20),
]

# WhatsApp outreach format
WHATSAPP_COLUMNS = [
    ('name', 'business_name', 'Business Name', 30),
    ('whatsapp_number', 'whatsapp_number', 'WhatsApp Number', 20),
    ('whatsapp_link', 'whatsapp_link', 'WhatsApp Link', 50),
    ('phone_1', 'phone_1', 'Phone 1', 18),
    ('contact_name', 'contact_name_1', 'Contact Name', 22),
    ('city', 'city', 'City', 18),
    ('category', 'category', 'Category', 20),
    ('website', 'website', 'Website', 35),
]

# Mapping of format names to column definitions
COLUMN_FORMATS = {
    'standard': EXPORT_COLUMNS,
    'full': FULL_EXPORT_COLUMNS,
    'cold_calling': COLD_CALLING_COLUMNS,
    'email_campaign': EMAIL_CAMPAIGN_COLUMNS,
    'social_media': SOCIAL_MEDIA_COLUMNS,
    'whatsapp': WHATSAPP_COLUMNS,
}


def get_columns(format_name: str = 'standard') -> list:
    """
    Get column definitions for a specific format.

    Args:
        format_name: One of 'standard', 'full', 'cold_calling',
                    'email_campaign', 'social_media', 'whatsapp'

    Returns:
        List of column tuples (export_name, db_field, display_name, width)
    """
    return COLUMN_FORMATS.get(format_name, EXPORT_COLUMNS)


def get_fieldnames(format_name: str = 'standard') -> list:
    """
    Get just the export field names for a format.

    Args:
        format_name: Format name

    Returns:
        List of export field names
    """
    return [col[0] for col in get_columns(format_name)]


def get_display_names(format_name: str = 'standard') -> list:
    """
    Get just the display names for a format.

    Args:
        format_name: Format name

    Returns:
        List of display names
    """
    return [col[2] for col in get_columns(format_name)]


def get_column_widths(format_name: str = 'standard') -> dict:
    """
    Get a mapping of field names to column widths.

    Args:
        format_name: Format name

    Returns:
        Dict mapping export names to widths
    """
    return {col[0]: col[3] for col in get_columns(format_name)}
