# Google Maps AI Web Scraper - Product Requirements Document (PRD)

**Version:** 1.0  
**Date:** December 2024  
**Project Name:** MapLeads Pro  
**Author:** kk  

---

## 1. Executive Summary

Build a powerful, self-hosted Google Maps scraping tool for lead generation and competitor research across all industries. The tool should be scalable to 1M+ records, run on a personal VPS, operate within safe limits to avoid detection, and have zero ongoing costs (no paid proxies, APIs, or CAPTCHA services).

**Key Goals:**
- Extract business data from Google Maps at scale (5,000 leads/week target)
- All-industry support with customizable field selection
- Browser-based automation to mimic real user behavior
- Self-hosted on Hostinger VPS (16GB RAM, 8 cores)
- Zero operational costs
- Dashboard UI for management
- Export-ready for cold calling and CRM integration

---

## 2. System Architecture

### 2.1 Recommended Tech Stack

| Component | Technology | Reason |
|-----------|------------|--------|
| **Backend** | Python 3.11+ | Best scraping ecosystem, async support |
| **Browser Automation** | Playwright | Faster than Selenium, better stealth, built-in waits |
| **Database** | PostgreSQL | Handles 1M+ records, great for deduplication |
| **Task Queue** | Celery + Redis | Manages concurrent scraping jobs |
| **Web Dashboard** | FastAPI + React (or Streamlit for MVP) | Modern, fast, easy deployment |
| **Proxy Management** | Built-in rotation with free proxies | Zero cost requirement |
| **Export** | CSV, JSON, Google Sheets API | Multiple format support |

### 2.2 Infrastructure

```
┌─────────────────────────────────────────────────────────────┐
│                    HOSTINGER VPS                            │
│                 (16GB RAM, 8 Cores)                         │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Dashboard  │  │   Scraper   │  │     Database        │ │
│  │  (FastAPI)  │  │  Workers    │  │   (PostgreSQL)      │ │
│  │  Port 8000  │  │  (Celery)   │  │    Port 5432        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│         │               │                    │              │
│         └───────────────┼────────────────────┘              │
│                         │                                   │
│                  ┌──────┴──────┐                            │
│                  │    Redis    │                            │
│                  │  (Queue)    │                            │
│                  └─────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Data Fields Specification

### 3.1 Core Fields (Always Extracted)

| Field | Type | Source | Required |
|-------|------|--------|----------|
| `business_name` | String | Maps listing | ✅ |
| `full_address` | String | Maps listing | ✅ |
| `city` | String | Parsed from address | ✅ |
| `state` | String | Parsed from address | ✅ |
| `pin_code` | String | Parsed from address | ✅ |
| `phone` | String | Maps listing | ✅ |
| `website` | String | Maps listing | ⬚ |
| `category` | String | Maps listing | ✅ |
| `subcategories` | Array | Maps listing | ⬚ |

### 3.2 Extended Fields (Optional - User Selectable)

| Field | Type | Source | Extraction Method |
|-------|------|--------|-------------------|
| `email` | String | Website scrape | Regex patterns on website |
| `owner_name` | String | Website/About page | NLP extraction |
| `social_facebook` | String | Maps/Website | Link extraction |
| `social_instagram` | String | Maps/Website | Link extraction |
| `social_twitter` | String | Maps/Website | Link extraction |
| `social_linkedin` | String | Maps/Website | Link extraction |
| `social_youtube` | String | Maps/Website | Link extraction |
| `hours_monday` | String | Maps listing | Direct extraction |
| `hours_tuesday` | String | Maps listing | Direct extraction |
| `hours_wednesday` | String | Maps listing | Direct extraction |
| `hours_thursday` | String | Maps listing | Direct extraction |
| `hours_friday` | String | Maps listing | Direct extraction |
| `hours_saturday` | String | Maps listing | Direct extraction |
| `hours_sunday` | String | Maps listing | Direct extraction |
| `is_open_now` | Boolean | Calculated | Based on hours |

### 3.3 Metadata Fields (Auto-Generated)

| Field | Type | Description |
|-------|------|-------------|
| `place_id` | String | Google's unique identifier |
| `maps_url` | String | Direct link to listing |
| `latitude` | Float | Geo coordinates |
| `longitude` | Float | Geo coordinates |
| `scraped_at` | Datetime | Timestamp of extraction |
| `search_query` | String | Query that found this result |
| `data_quality_score` | Integer | 0-100 completeness score |

---

## 4. Search Capabilities

### 4.1 Search Methods

**Method 1: Keyword + Location Search**
```
Input: "restaurants in Mumbai"
Input: "doctors near Connaught Place Delhi"
Input: "hardware stores 110001"
```

**Method 2: Category-Based Search**
```
Input: Category = "Hospitals", Location = "Bangalore"
Input: Category = "Car Dealers", State = "Maharashtra"
```

**Method 3: Direct Place URLs**
```
Input: List of Google Maps URLs
- https://maps.google.com/maps?cid=XXXXX
- https://www.google.com/maps/place/XXXXX
```

**Method 4: Bulk Location Sweep**
```
Input: Category = "Pharmacies"
        Locations = [All India Pin Codes] or [State List]
        Radius = 5km per point
