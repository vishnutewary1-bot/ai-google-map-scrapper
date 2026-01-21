# Comprehensive Code Review & Deployment Prompt
## MapLeads Pro - AI Google Maps Lead Scraper v2.0.0

---

## MISSION STATEMENT

You are a senior software engineer conducting an **unbiased, thorough code audit** of the MapLeads Pro Google Maps Scraper project. Your goal is to:

1. **Identify ALL issues, errors, bugs, and vulnerabilities** in the codebase
2. **Find duplicate code** across all files
3. **Identify unused code and unnecessary files**
4. **Create a complete remediation plan** to achieve 100% functionality
5. **Prepare the project for GitHub deployment** with full testing

---

## PHASE 1: COMPREHENSIVE CODE AUDIT

### 1.1 Security Audit (CRITICAL)

Review each file for security vulnerabilities:

**Files to Audit:**
```
api/app.py
api/middleware.py
api/routes/*.py
api/services/*.py
scraper/browser_engine.py
scraper/extractors/contact_extractor.py
config/settings.py
database/connection.py
```

**Check for:**
- [ ] Missing authentication/authorization on API endpoints
- [ ] JWT implementation status (declared but not used?)
- [ ] CSRF protection implementation
- [ ] SQL injection vulnerabilities in database queries
- [ ] XSS vulnerabilities in data handling
- [ ] Command injection in subprocess calls
- [ ] SSL/TLS verification disabled (`verify=False`)
- [ ] Hardcoded credentials or API keys
- [ ] Insecure default configurations
- [ ] Missing input validation/sanitization
- [ ] Rate limiting per user (not just global)
- [ ] Session management issues
- [ ] CORS misconfiguration

**Document in ISSUES.md:**
```markdown
## Security Issues
| ID | Severity | File:Line | Issue | Fix Required |
|----|----------|-----------|-------|--------------|
| SEC-001 | CRITICAL | file.py:123 | Description | Fix description |
```

---

### 1.2 Code Quality Audit

**Review ALL Python files for:**

**Error Handling:**
- [ ] Bare `except:` clauses (should be specific exceptions)
- [ ] Silent exception swallowing (`except: pass`)
- [ ] Missing error recovery logic
- [ ] Inconsistent error responses
- [ ] Missing try-except where needed

**Type Hints:**
- [ ] Missing type hints on functions
- [ ] Incorrect type hints (e.g., `Optional[callable]` should be `Optional[Callable]`)
- [ ] Missing return type annotations
- [ ] Generic types without parameters

**Code Style:**
- [ ] Inconsistent naming conventions
- [ ] Functions longer than 50 lines
- [ ] Classes with too many responsibilities
- [ ] Magic numbers/strings (should be constants)
- [ ] Commented-out code blocks
- [ ] TODO/FIXME comments that need resolution

**Import Issues:**
- [ ] `sys.path.insert` usage (anti-pattern)
- [ ] Circular imports
- [ ] Unused imports
- [ ] Import order violations (PEP 8)

---

### 1.3 Duplicate Code Detection

**Search for duplications in:**

```
# Priority files for duplication check:
utils/crm_integrations.py      # Known: _fetch_leads() duplicated at lines 236-256 and 455-473
scraper/extractors/*.py        # Email extraction logic
api/services/*.py              # Database query patterns
utils/exporter.py              # Export formatting
```

**Create duplication report:**
```markdown
## Duplicate Code
| ID | File 1 | Lines | File 2 | Lines | Description | Refactor To |
|----|--------|-------|--------|-------|-------------|-------------|
| DUP-001 | crm_integrations.py | 236-256 | crm_integrations.py | 455-473 | _fetch_leads() | Create single method |
```

---

### 1.4 Unused Code Detection

**Check for:**
- [ ] Unused functions/methods
- [ ] Unused classes
- [ ] Unused imports
- [ ] Dead code branches (unreachable code)
- [ ] Unused variables
- [ ] Unused configuration options

**Files to check:**
```
All .py files in:
- api/
- scraper/
- database/
- utils/
- config/
```

**Create unused code report:**
```markdown
## Unused Code
| ID | File | Line | Element | Type | Action |
|----|------|------|---------|------|--------|
| UNU-001 | file.py | 45 | function_name | Function | Remove/Integrate |
```

---

### 1.5 Unnecessary Files Detection

**Check if these files are needed:**
```
test_setup.py           # Is it a placeholder or functional?
migrate_database.py     # Is Alembic properly configured?
api/index.py           # Vercel-specific, needed for local?
*.bat files            # Windows-only, document or remove
```

**Check for:**
- [ ] Duplicate configuration files
- [ ] Obsolete documentation
- [ ] Temporary/test files committed
- [ ] Build artifacts that should be gitignored
- [ ] Cache files (*.pyc, __pycache__)

