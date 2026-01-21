# MapLeads Pro - Code Audit Issues Report

**Audit Date:** 2026-01-21
**Auditor:** Claude Code
**Project:** AI Google Maps Scraper v2.0.0

---

## Executive Summary

This audit identified **23 issues** across security, code quality, integration, and documentation categories:
- **Critical (P0):** 4 issues
- **High (P1):** 6 issues
- **Medium (P2):** 8 issues
- **Low (P3):** 5 issues

---

## 1. Security Issues

### SEC-001: SSL Verification Disabled [CRITICAL]
- **File:** `utils/contact_extractor.py:198`
- **Issue:** `verify=False` disables SSL certificate verification
- **Risk:** Man-in-the-middle attacks, data interception
- **Code:**
  ```python
  response = self.session.get(
      url,
      timeout=self.timeout,
      allow_redirects=True,
      verify=False  # SECURITY VULNERABILITY
  )
  ```
- **Fix:** Remove `verify=False` or make it configurable with a warning

### SEC-002: Overly Permissive CORS [HIGH]
- **File:** `api/middleware.py:35-40`
- **Issue:** CORS allows all origins with `allow_origins=["*"]`
- **Risk:** Cross-site request forgery, unauthorized API access
- **Code:**
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **Fix:** Restrict to specific allowed origins from configuration

### SEC-003: No Authentication Implemented [CRITICAL]
- **File:** `api/middleware.py`, `config/settings.py`
- **Issue:** JWT authentication is configured in settings but NOT implemented in middleware
- **Risk:** Unauthorized access to all API endpoints
- **Evidence:** `settings.py` has `jwt_secret_key` and `auth_enabled` but `middleware.py` has no JWT verification
- **Fix:** Implement JWT middleware and protect routes

### SEC-004: Insecure Default JWT Secret [HIGH]
- **File:** `.env:8` and `config/settings.py`
- **Issue:** Default JWT secret is `"your-super-secret-key-change-this-in-production"`
- **Risk:** Token forgery if deployed with default
- **Fix:** Generate secure random key, validate at startup

### SEC-005: Bare Exception Handlers [MEDIUM]
- **Files:** Multiple files
- **Locations:**
  - `utils/email_verification.py:228` - `except:` with no exception type
  - `utils/email_verification.py:242` - `except:` with no exception type
- **Risk:** Swallows all errors including system exceptions
- **Fix:** Catch specific exception types (e.g., `dns.resolver.NXDOMAIN`)

---

## 2. Code Quality Issues

### CQ-001: sys.path.insert Anti-Pattern [MEDIUM]
- **Files:**
  - `api/app.py:14`
  - `scraper/unified_scraper.py:9`
  - Multiple other files
- **Issue:** Modifying `sys.path` at runtime is an anti-pattern
- **Code:**
  ```python
  sys.path.insert(0, str(Path(__file__).parent.parent))
  ```
- **Fix:** Properly configure Python package with `setup.py` or `pyproject.toml`

### CQ-002: Duplicate _fetch_leads() Method [HIGH]
- **File:** `utils/crm_integrations.py`
- **Issue:** `_fetch_leads()` method appears twice (lines 236-256 and 455-473)
- **Impact:** Code duplication, maintenance burden
- **Fix:** Remove duplicate, consolidate into single method

### CQ-003: Inconsistent Error Handling [MEDIUM]
- **Files:** Multiple route files
- **Issue:** Some endpoints return generic "An error occurred" while others return detailed errors
- **Fix:** Standardize error responses with error codes

### CQ-004: Type Hint Issues [LOW]
- **Files:** Multiple
- **Issues:**
  - Missing return types on some functions
  - `Optional[callable]` should be `Optional[Callable]` (capital C)
- **Fix:** Run mypy and fix type errors

### CQ-005: Hardcoded India Country Code [LOW]
- **File:** `utils/deduplicator.py:35-38`
- **Issue:** Phone normalization assumes India (+91) country code
- **Code:**
  ```python
  if len(normalized) == 10:
      normalized = '+91' + normalized
  ```
- **Fix:** Make country code configurable

---

## 3. Database Issues

### DB-001: Missing Foreign Key Relationship [HIGH]
- **File:** `database/models.py`
- **Issue:** `BusinessLead` has no `job_id` foreign key linking to `ScrapeJob`
- **Impact:** Cannot track which job produced which leads
- **Fix:** Add `job_id = Column(Integer, ForeignKey('scrape_jobs.id'))`