```

### 4.2 Geographic Scope Options

| Scope Level | Description | Implementation |
|-------------|-------------|----------------|
| **Pin Code** | Single pin code area | Direct search |
| **City** | Entire city | Grid-based with overlapping radius |
| **District** | District level | Multiple city searches |
| **State** | Full state | All districts iteration |
| **Pan-India** | Entire country | State-by-state queue |
| **Custom Radius** | X km from point | Lat/long + radius parameter |

### 4.3 Pre-Built Location Database

Include a database of:
- All India pin codes (19,000+)
- All cities with population data
- All state/district boundaries
- Major landmarks for reference points

---

## 5. Scale & Performance Specifications

### 5.1 Target Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| **Daily Volume** | 700-1,000 leads | Conservative for safety |
| **Weekly Volume** | 5,000 leads | Primary target |
| **Monthly Volume** | 20,000 leads | Sustainable pace |
| **Total Capacity** | 1,000,000+ records | Database designed for this |
| **Concurrent Workers** | 3-4 browsers | VPS optimized |
| **Avg Time per Lead** | 10-15 seconds | Including website scrape |

### 5.2 Resource Allocation (16GB RAM, 8 Cores)

```
PostgreSQL:     2GB RAM, 1 Core
Redis:          512MB RAM
Celery Workers: 8GB RAM, 4 Cores (4 workers × 2GB each)
Dashboard:      1GB RAM, 1 Core
System/Buffer:  4.5GB RAM, 2 Cores
```

---

## 6. Anti-Detection & Safety Measures

### 6.1 Browser Fingerprint Randomization

```python
# Randomize for each session:
- User Agent (rotate through 50+ real Chrome UAs)
- Viewport size (common resolutions)
- WebGL renderer
- Canvas fingerprint
- Timezone (match with proxy location)
- Language headers
- Platform details
```

### 6.2 Behavioral Mimicking

| Action | Human-Like Implementation |
|--------|---------------------------|
| **Scrolling** | Random speed, pauses, occasional scroll-up |
| **Mouse Movement** | Bezier curves, not straight lines |
| **Clicking** | Random offset within element, varied delays |
| **Typing** | Character-by-character with random delays |
| **Page Load Wait** | Random 2-5 seconds after load |
| **Session Duration** | 15-30 minutes, then new session |

### 6.3 Rate Limiting Strategy

```
Base delay between requests: 3-8 seconds (randomized)
Delay after every 10 results: 30-60 seconds
Delay after every 50 results: 2-5 minutes
Max requests per hour per IP: 100
Daily limit per browser profile: 500 searches
Cool-down after detection signal: 30-60 minutes
```

### 6.4 Free Proxy Strategy

Since budget is zero, implement:

1. **Rotating Free Proxies** (with health checks)
   - Sources: free-proxy-list.net, sslproxies.org
   - Auto-validate before use
   - Blacklist failed proxies
   
2. **Tor Network Integration** (optional fallback)
   - Rotate circuits every 10 requests
   - Slower but free and anonymous

3. **Direct Connection with VPN** (manual)
   - User can enable VPN on VPS
   - Rotate VPN servers daily

4. **No Proxy Mode** (for light usage)
   - Direct from VPS IP
   - Very conservative rate limits
   - Good for <100 leads/day

### 6.5 CAPTCHA Handling (Zero Budget)

| Strategy | Implementation |
|----------|----------------|
| **Avoidance** | Primary goal - slow down before CAPTCHA triggers |
| **Detection** | Identify CAPTCHA page, pause worker |
| **Manual Queue** | If CAPTCHA appears, add to manual review queue |
| **Session Reset** | Clear cookies, new fingerprint, wait 30 min |
| **Alternative Search** | Try different search query/location |

---

## 7. Deduplication System

### 7.1 Multi-Level Deduplication

**Level 1: Place ID (Exact Match)**
```sql
-- Google's unique identifier - guaranteed unique
UNIQUE INDEX ON place_id
```

**Level 2: Phone Number Normalization**
```python
# Normalize: +91-98765-43210 → 919876543210
# Flag duplicates with same phone, different listings
```

**Level 3: Fuzzy Name + Address Match**
```python
# Using rapidfuzz library
# "Sharma Medical Store" ≈ "Sharma Medicals" (85% match)
# Same pin code + 85% name match = likely duplicate
```

**Level 4: Geographic Proximity**
```sql
-- Businesses within 50 meters with similar names
-- Flag for manual review
```

### 7.2 Duplicate Handling Options

| Option | Action |
|--------|--------|
| `skip` | Don't scrape if exists |
| `update` | Re-scrape and update record |
| `merge` | Combine data from both sources |
| `flag` | Mark for manual review |

---

## 8. Data Enrichment Pipeline

### 8.1 Website Scraping for Emails

```python
# Priority order for email extraction:
1. Contact page (/contact, /contact-us, /reach-us)
2. About page (/about, /about-us)
3. Footer section (all pages)
4. Homepage body
5. Privacy policy (sometimes has contact)