---

### 1.6 Integration Issues

**Features declared but not integrated:**

| Feature | Implementation File | Integration Point | Status |
|---------|--------------------|--------------------|--------|
| CAPTCHA Solver | `scraper/captcha_solver.py` | `browser_engine.py` | Check if called |
| Proxy Rotation | `scraper/proxy_manager.py` | `browser_engine.py` | Check if used |
| Job Pause/Resume | `api/routes/scraping.py` | `scrape_service.py` | Logic complete? |
| Scheduled Scraping | `scraper/scheduler.py` | API routes | Exposed? |
| Email Verification | `utils/email_verification.py` | Scraping pipeline | Auto-triggered? |
| Lead Scoring | `utils/lead_scoring.py` | Lead creation | Auto-calculated? |
| Deduplication | `utils/deduplicator.py` | Scraping pipeline | Integrated? |

---

### 1.7 Database Issues

**Review:**
```
database/models.py
database/connection.py
migrate_database.py
```

**Check for:**
- [ ] Missing foreign key relationships (BusinessLead → ScrapeJob)
- [ ] Missing indexes for frequently queried columns
- [ ] Alembic migration configuration
- [ ] Connection pooling settings
- [ ] Transaction handling
- [ ] N+1 query problems
- [ ] Missing `job_id` on BusinessLead

---

### 1.8 Frontend Issues

**Review:**
```
frontend/index.html
frontend/app.js
```

**Check for:**
- [ ] JavaScript errors
- [ ] Missing error handling in API calls
- [ ] XSS vulnerabilities
- [ ] Broken WebSocket reconnection
- [ ] Memory leaks (event listeners)
- [ ] Missing loading states
- [ ] Missing form validation
- [ ] Accessibility issues (ARIA, semantic HTML)

---

### 1.9 Configuration Issues

**Review:**
```
config/settings.py
.env.example
vercel.json
Procfile
nginx.conf
```

**Check for:**
- [ ] Hardcoded values that should be configurable
- [ ] Missing environment variable documentation
- [ ] Inconsistent default values
- [ ] Development settings in production configs
- [ ] Missing required environment variables

---

## PHASE 2: ISSUES & ERRORS DOCUMENTATION

Create `ISSUES.md` with the following structure:

```markdown
# MapLeads Pro - Code Issues & Errors Report
Generated: [DATE]
Reviewed by: [AI Code Reviewer]

## Summary
- Total Issues Found: [X]
- Critical: [X]
- High: [X]
- Medium: [X]
- Low: [X]

## Table of Contents
1. [Security Issues](#security-issues)
2. [Bugs & Errors](#bugs--errors)
3. [Code Quality Issues](#code-quality-issues)
4. [Duplicate Code](#duplicate-code)
5. [Unused Code](#unused-code)
6. [Unnecessary Files](#unnecessary-files)
7. [Integration Gaps](#integration-gaps)
8. [Performance Issues](#performance-issues)
9. [Documentation Gaps](#documentation-gaps)

---

## Security Issues
[Detailed table with all security findings]

## Bugs & Errors
[Runtime errors, logic errors, edge cases]

## Code Quality Issues
[Style, typing, naming, structure issues]

## Duplicate Code
[All duplications with locations and suggested refactoring]

## Unused Code
[Dead code, unused imports, unreachable branches]

## Unnecessary Files
[Files to remove or consolidate]

## Integration Gaps
[Features not properly connected]

## Performance Issues
[Memory leaks, N+1 queries, missing caching]

## Documentation Gaps
[Missing docstrings, outdated docs, missing API docs]
```

---

## PHASE 3: REMEDIATION PLAN

Create `REMEDIATION_PLAN.md`:

```markdown
# MapLeads Pro - Complete Remediation Plan
Target: 100% Functionality & GitHub Deployment Ready

## Phase 3.1: Critical Security Fixes (Priority 1)
Estimated: [Time based on issues found]

### Tasks:
1. [ ] Implement JWT Authentication
   - Add auth middleware
   - Create user model
   - Add login/register endpoints
   - Protect all API routes

2. [ ] Fix SSL Verification
   - Remove verify=False
   - Add proper certificate handling
   - Make configurable for development

3. [ ] Add Input Sanitization
   - Validate all user inputs
   - Sanitize HTML/script content
   - Add rate limiting per user

## Phase 3.2: Bug Fixes (Priority 2)
[List all bugs with fix approach]

## Phase 3.3: Integration Completion (Priority 3)
### Connect Disconnected Features:
1. [ ] Integrate CAPTCHA solver into browser_engine.py
2. [ ] Connect proxy_manager.py to browser_engine.py
3. [ ] Wire email_verification.py into scraping pipeline
4. [ ] Auto-trigger lead_scoring.py on new leads
5. [ ] Complete job pause/resume logic
6. [ ] Expose scheduler.py via API endpoints

## Phase 3.4: Code Cleanup (Priority 4)
1. [ ] Remove duplicate code
2. [ ] Remove unused code
3. [ ] Delete unnecessary files
4. [ ] Fix all type hints
5. [ ] Refactor large functions

## Phase 3.5: Database Improvements (Priority 5)
1. [ ] Add foreign key: BusinessLead.job_id → ScrapeJob.id
2. [ ] Configure Alembic migrations
3. [ ] Add missing indexes
4. [ ] Implement soft delete

## Phase 3.6: Testing (Priority 6 - CRITICAL BEFORE DEPLOYMENT)
### Unit Tests Required:
```
tests/
├── test_scraper/
│   ├── test_browser_engine.py
│   ├── test_unified_scraper.py
│   └── test_extractors/
│       ├── test_maps_extractor.py
│       ├── test_contact_extractor.py
│       ├── test_social_media_extractor.py
│       ├── test_company_insights_extractor.py
│       ├── test_review_extractor.py
│       └── test_popular_times_extractor.py
├── test_api/
│   ├── test_routes/
│   │   ├── test_scraping.py
│   │   ├── test_leads.py
│   │   ├── test_export.py
│   │   ├── test_analytics.py
│   │   └── test_websocket.py
│   └── test_services/
│       ├── test_scrape_service.py
│       ├── test_lead_service.py
│       └── test_export_service.py
├── test_database/
│   ├── test_connection.py
│   └── test_models.py
├── test_utils/
│   ├── test_exporter.py
│   ├── test_deduplicator.py
│   ├── test_lead_scoring.py
│   ├── test_email_verification.py
│   ├── test_notifications.py
│   └── test_crm_integrations.py
├── test_integration/
│   ├── test_full_scrape_flow.py
│   ├── test_export_flow.py
│   └── test_crm_sync.py
├── conftest.py
└── fixtures/
    ├── mock_html/
    │   └── google_maps_results.html
    └── mock_data/
        └── sample_leads.json
```

### Testing Requirements:
- [ ] Minimum 80% code coverage
- [ ] All extractors tested with mock HTML
- [ ] All API endpoints tested
- [ ] Database operations tested
- [ ] Export functionality verified for all formats
- [ ] Integration tests for complete flows

## Phase 3.7: Export Functionality Verification
### Verify ALL export formats work:
1. [ ] Excel (.xlsx) export with proper formatting
2. [ ] CSV export with correct encoding
3. [ ] JSON export with proper structure
4. [ ] Google Sheets export
5. [ ] Cold calling format
6. [ ] Email campaign format
7. [ ] CRM exports (HubSpot, Salesforce)
8. [ ] Airtable export
9. [ ] Notion export

### Test cases for each export:
- Empty data set
- Single lead
- 100 leads
- 10,000 leads (performance)
- Special characters in data
- Missing fields handling
- Unicode/international characters
```

---

## PHASE 4: LOCAL TESTING CHECKLIST

Before ANY deployment, complete these tests locally:

```markdown
# Pre-Deployment Local Testing Checklist

## Environment Setup
- [ ] Python 3.11+ installed
- [ ] Virtual environment created and activated
- [ ] All dependencies installed (requirements-local.txt)
- [ ] Playwright browsers installed
- [ ] .env file configured
- [ ] Database initialized

## Core Functionality Tests

### 1. Server Startup
- [ ] `python run.py` starts without errors
- [ ] API accessible at http://localhost:9000
- [ ] Health check passes: GET /api/health
- [ ] Swagger docs accessible: /docs

### 2. Scraping Tests
- [ ] Single search scrape works
- [ ] Multiple location scrape works
- [ ] Bulk scrape works
- [ ] Progress WebSocket updates work
- [ ] Scraping cancellation works
- [ ] Anti-detection measures working
- [ ] Rate limiting working

### 3. Data Extraction Tests
- [ ] Business name extracted correctly
- [ ] Address parsed correctly (test India, US, UK formats)
- [ ] Phone numbers extracted
- [ ] Emails extracted
- [ ] Social media links found
- [ ] Reviews extracted
- [ ] Coordinates extracted
- [ ] Place ID/CID extracted

### 4. Lead Management Tests
- [ ] Leads list loads (GET /api/leads)
- [ ] Filtering works (all 20+ filters)
- [ ] Pagination works
- [ ] Single lead detail works
- [ ] Bulk delete works
- [ ] Search works

### 5. Export Tests
- [ ] Excel export downloads correctly
- [ ] CSV export downloads correctly
- [ ] JSON export downloads correctly
- [ ] Google Sheets export works (if configured)
- [ ] Cold calling format correct
- [ ] Email campaign format correct
- [ ] Large export (1000+ leads) doesn't crash

### 6. Frontend Tests
- [ ] Dashboard loads with stats
- [ ] New Scrape form submits
- [ ] Jobs table updates in real-time
- [ ] Leads table with filtering
- [ ] Export modal works
- [ ] Analytics charts render
- [ ] Responsive design works
- [ ] No JavaScript console errors

### 7. Integration Tests (if configured)
- [ ] HubSpot sync works
- [ ] Salesforce sync works
- [ ] Airtable export works
- [ ] Notion export works
- [ ] Slack notifications work
- [ ] Discord notifications work
- [ ] Email notifications work

### 8. Error Handling Tests
- [ ] Invalid search query handled
- [ ] Network timeout handled
- [ ] Database connection error handled
- [ ] Invalid export format handled
- [ ] Rate limit exceeded handled

### 9. Performance Tests
- [ ] 100 leads scrape completes
- [ ] 1000 leads export completes
- [ ] Memory usage stable during long scrape
- [ ] No memory leaks in browser
```

