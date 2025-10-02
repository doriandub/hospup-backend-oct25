# 📋 Code Duplicates & Refactoring Roadmap

**Generated:** 2025-10-02
**Status:** Post-cleanup analysis

---

## 🎯 Executive Summary

After the major cleanup (2596 files removed, 200MB saved), these **architectural and code duplication issues** remain to be addressed:

### Priority Breakdown:
- 🔴 **Critical (Blocks scaling):** 2 issues
- 🟠 **High (Major refactoring needed):** 4 issues
- 🟡 **Medium (Code quality improvements):** 6 issues
- 🟢 **Low (Nice to have):** 3 issues

**Estimated effort:** 3-4 weeks for full refactoring

---

## 🔴 CRITICAL ISSUES

### 1. Architecture Confusion: DDD vs Traditional MVC

**Location:** `hospup-backend/app/`

**Problem:**
Two competing architectures exist in parallel:
- **DDD layer** (Domain-Driven Design): `/domain/`, `/application/`, `/interfaces/`
- **Traditional MVC**: `/models/`, `/schemas/`, `/api/`, `/services/`

**Duplicate entities:**
```
/app/domain/entities/video.py          (243 lines, business logic)
/app/models/video.py                   (35 lines, SQLAlchemy)
```

Both define the **same Video concept** but API routes use only the models layer.

**Impact:**
- 40% code duplication
- DDD layer is **dead code** (never used)
- New developers are confused about where to add logic
- Business rules scattered across layers

**Recommendation:**
```
OPTION A (Recommended): Remove DDD layer, stick with FastAPI MVC
- Delete /app/domain/, /app/application/, /app/interfaces/
- Keep /app/models/, /app/schemas/, /app/api/, /app/services/
- Move any useful business logic from entities to services

OPTION B: Commit fully to DDD
- Refactor ALL API routes to use use cases
- Remove /app/models/ (use domain entities)
- Add proper repository implementations
```

**Effort:** 1-2 weeks

---

### 2. Video vs Asset Model Duplication

**Location:** `hospup-backend/app/models/`

**Problem:**
Two nearly identical models (95% same fields):

```python
# Asset = User-uploaded videos
class Asset(Base):
    id, title, description, file_url, thumbnail_url
    duration, file_size, status, asset_type
    property_id, user_id

# Video = AI-generated videos
class Video(Base):
    id, title, description, file_url, thumbnail_url
    duration, file_size, status
    property_id, user_id
```

**Duplicated code:**
- `app/api/assets.py` (400+ lines)
- `app/api/videos.py` (300+ lines)
- Frontend: `useAssets()` vs `useVideos()` hooks
- Separate database tables for same concept

**Recommendation:**
```python
# Unified model
class Media(Base):
    """Unified model for all media (uploaded + generated)"""
    __tablename__ = "media"

    id = Column(UUID, primary_key=True)
    source = Column(Enum("uploaded", "generated"))  # Discriminator

    # Common fields
    title, description, file_url, thumbnail_url
    duration, file_size, status

    # For generated videos only
    generation_metadata = Column(JSON, nullable=True)
    template_id = Column(UUID, ForeignKey("templates.id"), nullable=True)
```

**Migration plan:**
1. Create new `media` table
2. Migrate data from `assets` + `videos` tables
3. Update all API endpoints to use unified model
4. Update frontend to use single `useMedia()` hook
5. Drop old tables

**Effort:** 1 week

---

## 🟠 HIGH PRIORITY

### 3. Frontend Component Duplication

**Location:** `hospup-frontend/src/components/`

**Duplicate Canvas Editors:**
```
canvas-video-editor.tsx               (345 lines)
canvas-video-editor-masterclass.tsx   (710 lines) ← MORE FEATURES
```
→ Keep `masterclass`, rename to `canvas-video-editor.tsx`

**Duplicate Timeline Editors:**
```
video-timeline-editor.tsx
video-timeline-editor-new.tsx
video-timeline-editor-compact.tsx
```
→ Consolidate to ONE with props: `variant="compact" | "full"`

**Duplicate Text Editors:**
```
text-overlay-editor.tsx
timeline-text-editor.tsx
interactive-text-editor.tsx
unified-text-editor.tsx              ← Most complete?
text-formatting-toolbar.tsx
text-formatting-modal-toolbar.tsx
```
→ Keep `unified-text-editor.tsx`, extract toolbar to shared component