# Email patterns to extract:
- Standard: name@domain.com
- Obfuscated: name [at] domain [dot] com
- Image-based: OCR if detected (optional)
```

### 8.2 Social Media Link Extraction

```python
# Extract from:
1. Google Maps listing (if available)
2. Website header/footer
3. Contact page

# Platforms to detect:
- Facebook (facebook.com, fb.com)
- Instagram (instagram.com)
- Twitter/X (twitter.com, x.com)
- LinkedIn (linkedin.com)
- YouTube (youtube.com)
- WhatsApp (wa.me, api.whatsapp.com)
```

### 8.3 Phone Verification (Basic)

```python
# Validation checks:
- Format validation (10 digits for India)
- Carrier detection (Jio, Airtel, etc.)
- Landline vs Mobile classification
- STD code validation for landlines
# Note: No actual calling/SMS verification (would cost money)
```

---

## 9. Filtering System

### 9.1 Pre-Scrape Filters (Search Level)

| Filter | Options |
|--------|---------|
| `category` | Select from Google's categories |
| `location_type` | City, State, Pin Code, Radius |
| `keyword_include` | Must contain these words |
| `keyword_exclude` | Must NOT contain these words |

### 9.2 Post-Scrape Filters (Data Level)

| Filter | Type | Example |
|--------|------|---------|
| `has_phone` | Boolean | Only with phone numbers |
| `has_website` | Boolean | Only with websites |
| `has_email` | Boolean | Only with extracted emails |
| `category_match` | String/Array | Specific categories only |
| `city_match` | String/Array | Specific cities only |
| `state_match` | String/Array | Specific states only |
| `data_quality_min` | Integer | Minimum completeness score |
| `scraped_after` | Date | Only recent scrapes |
| `scraped_before` | Date | Only older scrapes |

### 9.3 Smart Filters

```python
# Combination filters:
"high_quality_leads" = has_phone AND has_website AND data_quality > 70
"cold_call_ready" = has_phone AND phone_is_mobile
"email_campaign_ready" = has_email AND email_verified
```

---

## 10. Dashboard UI Specifications

### 10.1 Pages Required

**1. Dashboard Home**
- Total leads count
- Leads scraped today/week/month
- Active scraping jobs
- System health (CPU, RAM, Queue size)
- Quick stats by category/location

**2. New Scrape Job**
- Search method selector (Keyword, Category, URL, Bulk)
- Location input (with autocomplete)
- Field selection checkboxes
- Filter configuration
- Schedule options (now, later, recurring)
- Estimated time/volume preview

**3. Job Monitor**
- Active jobs list
- Progress bars
- Pause/Resume/Cancel controls
- Error logs per job
- Real-time lead counter

**4. Leads Database**
- Searchable/filterable table
- Column visibility toggle
- Bulk selection
- Inline editing
- Duplicate flags

**5. Export Center**
- Format selection (CSV, JSON, Excel, Google Sheets)
- Field selection for export
- Filter application
- Export history

**6. Settings**
- Rate limit configuration
- Proxy management
- Browser profile settings
- Database maintenance
- API keys (for future integrations)

### 10.2 UI Wireframe - New Scrape Job

```
┌─────────────────────────────────────────────────────────────┐
│  🔍 NEW SCRAPE JOB                                    [X]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Search Method:  ○ Keyword  ○ Category  ○ URLs  ○ Bulk     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Enter search query...                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Location:                                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🔍 Search city, state, or pin code...              │   │
│  └─────────────────────────────────────────────────────┘   │
│  ☑ Mumbai  ☑ Delhi  ☐ Add more...                         │
│                                                             │
│  Fields to Extract:                                         │
│  ☑ Basic (Name, Address, Phone, Website, Category)         │
│  ☐ Extended (Email, Social, Hours)                         │
│  ☐ All Available Fields                                    │
│                                                             │
│  Filters:                                                   │
│  ☐ Must have phone  ☐ Must have website  ☐ Must have email │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│  Estimated: ~2,500 leads  |  Time: ~8 hours                │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│              [ Cancel ]        [ 🚀 Start Scraping ]        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 11. Export Formats

