"""Website analysis without external APIs.

This module analyzes websites for:
- SSL certificate info
- Technology stack (from HTML/headers)
- Basic performance metrics
- Contact page detection
"""

import re
import ssl
import socket
from typing import Dict, List, Optional
from urllib.parse import urlparse
from datetime import datetime
from loguru import logger


class WebsiteAnalyzer:
    """
    Analyzes websites for:
    - SSL certificate info
    - Technology stack (from HTML/headers)
    - Basic performance metrics
    - Contact page detection
    """

    # Technology detection patterns
    TECH_PATTERNS = {
        # CMS
        'WordPress': [r'wp-content', r'wp-includes', r'/wp-json/', r'wordpress'],
        'Shopify': [r'cdn\.shopify\.com', r'shopify\.com', r'myshopify\.com'],
        'Wix': [r'wix\.com', r'wixsite\.com', r'_wix_'],
        'Squarespace': [r'squarespace\.com', r'static1\.squarespace', r'sqsp'],
        'Webflow': [r'webflow\.com', r'website-files\.com', r'webflow\.io'],
        'Drupal': [r'drupal\.js', r'/sites/default/files', r'drupal\.settings'],
        'Joomla': [r'joomla', r'/components/com_', r'/media/jui/'],
        'Ghost': [r'ghost\.io', r'ghost-', r'ghost\.org'],

        # E-commerce
        'WooCommerce': [r'woocommerce', r'/cart/', r'wc-ajax'],
        'Magento': [r'magento', r'mage/', r'/static/version'],
        'BigCommerce': [r'bigcommerce\.com', r'bigcommerce-'],
        'PrestaShop': [r'prestashop', r'/modules/'],

        # JavaScript frameworks
        'React': [r'react', r'__REACT_DEVTOOLS_GLOBAL_HOOK__', r'reactDOM'],
        'Vue.js': [r'vue\.js', r'__VUE__', r'vue\.min\.js'],
        'Angular': [r'angular', r'ng-', r'ng\.module'],
        'jQuery': [r'jquery', r'jQuery'],
        'Bootstrap': [r'bootstrap', r'btn-primary'],
        'Tailwind': [r'tailwindcss', r'tailwind'],

        # Analytics
        'Google Analytics': [r'google-analytics\.com', r'gtag/', r'ga\.js', r'analytics\.js'],
        'Google Tag Manager': [r'googletagmanager\.com', r'gtm\.js'],
        'Facebook Pixel': [r'connect\.facebook\.net', r'fbevents\.js', r'fbq\('],
        'Hotjar': [r'hotjar\.com', r'hj\('],
        'Mixpanel': [r'mixpanel\.com', r'mixpanel'],

        # Payment
        'Stripe': [r'stripe\.com', r'stripe\.js', r'Stripe\('],
        'PayPal': [r'paypal\.com', r'paypalobjects\.com'],
        'Square': [r'squareup\.com', r'square\.site'],
        'Razorpay': [r'razorpay\.com', r'razorpay'],

        # Chat/Support
        'Intercom': [r'intercom\.io', r'intercom'],
        'Zendesk': [r'zendesk\.com', r'zdassets\.com'],
        'LiveChat': [r'livechatinc\.com', r'livechat'],
        'Tawk.to': [r'tawk\.to', r'embed\.tawk'],
        'Crisp': [r'crisp\.chat', r'crisp\.im'],
        'Drift': [r'drift\.com', r'js\.drift\.com'],
        'HubSpot': [r'hubspot\.com', r'hs-scripts'],

        # Marketing
        'Mailchimp': [r'mailchimp\.com', r'chimpstatic\.com'],
        'ConvertKit': [r'convertkit\.com'],
        'ActiveCampaign': [r'activecampaign\.com'],

        # CDN
        'Cloudflare': [r'cloudflare\.com', r'cloudflareinsights'],
        'Fastly': [r'fastly\.net'],
        'AWS CloudFront': [r'cloudfront\.net'],
        'Akamai': [r'akamai', r'akamaized\.net'],

        # Hosting indicators
        'AWS': [r'amazonaws\.com', r'aws\.'],
        'Google Cloud': [r'googleapis\.com', r'storage\.googleapis'],
        'Azure': [r'azure\.com', r'azureedge\.net'],
        'Vercel': [r'vercel\.app', r'vercel\.com'],
        'Netlify': [r'netlify\.app', r'netlify\.com'],
        'Heroku': [r'herokuapp\.com'],
    }

    def __init__(self, page=None):
        """
        Initialize analyzer.

        Args:
            page: Optional Playwright page object for JS-rendered analysis
        """
        self.page = page

    def set_page(self, page):
        """Set the Playwright page object."""
        self.page = page

    def analyze(self, url: str) -> Dict:
        """
        Perform full website analysis.

        Args:
            url: Website URL to analyze

        Returns:
            Dict with ssl_info, technologies, performance, contact_pages
        """
        result = {
            'url': url,
            'analyzed_at': datetime.now().isoformat(),
            'ssl_info': {},
            'technologies': [],
            'performance': {},
            'contact_pages': [],
            'social_links': [],
            'has_contact_form': False,
            'page_title': None,
            'meta_description': None,
            'mobile_responsive': None,
        }

        # Parse URL
        try:
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'
            parsed = urlparse(url)
            domain = parsed.netloc
            if not domain:
                domain = parsed.path.split('/')[0]
        except Exception as e:
            logger.error(f"Invalid URL: {url} - {e}")
            return result

        result['domain'] = domain

        # SSL Analysis
        result['ssl_info'] = self._check_ssl(domain)

        # Page analysis (requires page object)
        if self.page:
            try:
                page_analysis = self._analyze_page(url)
                result.update(page_analysis)
            except Exception as e:
                logger.warning(f"Page analysis error: {e}")

        return result

    def _check_ssl(self, domain: str) -> Dict:
        """Check SSL certificate information."""
        try:
            context = ssl.create_default_context()

            with socket.create_connection((domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()

                    # Parse certificate dates
                    not_before = datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z')
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')

                    # Get issuer
                    issuer = {}
                    for item in cert.get('issuer', []):
                        if item[0]:
                            key, value = item[0]
                            issuer[key] = value

                    # Get subject
                    subject = {}
                    for item in cert.get('subject', []):
                        if item[0]:
                            key, value = item[0]
                            subject[key] = value

                    days_until_expiry = (not_after - datetime.now()).days

                    return {
                        'valid': True,
                        'issuer': issuer.get('organizationName', issuer.get('commonName', 'Unknown')),
                        'issued_to': subject.get('commonName', domain),
                        'issued_date': not_before.isoformat(),
                        'expires': not_after.isoformat(),
                        'days_until_expiry': days_until_expiry,
                        'is_expiring_soon': days_until_expiry < 30,
                        'is_expired': days_until_expiry < 0,
                    }
        except ssl.SSLError as e:
            return {'valid': False, 'error': 'SSL Error', 'details': str(e)}
        except socket.timeout:
            return {'valid': False, 'error': 'Connection timeout'}
        except socket.gaierror:
            return {'valid': False, 'error': 'DNS resolution failed'}
        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def _analyze_page(self, url: str) -> Dict:
        """Analyze page content for technologies and features."""
        result = {
            'technologies': [],
            'contact_pages': [],
            'social_links': [],
            'has_contact_form': False,
            'performance': {},
            'page_title': None,
            'meta_description': None,
            'mobile_responsive': None,
        }

        try:
            # Navigate and measure load time
            start_time = datetime.now()
            self.page.goto(url, timeout=30000, wait_until='networkidle')
            load_time = (datetime.now() - start_time).total_seconds()

            result['performance']['load_time_seconds'] = round(load_time, 2)

            # Get page content
            html = self.page.content()

            # Detect technologies
            for tech, patterns in self.TECH_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, html, re.IGNORECASE):
                        if tech not in result['technologies']:
                            result['technologies'].append(tech)
                        break

            # Find contact pages
            contact_patterns = [
                r'href=["\']([^"\']*contact[^"\']*)["\']',
                r'href=["\']([^"\']*about[^"\']*)["\']',
                r'href=["\']([^"\']*reach-us[^"\']*)["\']',
                r'href=["\']([^"\']*get-in-touch[^"\']*)["\']',
            ]

            for pattern in contact_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches[:3]:
                    if match and match not in result['contact_pages']:
                        result['contact_pages'].append(match)

            # Detect contact form
            if re.search(r'<form[^>]*contact|<form[^>]*email|type=["\']email["\']', html, re.IGNORECASE):
                result['has_contact_form'] = True

            # Find social links
            social_patterns = {
                'facebook': r'(?:facebook\.com|fb\.com)/([^"\'>\s]+)',
                'instagram': r'instagram\.com/([^"\'>\s]+)',
                'twitter': r'(?:twitter\.com|x\.com)/([^"\'>\s]+)',
                'linkedin': r'linkedin\.com/(?:company/|in/)?([^"\'>\s]+)',
                'youtube': r'youtube\.com/(?:channel/|c/|user/)?([^"\'>\s]+)',
                'tiktok': r'tiktok\.com/@?([^"\'>\s]+)',
            }

            for platform, pattern in social_patterns.items():
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    result['social_links'].append({
                        'platform': platform,
                        'handle': matches[0],
                        'url': f'https://{platform}.com/{matches[0]}'
                    })

            # Get page title
            title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
            if title_match:
                result['page_title'] = title_match.group(1).strip()

            # Get meta description
            desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', html, re.IGNORECASE)
            if not desc_match:
                desc_match = re.search(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']description["\']', html, re.IGNORECASE)
            if desc_match:
                result['meta_description'] = desc_match.group(1).strip()

            # Check mobile responsiveness (viewport meta tag)
            if re.search(r'<meta[^>]*viewport', html, re.IGNORECASE):
                result['mobile_responsive'] = True
            else:
                result['mobile_responsive'] = False

            # Check for common performance issues
            result['performance']['has_minified_js'] = bool(re.search(r'\.min\.js', html))
            result['performance']['has_minified_css'] = bool(re.search(r'\.min\.css', html))
            result['performance']['has_lazy_loading'] = bool(re.search(r'loading=["\']lazy["\']', html))

            # Count external resources
            js_count = len(re.findall(r'<script[^>]*src=', html))
            css_count = len(re.findall(r'<link[^>]*stylesheet', html))
            img_count = len(re.findall(r'<img[^>]*src=', html))

            result['performance']['js_files'] = js_count
            result['performance']['css_files'] = css_count
            result['performance']['images'] = img_count

        except Exception as e:
            logger.error(f"Page analysis error for {url}: {e}")

        return result

    def analyze_simple(self, url: str) -> Dict:
        """
        Simple analysis without browser (SSL only).

        Args:
            url: Website URL

        Returns:
            Dict with basic analysis
        """
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'

        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]

        return {
            'url': url,
            'domain': domain,
            'ssl_info': self._check_ssl(domain),
            'analyzed_at': datetime.now().isoformat()
        }


# Convenience functions
def analyze_website(url: str, page=None) -> Dict:
    """
    Quick function to analyze a website.

    Args:
        url: Website URL
        page: Optional Playwright page object

    Returns:
        Analysis results dictionary
    """
    analyzer = WebsiteAnalyzer(page)
    return analyzer.analyze(url)


def check_ssl(url: str) -> Dict:
    """
    Check SSL certificate for a website.

    Args:
        url: Website URL or domain

    Returns:
        SSL certificate information
    """
    analyzer = WebsiteAnalyzer()
    if not url.startswith(('http://', 'https://')):
        domain = url
    else:
        parsed = urlparse(url)
        domain = parsed.netloc
    return analyzer._check_ssl(domain)


def detect_technologies(html: str) -> List[str]:
    """
    Detect technologies from HTML content.

    Args:
        html: HTML content to analyze

    Returns:
        List of detected technology names
    """
    technologies = []
    for tech, patterns in WebsiteAnalyzer.TECH_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, html, re.IGNORECASE):
                if tech not in technologies:
                    technologies.append(tech)
                break
    return technologies


# Aliases
WebsiteAnalysisEngine = WebsiteAnalyzer