**Effort:** 1 week

---

### 4. Next.js API Routes Proxy Backend (Unnecessary Layer)

**Location:** `hospup-frontend/src/app/api/`

**Problem:**
Next.js API routes proxy to backend API:
```typescript
// hospup-frontend/src/app/api/videos/route.ts
export async function GET(req: Request) {
  const response = await fetch(`${BACKEND_URL}/videos`)
  return response
}
```

**Why unnecessary:**
- Double API surface area
- Extra network hop
- CORS complexity
- Harder to debug

**Recommendation:**
Remove Next.js API routes. Call backend directly from frontend:
```typescript
// Before
const response = await fetch('/api/videos')

// After
const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/videos`)
```

**Keep ONLY:** Routes that need server-side auth handling

**Effort:** 2-3 days

---

### 5. Large Files Violating Single Responsibility Principle

**Location:** `hospup-backend/app/api/`

**Files:**
```
smart_matching.py    - 1,210 lines (!!)
diagnostic.py        - 563 lines
upload.py            - 451 lines
```

**Example (`smart_matching.py` contains):**
- Pydantic schemas (should be `/schemas/`)
- Business logic (should be `/services/`)
- Database queries (should be `/repositories/`)
- API routes (correct location)
- Constants and configs

**Recommendation:**
Split each into modules:
```
/api/smart_matching/
  ├── __init__.py
  ├── routes.py        # Just FastAPI routes
  ├── schemas.py       # Pydantic models
  ├── service.py       # Business logic
  └── repository.py    # DB queries
```

**Effort:** 3-4 days

---

### 6. No Database Migrations (Alembic)

**Location:** `hospup-backend/alembic/versions/` (empty)

**Problem:**
- Database schema changes not tracked
- Tables created programmatically in `main.py`:
  ```python
  if settings.APP_ENV == "development":
      async with engine.begin() as conn:
          await conn.run_sync(Base.metadata.create_all)
  ```

**Risks:**
- Cannot roll back schema changes
- Production deployments risky
- Hard to sync schema across environments

**Recommendation:**
1. Initialize Alembic: `alembic init alembic`
2. Create initial migration: `alembic revision --autogenerate -m "Initial schema"`
3. Remove `create_all()` from `main.py`
4. Document migration workflow

**Effort:** 1 day

---

## 🟡 MEDIUM PRIORITY

### 7. Excessive Debug Code in Production

**Found:** 329 occurrences of `console.log` / `print()`

**Examples:**
```python
# smart_matching.py:904
print("🔍 CRITICAL DEBUG: Log all required fields before sending to Lambda")

# simple-video-capture-mediaconvert.ts:16
console.log(`📊 DEBUG: videoData received:`, videoData)
```

**Impact:**
- Performance overhead
- Log spam in production
- Potential security risk (may log sensitive data)

**Recommendation:**
- Replace with proper logging libraries
- Use log levels: `logger.info()`, `logger.debug()`
- Remove debug statements before deployment

**Effort:** 2 days (automated with script)

---

### 8. Inconsistent Error Handling

**Problem:**
API endpoints return different error formats:
```python
# Format 1
return {"detail": "error message"}

# Format 2
return {"message": "error message"}

# Format 3
return {"error": "error message"}
```

**Impact:**
Frontend needs to handle 3+ error formats

**Recommendation:**
Standardize on one format:
```python
# Standard error response
{
  "error": {
    "code": "VIDEO_NOT_FOUND",
    "message": "Video with ID xyz not found",
    "details": {...}  # Optional
  }
}
```

**Effort:** 1 day

---

### 9. Hardcoded Values

**Examples:**
```typescript
// simple-video-capture-mediaconvert.ts:41
propertyId: '1', // TODO: Get from user context