### 11.1 Cold Calling Export

```csv
Name,Phone,City,Category,Website,Best_Call_Time
"ABC Traders","9876543210","Mumbai","Wholesaler","abc.com","10AM-6PM"
```

### 11.2 Email Campaign Export

```csv
Email,Name,Company,City,Website
"owner@abc.com","","ABC Traders","Mumbai","abc.com"
```

### 11.3 Full Data Export (JSON)

```json
{
  "export_date": "2024-12-15",
  "total_records": 5000,
  "leads": [
    {
      "business_name": "ABC Traders",
      "full_address": "123 Main St, Mumbai 400001",
      "phone": "9876543210",
      "email": "contact@abc.com",
      "website": "https://abc.com",
      "category": "Wholesaler",
      "social": {
        "facebook": "fb.com/abctraders",
        "instagram": null
      },
      "hours": {
        "monday": "9:00 AM - 8:00 PM",
        "sunday": "Closed"
      },
      "metadata": {
        "place_id": "ChIJ...",
        "scraped_at": "2024-12-15T10:30:00Z",
        "data_quality_score": 85
      }
    }
  ]
}
```

### 11.4 Google Sheets Integration

```python
# Auto-push to Google Sheets:
- Create new sheet per export
- Or append to existing sheet
- Real-time sync option (updates as scraped)
- Uses existing Google Apps Script auth
```