---

## PHASE 5: GITHUB DEPLOYMENT PREPARATION

```markdown
# GitHub Deployment Checklist

## Repository Preparation
- [ ] All sensitive data removed from code
- [ ] .gitignore properly configured
- [ ] .env.example updated with all variables
- [ ] README.md comprehensive
- [ ] LICENSE file added
- [ ] CONTRIBUTING.md added (if open source)
- [ ] CHANGELOG.md created

## Code Quality
- [ ] All tests passing
- [ ] No linting errors (flake8/pylint)
- [ ] Type checking passes (mypy)
- [ ] Code formatted (black)
- [ ] Import sorting (isort)

## Documentation
- [ ] API documentation complete
- [ ] Setup instructions verified
- [ ] Deployment guides updated
- [ ] Environment variables documented
- [ ] Feature list accurate

## CI/CD Setup
- [ ] GitHub Actions workflow created
- [ ] Automated tests on PR
- [ ] Linting on PR
- [ ] Build verification

## Security
- [ ] No credentials in code
- [ ] Security headers configured
- [ ] Rate limiting active
- [ ] Input validation complete

## Files to Include:
```
.github/
├── workflows/
│   ├── ci.yml           # Run tests on PR
│   ├── lint.yml         # Code quality checks
│   └── deploy.yml       # Deployment automation
├── ISSUE_TEMPLATE/
│   ├── bug_report.md
│   └── feature_request.md
└── PULL_REQUEST_TEMPLATE.md
```

## .gitignore Should Include:
```
# Python
__pycache__/
*.py[cod]
*.so
.Python
venv/
.env

# Data
data/*.db
exports/
logs/

# IDE
.idea/
.vscode/
*.swp

# Testing
.coverage
htmlcov/
.pytest_cache/

# Build
dist/
build/
*.egg-info/
```
```

---

## EXECUTION INSTRUCTIONS

### Step 1: Run Full Audit
```bash
# Read every file systematically
# Document all issues in ISSUES.md
# Be thorough - check every function, every line
```

### Step 2: Create Issues Document
```bash
# Create ISSUES.md with all findings
# Categorize by severity
# Include exact file:line references
```

### Step 3: Create Remediation Plan
```bash
# Create REMEDIATION_PLAN.md
# Prioritize by impact
# Include specific implementation steps
```

### Step 4: Execute Fixes
```bash
# Fix critical security issues first
# Fix bugs second
# Complete integrations third
# Clean up code fourth
```

### Step 5: Write Tests
```bash
# Create test directory structure
# Write unit tests
# Write integration tests
# Achieve 80%+ coverage
```

### Step 6: Local Verification
```bash
# Run all tests: pytest
# Run linting: flake8
# Run type check: mypy
# Manual feature testing
```

### Step 7: GitHub Preparation
```bash
# Clean repository
# Update documentation
# Set up CI/CD
# Create initial release
```

---

## OUTPUT DELIVERABLES

After completing this audit, produce:

1. **ISSUES.md** - Complete list of all issues with severity ratings
2. **REMEDIATION_PLAN.md** - Step-by-step fix plan
3. **tests/** - Complete test suite
4. **Fixed code** - All issues resolved
5. **Updated documentation** - Accurate and complete
6. **.github/** - CI/CD workflows
7. **Deployment verification** - Local testing complete

---

## QUALITY GATES

Do not proceed to deployment until:

- [ ] ZERO critical security issues
- [ ] ZERO high-severity bugs
- [ ] ALL tests passing
- [ ] ALL export formats verified
- [ ] ALL features functional
- [ ] Documentation complete
- [ ] Code coverage > 80%

---

*This prompt ensures a thorough, unbiased review that will result in a production-ready, fully functional Google Maps scraper ready for GitHub deployment.*