// Multiple files
const API_URL = 'https://web-production-b52f.up.railway.app'
```

**Recommendation:**
- Move all hardcoded values to environment variables
- Create `.env.example` files with documentation
- Validate env vars on startup

**Effort:** 1 day

---

### 10. Inconsistent Naming Conventions

**Problem:**
Mixed naming styles across same codebase:
```
viral_matching vs viralMatching vs viral-matching
text_overlays vs textOverlays
```

**Recommendation:**
Enforce conventions:
- **Python:** strict `snake_case`
- **TypeScript:** strict `camelCase`
- **API endpoints:** `kebab-case`
- **Database:** `snake_case`

Add linters: `isort`, `black` (Python), ESLint (TypeScript)

**Effort:** 1 day + CI setup

---

### 11. Missing Type Annotations

**Problem:**
- Some Python functions lack type hints
- TypeScript has `any` types in places

**Recommendation:**
```python
# Before
def process_video(video_id, options):
    ...

# After
def process_video(video_id: UUID, options: VideoOptions) -> ProcessResult:
    ...
```

Add to CI: `mypy` (Python), TypeScript strict mode

**Effort:** 2-3 days

---

### 12. Fragmented Documentation

**Problem:**
15 markdown files scattered across project:
```
AWS-SETUP-GUIDE.md
AWS-PERMISSIONS-NEEDED.md
AWS-PERMISSIONS-GUIDE.md  (duplicate!)
S3_CONFIGURATION.md
S3_CORS_FIX.md
DEPLOYMENT-GUIDE.md (2 copies!)
```

**Recommendation:**
Consolidate into:
```
/docs/
  ├── README.md          # Project overview
  ├── SETUP.md           # Local development setup
  ├── DEPLOYMENT.md      # Deployment guide (AWS, Railway, Vercel)
  ├── ARCHITECTURE.md    # System architecture
  └── API.md             # API documentation
```

**Effort:** 1 day

---

## 🟢 LOW PRIORITY

### 13. TODO/FIXME Comments Not Tracked

**Recommendation:**
Convert to GitHub issues, add to project board

**Effort:** 2 hours

---

### 14. Missing Unit Tests

**Current state:**
- No test coverage metrics
- Few unit tests for critical business logic

**Recommendation:**
- Add pytest for Python backend
- Add Jest/Vitest for TypeScript frontend
- Target 70%+ coverage for critical paths

**Effort:** Ongoing

---

### 15. No Pre-commit Hooks

**Recommendation:**
Setup pre-commit hooks:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
  - repo: https://github.com/PyCQA/isort
  - repo: https://github.com/pre-commit/mirrors-eslint
```

**Effort:** 1 hour

---

## 📊 Refactoring Roadmap

### Week 1: Critical Architecture
- [ ] Day 1-2: Remove DDD layer OR refactor to full DDD
- [ ] Day 3-5: Unify Video/Asset models into Media model

### Week 2: Component Consolidation
- [ ] Day 1-2: Consolidate canvas editors
- [ ] Day 3-4: Consolidate timeline editors
- [ ] Day 5: Consolidate text editors

### Week 3: API & Backend Cleanup
- [ ] Day 1: Remove Next.js API proxy routes
- [ ] Day 2-3: Split large files (smart_matching, etc.)
- [ ] Day 4: Setup Alembic migrations
- [ ] Day 5: Standardize error handling

### Week 4: Code Quality
- [ ] Day 1: Remove debug code (automated)
- [ ] Day 2: Add type annotations
- [ ] Day 3: Fix naming inconsistencies (linters)
- [ ] Day 4: Consolidate documentation
- [ ] Day 5: Setup pre-commit hooks + CI

---

## 🎯 Success Metrics

After completing refactoring:
- ✅ Code duplication: **<10%** (currently 35-40%)
- ✅ Average file size: **<200 lines** (currently 400+)
- ✅ Test coverage: **>70%** (currently minimal)
- ✅ Build time: **<2 min** (measure baseline first)
- ✅ No files >500 lines

---

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking changes during refactor | Write tests BEFORE refactoring |
| Lost business logic when removing DDD | Careful code review + migration checklist |
| Database migration failures | Test migrations on staging first |
| Frontend breaks without API proxy | Gradual migration, route by route |

---

## 📝 Notes

- All refactoring should be done in **feature branches**
- Each item should have **separate PR** for review
- **DO NOT** merge multiple refactorings into one PR
- Run full test suite before merging
- Update documentation as you go

---

**Next Steps:**
1. Review this roadmap with team
2. Prioritize based on current pain points
3. Create GitHub issues for each item
4. Start with Week 1 (Critical Architecture)