---

## 12. Logging & Monitoring

### 12.1 Log Levels

| Level | What to Log |
|-------|-------------|
| `INFO` | Job started, completed, exported |
| `DEBUG` | Each page scraped, each lead extracted |
| `WARNING` | Rate limit approached, slow response |
| `ERROR` | Failed extraction, timeout, blocked |
| `CRITICAL` | IP banned, CAPTCHA wall, system crash |

### 12.2 Monitoring Alerts

```python
# Alert conditions (shown in dashboard + optional email):
- Worker idle for >10 minutes
- Error rate >20% in last hour
- CAPTCHA detected
- Database near capacity (>80%)
- VPS resources critical (>90% RAM/CPU)
```

### 12.3 Job Resume System

```python
# On failure/pause, save state:
{
  "job_id": "uuid",
  "search_queries_completed": ["query1", "query2"],
  "search_queries_pending": ["query3", "query4"],
  "last_successful_url": "https://...",
  "leads_scraped": 1523,
  "last_checkpoint": "2024-12-15T10:30:00Z"
}

# Resume reads this state and continues from last checkpoint
```

---

## 13. Data Privacy Features

### 13.1 Auto-Cleanup

| Feature | Configuration |
|---------|---------------|
| `auto_delete_days` | Delete leads older than X days (default: off) |
| `anonymize_after` | Remove PII after X days, keep stats |
| `export_cleanup` | Delete export files after X days |

### 13.2 Data Isolation

- Each scrape job can be isolated in separate database schema
- Easy bulk delete by job/date/category
- No external data sharing (fully self-hosted)

---

## 14. Future Expansion Hooks

