"""Company insights extraction (employees, founded year, revenue estimation)."""
import re
from typing import Dict, Optional, Tuple, List
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from loguru import logger
import time
from dataclasses import dataclass


@dataclass
class CompanyInsights:
    """Represents company insights data."""
    employees: Optional[str] = None  # Employee count or range
    employees_min: Optional[int] = None  # Minimum employees
    employees_max: Optional[int] = None  # Maximum employees
    founded_year: Optional[int] = None
    revenue: Optional[str] = None  # Revenue estimate
    revenue_min: Optional[float] = None  # Minimum revenue in USD
    revenue_max: Optional[float] = None  # Maximum revenue in USD
    company_type: Optional[str] = None  # LLC, Corp, etc.
    industry: Optional[str] = None
    headquarters: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        return {
            'employees': self.employees,
            'employees_min': self.employees_min,
            'employees_max': self.employees_max,
            'founded_year': self.founded_year,
            'revenue': self.revenue,
            'revenue_min': self.revenue_min,
            'revenue_max': self.revenue_max,
            'company_type': self.company_type,
            'industry': self.industry,
            'headquarters': self.headquarters,
            'description': self.description,
        }


class CompanyInsightsExtractor:
    """Extract company insights from websites and estimate revenue."""

    # Headers to mimic a real browser
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    # Employee count patterns
    EMPLOYEE_PATTERNS = [
        # "50+ employees", "100+ team members"
        r'(\d{1,5})\+?\s*(?:employees?|team\s*members?|staff|people|professionals?)',
        # "50-100 employees"
        r'(\d{1,5})\s*[-–to]\s*(\d{1,5})\s*(?:employees?|team\s*members?|staff|people)',
        # "team of 50+"
        r'team\s+of\s+(\d{1,5})\+?',
        # "over 100 employees"
        r'(?:over|more than|around|approximately|about)\s*(\d{1,5})\s*(?:employees?|people|staff)',
        # LinkedIn style ranges
        r'(\d{1,5})-(\d{1,5})\s*employees?',
    ]

    # Founded year patterns
    FOUNDED_PATTERNS = [
        # "Founded in 2010", "Established 2010"
        r'(?:founded|established|since|started|est\.?|incorporated|formed)\s*(?:in\s*)?(\d{4})',
        # "Since 2010"
        r'since\s+(\d{4})',
        # "2010 - Present" in about sections
        r'(\d{4})\s*[-–]\s*(?:present|current|now|today)',
        # "(c) 2010-2024" in footers
        r'[©®]\s*(\d{4})',
        # "Company Name (2010)"
        r'\((\d{4})\)',
    ]

    # Revenue indicators by category/size
    REVENUE_ESTIMATION = {
        # Based on employee count
        'employees': {
            (1, 10): ('$100K - $1M', 100000, 1000000),
            (11, 50): ('$1M - $10M', 1000000, 10000000),
            (51, 200): ('$10M - $50M', 10000000, 50000000),
            (201, 500): ('$50M - $200M', 50000000, 200000000),
            (501, 1000): ('$200M - $500M', 200000000, 500000000),
            (1001, 5000): ('$500M - $2B', 500000000, 2000000000),
            (5001, float('inf')): ('$2B+', 2000000000, None),
        },
        # Based on review count (Google Maps)
        'reviews': {
            (0, 10): ('$50K - $200K', 50000, 200000),
            (11, 50): ('$200K - $500K', 200000, 500000),
            (51, 200): ('$500K - $2M', 500000, 2000000),
            (201, 500): ('$2M - $5M', 2000000, 5000000),
            (501, 1000): ('$5M - $10M', 5000000, 10000000),
            (1001, 5000): ('$10M - $50M', 10000000, 50000000),
            (5001, float('inf')): ('$50M+', 50000000, None),
        },
    }

    # Business type patterns
    BUSINESS_TYPE_PATTERNS = [
        (r'\b(?:LLC|L\.L\.C\.)\b', 'LLC'),
        (r'\b(?:Inc\.|Incorporated)\b', 'Inc.'),
        (r'\b(?:Corp\.|Corporation)\b', 'Corp.'),
        (r'\b(?:Ltd\.|Limited)\b', 'Ltd.'),
        (r'\b(?:Pvt\.|Private)\b', 'Private'),
        (r'\b(?:PLC|P\.L\.C\.)\b', 'PLC'),
        (r'\b(?:GmbH)\b', 'GmbH'),
        (r'\b(?:LLP|L\.L\.P\.)\b', 'LLP'),
        (r'\b(?:Sole Proprietorship)\b', 'Sole Proprietorship'),
        (r'\b(?:Partnership)\b', 'Partnership'),
    ]

    def __init__(self, timeout: int = 10, max_retries: int = 2):
        """
        Initialize the company insights extractor.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def extract_from_website(self, website_url: str) -> CompanyInsights:
        """
        Extract company insights from a website.

        Args:
            website_url: The business website URL

        Returns:
            CompanyInsights object with extracted data
        """
        insights = CompanyInsights()

        if not website_url:
            return insights

        try:
            # Normalize URL
            if not website_url.startswith(('http://', 'https://')):
                website_url = 'https://' + website_url

            # Fetch the main page
            html_content = self._fetch_page(website_url)
            if not html_content:
                return insights

            soup = BeautifulSoup(html_content, 'html.parser')
            page_text = soup.get_text(separator=' ')

            # Extract from main page
            self._extract_from_page(soup, page_text, insights)

            # Check about page for more info
            about_pages = self._find_about_pages(soup, website_url)
            for page_url in about_pages[:2]:
                try:
                    about_html = self._fetch_page(page_url)
                    if about_html:
                        about_soup = BeautifulSoup(about_html, 'html.parser')
                        about_text = about_soup.get_text(separator=' ')
                        self._extract_from_page(about_soup, about_text, insights)
                except Exception:
                    continue

            # Extract company description
            if not insights.description:
                insights.description = self._extract_description(soup)

            # Extract company type from business name or page
            if not insights.company_type:
                insights.company_type = self._extract_company_type(page_text)

            logger.info(f"Extracted insights from {website_url}: employees={insights.employees}, founded={insights.founded_year}")

        except Exception as e:
            logger.warning(f"Error extracting company insights from {website_url}: {e}")

        return insights

    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content with retries."""
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    verify=False
                )
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                    continue
                logger.debug(f"Failed to fetch {url}: {e}")
                return None
        return None

    def _extract_from_page(self, soup: BeautifulSoup, page_text: str, insights: CompanyInsights):
        """Extract insights from page content."""
        # Extract employees if not already found
        if not insights.employees:
            emp_data = self._extract_employees(page_text)
            if emp_data:
                insights.employees = emp_data[0]
                insights.employees_min = emp_data[1]
                insights.employees_max = emp_data[2]

        # Extract founded year if not already found
        if not insights.founded_year:
            insights.founded_year = self._extract_founded_year(page_text)

        # Extract from structured data
        self._extract_from_structured_data(soup, insights)

    def _extract_employees(self, text: str) -> Optional[Tuple[str, Optional[int], Optional[int]]]:
        """Extract employee count from text."""
        for pattern in self.EMPLOYEE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # Range format
                    try:
                        min_emp = int(match[0])
                        max_emp = int(match[1]) if len(match) > 1 else None

                        if min_emp > 0 and min_emp < 1000000:  # Sanity check
                            if max_emp:
                                return (f"{min_emp}-{max_emp}", min_emp, max_emp)
                            else:
                                return (f"{min_emp}+", min_emp, None)
                    except (ValueError, IndexError):
                        continue
                else:
                    # Single value
                    try:
                        count = int(match)
                        if 0 < count < 1000000:  # Sanity check
                            return (str(count), count, count)
                    except ValueError:
                        continue

        return None

    def _extract_founded_year(self, text: str) -> Optional[int]:
        """Extract founded year from text."""
        current_year = 2024  # Update as needed

        for pattern in self.FOUNDED_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    year = int(match)
                    # Sanity check: year should be reasonable
                    if 1800 <= year <= current_year:
                        return year
                except ValueError:
                    continue

        return None

    def _extract_from_structured_data(self, soup: BeautifulSoup, insights: CompanyInsights):
        """Extract from JSON-LD structured data."""
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string or '{}')
                self._parse_json_ld(data, insights)
            except:
                continue

    def _parse_json_ld(self, data, insights: CompanyInsights):
        """Parse JSON-LD data for company insights."""
        if isinstance(data, dict):
            # Organization schema
            if data.get('@type') in ['Organization', 'LocalBusiness', 'Corporation', 'Company']:
                if not insights.founded_year and data.get('foundingDate'):
                    try:
                        year = int(str(data['foundingDate'])[:4])
                        if 1800 <= year <= 2024:
                            insights.founded_year = year
                    except:
                        pass

                if not insights.employees and data.get('numberOfEmployees'):
                    emp = data['numberOfEmployees']
                    if isinstance(emp, dict):
                        if emp.get('minValue') and emp.get('maxValue'):
                            insights.employees = f"{emp['minValue']}-{emp['maxValue']}"
                            insights.employees_min = int(emp['minValue'])
                            insights.employees_max = int(emp['maxValue'])
                        elif emp.get('value'):
                            insights.employees = str(emp['value'])
                            insights.employees_min = int(emp['value'])
                            insights.employees_max = int(emp['value'])
                    elif isinstance(emp, (int, str)):
                        insights.employees = str(emp)
                        try:
                            insights.employees_min = int(emp)
                            insights.employees_max = int(emp)
                        except:
                            pass

                if not insights.description and data.get('description'):
                    insights.description = data['description'][:500]

                if not insights.headquarters and data.get('address'):
                    addr = data['address']
                    if isinstance(addr, dict):
                        parts = [addr.get('addressLocality'), addr.get('addressRegion'), addr.get('addressCountry')]
                        insights.headquarters = ', '.join(p for p in parts if p)
                    elif isinstance(addr, str):
                        insights.headquarters = addr

            # Recurse into nested structures
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    if isinstance(value, dict):
                        self._parse_json_ld(value, insights)
                    else:
                        for item in value:
                            if isinstance(item, dict):
                                self._parse_json_ld(item, insights)

    def _find_about_pages(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Find about page URLs."""
        pages = []
        keywords = ['about', 'about-us', 'company', 'who-we-are', 'our-story', 'history']

        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '').lower()
            text = a_tag.get_text().lower()

            if any(keyword in href or keyword in text for keyword in keywords):
                full_url = urljoin(base_url, a_tag['href'])
                if full_url not in pages:
                    pages.append(full_url)

        return pages

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract company description from meta tags or page content."""
        # Try meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content'][:500]

        # Try og:description
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            return og_desc['content'][:500]

        # Try first paragraph in about section
        about_section = soup.find(['section', 'div'], class_=lambda c: c and 'about' in str(c).lower())
        if about_section:
            first_p = about_section.find('p')
            if first_p:
                return first_p.get_text().strip()[:500]

        return None

    def _extract_company_type(self, text: str) -> Optional[str]:
        """Extract company type from text."""
        for pattern, comp_type in self.BUSINESS_TYPE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return comp_type
        return None

    def estimate_revenue(
        self,
        employee_count: Optional[int] = None,
        review_count: Optional[int] = None,
        rating: Optional[float] = None,
        category: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[float], Optional[float]]:
        """
        Estimate revenue based on available data.

        Args:
            employee_count: Number of employees
            review_count: Number of Google reviews
            rating: Google rating
            category: Business category

        Returns:
            Tuple of (revenue_string, min_revenue, max_revenue)
        """
        # Primary: Use employee count if available
        if employee_count:
            for (min_emp, max_emp), (rev_str, rev_min, rev_max) in self.REVENUE_ESTIMATION['employees'].items():
                if min_emp <= employee_count <= max_emp:
                    return (rev_str, rev_min, rev_max)

        # Secondary: Use review count
        if review_count:
            for (min_rev, max_rev), (rev_str, rev_min, rev_max) in self.REVENUE_ESTIMATION['reviews'].items():
                if min_rev <= review_count <= max_rev:
                    # Adjust for rating if available
                    if rating:
                        multiplier = rating / 4.0  # 4.0 as baseline
                        if rev_min:
                            rev_min = int(rev_min * multiplier)
                        if rev_max:
                            rev_max = int(rev_max * multiplier)
                        return (rev_str, rev_min, rev_max)
                    return (rev_str, rev_min, rev_max)

        return (None, None, None)

    def extract_from_google_maps_data(
        self,
        review_count: Optional[int] = None,
        rating: Optional[float] = None,
        category: Optional[str] = None,
        website_insights: Optional[CompanyInsights] = None
    ) -> Dict:
        """
        Combine Google Maps data with website insights for comprehensive company info.

        Args:
            review_count: Number of Google reviews
            rating: Google rating
            category: Business category
            website_insights: CompanyInsights from website extraction

        Returns:
            Dictionary with all company insights
        """
        result = {
            'employees': None,
            'employees_min': None,
            'employees_max': None,
            'founded_year': None,
            'revenue': None,
            'revenue_min': None,
            'revenue_max': None,
            'company_type': None,
            'industry': category,
            'description': None,
        }

        # Merge with website insights if available
        if website_insights:
            result.update({
                'employees': website_insights.employees,
                'employees_min': website_insights.employees_min,
                'employees_max': website_insights.employees_max,
                'founded_year': website_insights.founded_year,
                'company_type': website_insights.company_type,
                'description': website_insights.description,
            })

        # Estimate revenue
        emp_count = result.get('employees_min') or result.get('employees_max')
        rev_str, rev_min, rev_max = self.estimate_revenue(
            employee_count=emp_count,
            review_count=review_count,
            rating=rating,
            category=category
        )

        result['revenue'] = rev_str
        result['revenue_min'] = rev_min
        result['revenue_max'] = rev_max

        return result


# Singleton instance for easy importing
company_insights_extractor = CompanyInsightsExtractor()
