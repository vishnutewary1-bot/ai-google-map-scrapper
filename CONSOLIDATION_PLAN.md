# MapLeads Pro - Code Consolidation & Production Readiness Plan

## Executive Summary

**Total Codebase Size:** ~15,279 lines (excluding tests)
**Dormant/Unused Code:** ~4,500+ lines (29% of codebase)
**Duplicate Code:** ~2,000+ lines across multiple files
**Production Readiness:** 65% (needs consolidation)

---

## Table of Contents

1. [Phase 1: Delete Obsolete Code](#phase-1-delete-obsolete-code)
2. [Phase 2: Consolidate Duplicate Code](#phase-2-consolidate-duplicate-code)
3. [Phase 3: Integrate Dormant Features](#phase-3-integrate-dormant-features)
4. [Phase 4: Fix Integration Gaps](#phase-4-fix-integration-gaps)
5. [Phase 5: Production Hardening](#phase-5-production-hardening)
6. [Implementation Checklist](#implementation-checklist)

---

## Phase 1: Delete Obsolete Code

### 1.1 Delete Unused Extractors (739 lines)

| File | Lines | Reason |
|------|-------|--------|
| `scraper/extractors/justdial_extractor.py` | 361 | Never called, no frontend integration |
| `scraper/extractors/yellowpages_extractor.py` | 378 | Never called, no frontend integration |

**Action:**
```
DELETE: scraper/extractors/justdial_extractor.py
DELETE: scraper/extractors/yellowpages_extractor.py
UPDATE: scraper/extractors/__init__.py (remove imports)
UPDATE: scraper/unified_scraper.py (remove imports lines 83, 91)
```

### 1.2 Delete Unused Database Columns

| Column | File:Line | Reason |
|--------|-----------|--------|
| `cid` | models.py:169 | Never extracted or queried |
| `change_history` | models.py:181 | Never populated |
| `social_tiktok` | models.py:92 | Never extracted |
| `social_pinterest` | models.py:93 | Never extracted |
| `social_whatsapp` | models.py:94 | Never extracted (use whatsapp_number instead) |

**Action:**
```
CREATE: migrations/002_remove_unused_columns.py
DELETE: Columns from models.py
UPDATE: to_dict() method
UPDATE: to_export_dict() method
```

### 1.3 Delete Unused Database Models

| Model | File:Lines | Reason |
|-------|------------|--------|
| `WebhookHistory` | models.py:667-695 | Incomplete webhook feature |
| `ExportHistory` | models.py:636-664 | Never tracked in practice |

**Action:**
```
DELETE: WebhookHistory class (models.py:667-695)
DELETE: ExportHistory class (models.py:636-664)
UPDATE: Remove related imports
CREATE: Migration to drop tables
```

### 1.4 Delete Unused API Endpoints

| Endpoint | File:Lines | Reason |
|----------|------------|--------|
| `GET /api/data-sources` | features.py:1631-1652 | Lists non-functional extractors |
| `GET /api/webhook/history` | features.py | Webhook feature incomplete |

**Action:**
```
DELETE: /data-sources endpoint (features.py:1631-1652)
DELETE: /webhook/history endpoint
UPDATE: frontend/app.js (remove any references)
```

### 1.5 Delete Empty Test Directories

```
DELETE: teststest_api/ (empty)
DELETE: teststest_database/ (empty)
DELETE: teststest_utils/ (empty)
```

---

## Phase 2: Consolidate Duplicate Code

### 2.1 Consolidate Export Functions (CRITICAL)

**Current State (3 implementations):**
1. `utils/exporter.py` - Standalone functions (lines 692-827)
2. `utils/exporter.py` - DataExporter class methods (lines 107-476)
3. `api/services/export_service.py` - ExportService wrapper (lines 151-308)

**Target State (1 implementation):**
Create unified `utils/export_manager.py`

**Consolidation Map:**

| Current Location | Lines | Move To |
|-----------------|-------|---------|
| `exporter.py:export_to_excel()` (standalone) | 692-759 | DELETE (use class method) |
| `exporter.py:export_to_csv()` (standalone) | 762-802 | DELETE (use class method) |
| `exporter.py:export_to_json()` (standalone) | 804-827 | DELETE (use class method) |
| `exporter.py:DataExporter.export_to_excel()` | 107-156 | KEEP (primary) |
| `export_service.py:_export_excel()` | 151-172 | REFACTOR (call DataExporter) |

**Action:**
```python
# NEW: utils/export_manager.py
class ExportManager:
    """Unified export manager - single source of truth"""

    # Merge all column definitions here
    COLUMNS = {
        'full': [...],  # From FULL_EXPORT_COLUMNS
        'basic': [...],  # From EXPORT_COLUMNS
        'cold_calling': [...],
        'email_campaign': [...],
        'social_media': [...]
    }

    def export(self, format, leads, columns=None):
        """Single export method for all formats"""
        pass
```

### 2.2 Consolidate Column Definitions (6 locations -> 1)

**Current Locations:**
| Location | Lines | Columns |
|----------|-------|---------|
| `exporter.py` | 24-81 | EXPORT_COLUMNS (39) |
| `exporter.py` | 84-101 | FULL_EXPORT_COLUMNS (50+) |
| `exporter.py` | 224-237 | cold_calling_columns (12) |
| `exporter.py` | 280-294 | email_columns (13) |
| `exporter.py` | 337-347 | social_columns (9) |
| `models.py` | 386-432 | to_export_dict() mapping |

**Action:**
```
CREATE: config/export_columns.py
MOVE: All column definitions to single file
UPDATE: exporter.py to import from config
UPDATE: models.py to import from config
DELETE: Duplicate definitions
```

### 2.3 Consolidate HAS_DATABASE Pattern (16+ files -> 1)

**Current State:** Repeated in 16+ files:
```python
try:
    from database import db_manager
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False
```

**Files with duplication:**
- api/app.py:28-33
- api/services/scrape_service.py:17-24
- api/services/lead_service.py:15-23
- scraper/unified_scraper.py:27-34
- utils/lead_scoring.py:24-31
- utils/exporter.py:17
- api/routes/analytics.py
- api/routes/features.py
- (8+ more files)

**Target State:**
```python
# NEW: config/features.py
class FeatureFlags:
    HAS_DATABASE = False
    HAS_SHEETS = False
    HAS_OPENAI = False
    HAS_SENTIMENT = False
    HAS_SCRAPE_FILTERS = False

    @classmethod
    def initialize(cls):
        """Initialize all feature flags once at startup"""
        try:
            from database import db_manager
            cls.HAS_DATABASE = True
        except ImportError:
            pass
        # ... etc
```

**Action:**
```
CREATE: config/features.py
UPDATE: All 16+ files to import from config.features
DELETE: Duplicate try-except blocks
```

### 2.4 Consolidate Quality Score Calculation (3 locations -> 1)

**Current Locations:**
| Location | Lines | Method |
|----------|-------|--------|
| `models.py` | 434-486 | BusinessLead.calculate_quality_score() |
| `unified_scraper.py` | 636-670 | _calculate_quality_score() |
| `lead_scoring.py` | various | Multiple scoring methods |

**Action:**
```
KEEP: utils/lead_scoring.py as single source
UPDATE: models.py to call lead_scoring functions
UPDATE: unified_scraper.py to call lead_scoring functions
DELETE: Duplicate implementations
```

### 2.5 Consolidate Database Filter Logic (3 locations -> 1)

**Current Locations:**
- `utils/exporter.py:_fetch_from_database()` (lines 506-601)
- `api/services/lead_service.py:_apply_filters()`
- `api/routes/features.py` (multiple filter applications)

**Action:**
```
CREATE: database/filters.py
MOVE: All filter logic to single file
UPDATE: Services to use shared filter module
```

### 2.6 Consolidate Job Status Updates (2 locations -> 1)

**Current Locations:**
- `api/services/scrape_service.py:301-321`
- `scraper/unified_scraper.py:775-794`

**Action:**
```
CREATE: api/services/job_service.py
MOVE: All job status logic to single service
UPDATE: scrape_service.py to use job_service
UPDATE: unified_scraper.py to use job_service
```

---

## Phase 3: Integrate Dormant Features

### 3.1 Email Guesser (INTEGRATE or DELETE)

**Current State:**
- File: `utils/email_guesser.py` (252 lines)
- Endpoint: `/api/leads/{lead_id}/guess-emails` (unused)
- DB Column: `guessed_emails` (partially populated)

**Decision: INTEGRATE**

**Action:**
```
UPDATE: scraper/unified_scraper.py
  - Call email guesser automatically during scraping
  - Populate guessed_emails column

UPDATE: frontend/app.js
  - Show guessed emails in lead details modal
  - Add "Guess Emails" button

UPDATE: frontend/index.html
  - Add guessed_emails to lead details view
```

### 3.2 WhatsApp Detector (INTEGRATE or DELETE)

**Current State:**
- File: `utils/whatsapp_detector.py` (290 lines)
- Endpoint: `/api/leads/{lead_id}/detect-whatsapp` (unused)
- DB Columns: `whatsapp_number`, `whatsapp_link`, `whatsapp_likelihood` (rarely populated)

**Decision: INTEGRATE**

**Action:**
```
UPDATE: scraper/unified_scraper.py
  - Call WhatsApp detector automatically
  - Populate whatsapp columns

UPDATE: frontend/app.js
  - Show WhatsApp info in lead details
  - Add WhatsApp click-to-chat link

UPDATE: frontend/index.html
  - Add WhatsApp column to leads table (optional)
```

### 3.3 Hours Analyzer (INTEGRATE or DELETE)

**Current State:**
- File: `utils/hours_analyzer.py` (366 lines)
- Endpoint: `/api/leads/{lead_id}/analyze-hours` (unused)
- DB Columns: `hours_analysis`, `best_call_times`, `opening_pattern` (partially populated)

**Decision: INTEGRATE**

**Action:**
```
UPDATE: scraper/unified_scraper.py
  - Call hours analyzer automatically
  - Populate hours analysis columns

UPDATE: frontend/app.js
  - Show "Best Time to Call" in lead details
  - Add opening_pattern badge to leads table

UPDATE: frontend/index.html
  - Add "Best Call Time" to lead details modal
```

### 3.4 Cloud Storage (INTEGRATE or DELETE)

**Current State:**
- File: `utils/cloud_storage.py` (327 lines)
- Status: Fully implemented but not integrated

**Decision: INTEGRATE**

**Action:**
```
UPDATE: api/services/export_service.py
  - Add cloud upload option
  - Support S3 and GCS

UPDATE: frontend/index.html
  - Add "Upload to Cloud" checkbox in export form
  - Add cloud provider dropdown (S3/GCS)

UPDATE: frontend/app.js
  - Handle cloud upload response
  - Show cloud URL after upload
```

### 3.5 Data Freshness Tracking (COMPLETE or DELETE)

**Current State:**
- File: `utils/data_freshness.py` (239 lines)
- DB Columns: `last_verified_at`, `verification_count` (rarely updated)

**Decision: COMPLETE**

**Action:**
```
UPDATE: scraper/unified_scraper.py
  - Update last_verified_at on each scrape
  - Increment verification_count on re-scrape

UPDATE: frontend/app.js
  - Show freshness status badge (Fresh/Stale/Outdated)
  - Add "Re-verify" button for stale leads

UPDATE: api/routes/leads.py
  - Add freshness filter parameter
```

### 3.6 Scheduler (DELETE - Too Complex)

**Current State:**
- File: `scraper/scheduler.py`
- Status: Partially implemented, complex

**Decision: DELETE**

**Action:**
```
DELETE: scraper/scheduler.py
DELETE: Scheduler endpoints in features.py (lines 631-805)
DELETE: Related imports
```

### 3.7 Notifications Service (DELETE - Not Core Feature)

**Current State:**
- File: `utils/notifications.py` (530 lines)
- Status: Incomplete, many external dependencies

**Decision: DELETE**

**Action:**
```
DELETE: utils/notifications.py
DELETE: Related imports and endpoints
```

---

## Phase 4: Fix Integration Gaps

### 4.1 Fix main.py Import Error (CRITICAL)

**Current State:**
```python
# main.py:7
from scraper import GoogleMapsScraper  # ERROR: Does not exist!
```

**Action:**
```python
# Fix main.py:7
from scraper import UnifiedGoogleMapsScraper as GoogleMapsScraper
```

### 4.2 Centralize Database Initialization

**Current State:** Database initialized in multiple places:
- api/app.py:129-135
- main.py:18-19, 50
- scraper/unified_scraper.py:255-256

**Action:**
```
CREATE: database/init.py
  - Single initialization function
  - Called once at startup

UPDATE: api/app.py
  - Import and call init function

UPDATE: main.py
  - Import and call init function

DELETE: Duplicate initialization code
```

### 4.3 Standardize Entry Points

**Current State:** Multiple confusing entry points:
- `main.py` - CLI commands
- `run.py` - Unknown
- `run_server.py` - Server startup
- `api/app.py` - FastAPI app
- `api/index.py` - Vercel handler

**Action:**
```
KEEP: main.py (rename to cli.py)
KEEP: run_server.py (primary server entry)
DELETE: run.py (duplicate)
KEEP: api/app.py (FastAPI app)
KEEP: api/index.py (Vercel deployment)

CREATE: docs/ENTRY_POINTS.md
  - Document when to use each entry point
```

### 4.4 Service Layer Integration

**Current State:** Services don't share data/cache

**Action:**
```
CREATE: api/services/base_service.py
  - Shared database session management
  - Shared caching layer
  - Common error handling

UPDATE: All services to extend BaseService
```

---

## Phase 5: Production Hardening

### 5.1 Environment Configuration

**Action:**
```
UPDATE: config/settings.py
  - Add all environment variables
  - Add validation for required vars
  - Add sensible defaults

CREATE: .env.production.example
  - Production-ready template
```

### 5.2 Error Handling Standardization

**Action:**
```
CREATE: utils/exceptions.py
  - Custom exception classes
  - Standardized error responses

UPDATE: All routes to use custom exceptions
```

### 5.3 Logging Consolidation

**Action:**
```
UPDATE: utils/logger.py
  - Single logging configuration
  - Structured logging format
  - Log levels by environment
```

### 5.4 API Documentation

**Action:**
```
UPDATE: All API routes
  - Add proper docstrings
  - Add request/response examples
  - Add error response documentation
```

### 5.5 Database Migrations

**Action:**
```
CREATE: migrations/
  - 002_remove_unused_columns.py
  - 003_add_indexes.py
  - 004_cleanup_models.py
```

### 5.6 Frontend Cleanup

**Action:**
```
UPDATE: frontend/app.js
  - Remove unused functions
  - Consolidate duplicate code
  - Add proper error handling

UPDATE: frontend/index.html
  - Remove unused elements
  - Add loading states
  - Improve accessibility
```

---

## Implementation Checklist

### Week 1: Delete & Cleanup
- [ ] Delete justdial_extractor.py
- [ ] Delete yellowpages_extractor.py
- [ ] Delete empty test directories
- [ ] Delete unused database models
- [ ] Delete unused API endpoints
- [ ] Create column removal migration
- [ ] Fix main.py import error

### Week 2: Consolidate Duplicates
- [ ] Create config/features.py
- [ ] Create config/export_columns.py
- [ ] Create utils/export_manager.py
- [ ] Consolidate HAS_DATABASE pattern
- [ ] Consolidate quality score calculation
- [ ] Consolidate filter logic
- [ ] Consolidate job status updates

### Week 3: Integrate Features
- [ ] Integrate email guesser into scraping flow
- [ ] Integrate WhatsApp detector into scraping flow
- [ ] Integrate hours analyzer into scraping flow
- [ ] Integrate cloud storage into export
- [ ] Complete data freshness tracking
- [ ] Delete scheduler feature
- [ ] Delete notifications service

### Week 4: Production Hardening
- [ ] Centralize database initialization
- [ ] Standardize entry points
- [ ] Create base service class
- [ ] Standardize error handling
- [ ] Consolidate logging
- [ ] Update API documentation
- [ ] Frontend cleanup

---

## Code Metrics After Consolidation

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total Lines | 15,279 | ~11,500 | -25% |
| Dormant Code | 4,500+ | ~200 | -96% |
| Duplicate Code | 2,000+ | ~100 | -95% |
| Files | 45+ | ~35 | -22% |
| Entry Points | 5 | 3 | -40% |

---

## Files to DELETE (Complete List)

```
scraper/extractors/justdial_extractor.py (361 lines)
scraper/extractors/yellowpages_extractor.py (378 lines)
scraper/scheduler.py (~200 lines)
utils/notifications.py (530 lines)
run.py (~50 lines)
teststest_api/ (directory)
teststest_database/ (directory)
teststest_utils/ (directory)
```

**Total Deletion: ~1,519+ lines + 3 directories**

---

## Files to CREATE (Complete List)

```
config/features.py - Feature flags
config/export_columns.py - Column definitions
utils/export_manager.py - Unified export
database/filters.py - Shared filter logic
database/init.py - Centralized init
api/services/base_service.py - Base service class
api/services/job_service.py - Job management
utils/exceptions.py - Custom exceptions
migrations/002_remove_unused_columns.py
migrations/003_cleanup_models.py
docs/ENTRY_POINTS.md - Documentation
.env.production.example - Production config
```

---

## Priority Order

1. **CRITICAL** - Fix main.py import error
2. **HIGH** - Delete obsolete extractors (prevents confusion)
3. **HIGH** - Consolidate HAS_DATABASE pattern (reduces bugs)
4. **MEDIUM** - Consolidate export functions (reduces maintenance)
5. **MEDIUM** - Integrate dormant features (adds value)
6. **LOW** - Production hardening (improves quality)

---

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| Delete extractors | LOW | Not used anywhere |
| Delete columns | MEDIUM | Migration required |
| Consolidate exports | MEDIUM | Test all export formats |
| Integrate features | LOW | Features already exist |
| Delete scheduler | LOW | Feature incomplete |

---

## Testing Requirements

After each phase, test:
1. All API endpoints respond correctly
2. All export formats generate valid files
3. Scraping flow completes successfully
4. Frontend loads and functions
5. Database migrations apply cleanly
6. All integrated features work

---

## Success Criteria

- [ ] Zero duplicate code patterns
- [ ] All dormant code either integrated or deleted
- [ ] Single source of truth for each functionality
- [ ] All tests pass
- [ ] API documentation complete
- [ ] Production deployment successful