Build with these future features in mind (don't implement now, just ensure architecture supports):

1. **Multi-user support** - Different users, permissions, quotas
2. **API endpoint** - External apps can trigger scrapes
3. **Paid proxy integration** - Easy to add premium proxies later
4. **WhatsApp automation** - Send messages to scraped leads
5. **Email automation** - Campaign integration
6. **CRM sync** - HubSpot, Zoho, etc.
7. **Mobile app** - React Native dashboard
8. **Scheduled scrapes** - Cron-based recurring jobs
9. **Lead scoring** - AI-based quality scoring
10. **Competitor monitoring** - Track specific listings for changes

---

## 15. Installation & Deployment

### 15.1 VPS Requirements (Confirmed)

- **Provider:** Hostinger
- **RAM:** 16GB ✅
- **CPU:** 8 Cores ✅
- **Storage:** 100GB+ recommended
- **OS:** Ubuntu 22.04 LTS

### 15.2 Required Services

```bash
# Install these on VPS:
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Nginx (reverse proxy)
- Supervisor (process management)
- Playwright browsers (Chromium)
```

### 15.3 Directory Structure

```
/home/user/mapleads/
├── backend/
│   ├── api/              # FastAPI routes
│   ├── scraper/          # Playwright scraping logic
│   ├── workers/          # Celery tasks
│   ├── database/         # Models, migrations
│   └── utils/            # Helpers, constants
├── frontend/
│   ├── src/              # React components
│   └── public/           # Static assets
├── data/
│   ├── proxies/          # Proxy lists
│   ├── exports/          # Generated exports
│   └── logs/             # Application logs
├── config/
│   ├── settings.py       # Main configuration
│   └── locations.json    # India pin codes, cities
└── docker-compose.yml    # Optional containerization
```

---

## 16. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Uptime** | 95%+ | Dashboard accessible |
| **Success Rate** | 80%+ | Leads extracted / attempts |
| **Data Quality** | 70%+ avg score | Completeness of fields |
| **Speed** | 5,000/week | Sustainable without blocks |
| **Cost** | ₹0/month | No paid services |
| **Block Rate** | <5% | IP blocks or CAPTCHAs |

---

## 17. Development Phases

### Phase 1: Core Scraper (Week 1-2)
- [ ] Database setup (PostgreSQL)
- [ ] Basic Playwright scraper
- [ ] Keyword + Location search
- [ ] Core field extraction
- [ ] CSV export

### Phase 2: Anti-Detection (Week 2-3)
- [ ] Fingerprint randomization
- [ ] Rate limiting
- [ ] Free proxy rotation
- [ ] Session management
- [ ] Error recovery

### Phase 3: Dashboard MVP (Week 3-4)
- [ ] FastAPI backend
- [ ] Basic React/Streamlit UI
- [ ] Job creation
- [ ] Progress monitoring
- [ ] Export interface

### Phase 4: Advanced Features (Week 4-5)
- [ ] Email extraction from websites
- [ ] Social media extraction
- [ ] Advanced filtering
- [ ] Deduplication engine
- [ ] Bulk location sweep

### Phase 5: Polish & Scale (Week 5-6)
- [ ] Performance optimization
- [ ] Logging & monitoring
- [ ] Google Sheets integration
- [ ] Documentation
- [ ] Stress testing

---

## 18. Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| IP Block | High | Medium | Proxy rotation, rate limits |
| CAPTCHA Wall | Medium | High | Behavioral mimicking, pauses |
| Google ToS Action | Low | High | Stay under radar, no commercial resale |
| Data Loss | Low | High | Daily backups, transaction logs |
| VPS Overload | Medium | Medium | Resource monitoring, worker limits |

---

## 19. Commands Reference

### Start Scraping Job (CLI)
```bash
python manage.py scrape --query "restaurants" --location "Mumbai" --limit 1000
```

### Export Data (CLI)
```bash
python manage.py export --format csv --filter "has_phone=true" --output leads.csv
```

### Health Check (CLI)
```bash
python manage.py health
```

### Database Maintenance (CLI)
```bash
python manage.py deduplicate --strategy merge
python manage.py cleanup --older-than 90d
```

---

## 20. Support & Maintenance

### Daily Tasks
- Check dashboard for failed jobs
- Review CAPTCHA queue (if any)
- Monitor disk space

### Weekly Tasks
- Run deduplication
- Update proxy list
- Review rate limit effectiveness
- Export and backup data

### Monthly Tasks
- Update Playwright browsers
- Clean old exports
- Review success metrics
- Optimize slow queries

---

## Appendix A: India Location Data

The system should include pre-loaded data for:
- 19,100+ Pin Codes with city/state mapping
- 4,000+ Cities with population tiers
- 28 States + 8 Union Territories
- 700+ Districts
- Major landmarks for radius searches

---

## Appendix B: Google Maps Field Mapping

| UI Element | CSS Selector (may change) | Extraction Method |
|------------|---------------------------|-------------------|
| Business Name | `h1.fontHeadlineLarge` | Direct text |
| Address | `button[data-item-id="address"]` | aria-label |
| Phone | `button[data-item-id^="phone"]` | aria-label |
| Website | `a[data-item-id="authority"]` | href |
| Category | `button[jsaction*="category"]` | Direct text |
| Hours | `div[aria-label*="hours"]` | Expanded section |

*Note: Selectors change frequently. Implement fallback strategies and selector versioning.*

---

## Appendix C: Sample Search Queries

```
# High-value B2B queries:
"manufacturers in [city]"
"wholesalers near [location]"
"distributors [product] [state]"
"exporters [industry] india"

# Service businesses:
"doctors in [area]"
"lawyers near [court]"
"CA firms [city]"
"architects [location]"

# Retail:
"[product] shops in [city]"
"[brand] dealers [state]"
"showrooms near [landmark]"
```

---

**END OF PRD**

---

*This document is ready to be used with Claude Code or any AI coding assistant. Start with Phase 1 and iterate.*