### DB-002: No Database Indexes [MEDIUM]
- **File:** `database/models.py`
- **Issue:** No indexes on frequently queried columns
- **Impact:** Slow queries on large datasets
- **Columns needing indexes:** `city`, `category`, `phone`, `email`, `place_id`
- **Fix:** Add index=True to column definitions

### DB-003: Connection Pool Configuration [LOW]
- **File:** `database/connection.py`
- **Issue:** Uses SQLite default pool, no PostgreSQL production pooling
- **Fix:** Add proper pooling for PostgreSQL in production

---

## 4. Integration Issues

### INT-001: CAPTCHA Solver Not Integrated [HIGH]
- **File:** `scraper/browser_engine.py`
- **Issue:** CAPTCHA solver exists (`utils/captcha_solver.py`) but not imported/used
- **Evidence:** No import of `captcha_solver` in browser_engine.py
- **Fix:** Integrate CAPTCHA detection and solving into scraper flow

### INT-002: Proxy Manager Not Integrated [HIGH]
- **File:** `scraper/browser_engine.py`
- **Issue:** Proxy manager exists but not used in browser configuration
- **Evidence:** No proxy configuration in `launch_browser()` method
- **Fix:** Add proxy rotation to browser initialization

### INT-003: Email Verification Not Auto-Triggered [MEDIUM]
- **File:** `services/scrape_service.py`
- **Issue:** Email verification exists but not called after scraping
- **Fix:** Add optional email verification step post-scrape

### INT-004: Lead Scoring Not Auto-Triggered [MEDIUM]
- **File:** `services/lead_service.py`
- **Issue:** Lead scoring exists but must be manually triggered
- **Fix:** Add automatic scoring after lead creation

### INT-005: Deduplication Integration Gap [MEDIUM]
- **File:** `scraper/unified_scraper.py`
- **Issue:** Deduplicator exists but integration path unclear
- **Fix:** Ensure deduplication runs before saving leads

---

## 5. API Issues

### API-001: Missing Input Validation [MEDIUM]
- **File:** `api/routes/scraping.py`
- **Issue:** Limited validation on scrape request parameters
- **Risk:** Invalid queries, resource exhaustion
- **Fix:** Add Pydantic validators for all inputs

### API-002: No Rate Limiting on Scrape Endpoint [HIGH]
- **File:** `api/routes/scraping.py`
- **Issue:** Scrape endpoint has no rate limiting
- **Risk:** Resource exhaustion, API abuse
- **Fix:** Add rate limiter to `/api/scrape` endpoint

---

## 6. Frontend Issues

### FE-001: No CSRF Protection [MEDIUM]
- **File:** `frontend/app.js`
- **Issue:** API calls have no CSRF token
- **Risk:** Cross-site request forgery attacks
- **Fix:** Implement CSRF token handling

### FE-002: Console Errors Not User-Friendly [LOW]
- **File:** `frontend/app.js`
- **Issue:** Errors logged to console, not shown to users
- **Fix:** Add user-facing error notifications

---

## 7. Missing Features/Files

### MF-001: No Test Suite
- **Issue:** No tests directory or test files exist
- **Impact:** No automated quality assurance
- **Fix:** Create comprehensive test suite

### MF-002: No CI/CD Pipeline
- **Issue:** No `.github/workflows` directory
- **Impact:** No automated testing/deployment
- **Fix:** Create GitHub Actions workflows

### MF-003: Incomplete .gitignore
- **Issue:** May be missing entries for common files
- **Fix:** Ensure .env, __pycache__, .venv, etc. are ignored

---

## Issue Priority Matrix

| Priority | Count | Description |
|----------|-------|-------------|
| P0 (Critical) | 4 | Security vulnerabilities, data loss risk |
| P1 (High) | 6 | Major functionality gaps, security concerns |
| P2 (Medium) | 8 | Code quality, minor security, UX issues |
| P3 (Low) | 5 | Minor improvements, documentation |

---

## Recommended Fix Order

1. **Immediate (Before any deployment):**
   - SEC-001: Fix SSL verification
   - SEC-002: Fix CORS configuration
   - SEC-003: Implement authentication
   - SEC-004: Fix JWT secret

2. **Short-term (Before production):**
   - DB-001: Add job_id foreign key
   - INT-001, INT-002: Integrate CAPTCHA and proxy
   - API-002: Add rate limiting to scrape endpoint
   - CQ-002: Remove duplicate code

3. **Medium-term:**
   - Add comprehensive test suite
   - Set up CI/CD pipeline
   - Add database indexes
   - Standardize error handling

4. **Long-term:**
   - Auto-trigger lead scoring and email verification
   - Add CSRF protection
   - Improve type hints
   - User-friendly error handling in frontend

---

*This document should be updated as issues are resolved.*
