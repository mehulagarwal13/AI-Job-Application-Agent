# AI Job Application Agent

A GenAI-powered backend that takes a resume, understands it, and finds real jobs that fit — automatically.

**Core idea:** Upload a resume → the system extracts and structures its content with an LLM → scrapes live job listings → matches jobs to the resume using semantic (vector) search + skill analysis → scores each match like an ATS would.

**Roadmap:** resume tailoring for near-miss jobs (rewrite/emphasize resume content for a specific job), and eventually **auto-apply** — when a fitting job is found, the agent applies on the candidate's behalf.

---

## Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| API framework | FastAPI + Uvicorn | REST endpoints, async upload handling |
| Relational DB | **Neon** (serverless cloud PostgreSQL) + SQLAlchemy ORM | Resumes, jobs, match results |
| Migrations | Alembic | Schema versioning |
| Vector search | **pgvector on Neon** (HNSW index) | Similarity search over job embeddings — same DB as relational data, no extra service |
| LLM | OpenAI via a provider-agnostic **LLM Router** (`app/ai/llm/`) | Resume parsing, job-fit analysis; task→model routing is pure config |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (local, free) | 384-dim semantic vectors |
| Job sources | Plugin connectors: **Adzuna** (key), **Remotive** + **Arbeitnow** (free, keyless) | Live job listings, cross-source deduplicated |
| Scheduler | APScheduler | Optional automatic job sync (opt-in via `JOB_SYNC_QUERIES`) |
| File parsing | pdfplumber (PDF), python-docx (DOCX) | Text extraction |

---

## API Keys — what each one does

All keys live in `.env` (never commit it — see `.env.example` for the template). `app/core/config.py` loads them at startup and **fails fast** with a clear error if any is missing.

| Key | Where to get it | Used by | What it powers |
|---|---|---|---|
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) | `app/services/resume_parser.py`, `app/services/matching/job_skill_extractor.py` | LLM calls: parsing resume text into structured JSON, and analyzing each job description (required skills, ATS keywords, fit explanation) |
| `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` | [developer.adzuna.com](https://developer.adzuna.com) (free tier) | `app/services/job_sources/adzuna_client.py` | Fetching live job listings by search query, country, and location |
| `DATABASE_URL` | [neon.tech](https://neon.tech) → project → **Connect** | `app/core/database.py`, `alembic/env.py` | Neon cloud Postgres connection (must include `?sslmode=require`) |
| *(no vector DB key)* | — | `app/core/pgvector_setup.py`, `app/services/matching/job_vector_store.py` | Vector storage & search run inside Neon via the pgvector extension — enabled automatically at startup |

Note: embeddings are generated **locally** by sentence-transformers — no API key or cost involved.

---

## The Pipeline — every step in detail

### Stage 1 — Resume Upload
`POST /resumes/upload` · `app/api/resumes.py`, `app/services/file_storage.py`

1. File read into memory; rejected if empty, over 5 MB, or not `.pdf`/`.docx`.
2. SHA-256 hash computed over the raw bytes → **deduplication**: if the exact file was uploaded before, the existing `resume_id` is returned (status `duplicate_of_existing`) instead of creating a duplicate.
3. File saved to `storage/resumes/{uuid}.{ext}`; a `resumes` row is created with status `uploaded`.

### Stage 2 — Text Extraction
Runs **automatically in the background after upload** (also available as `POST /resumes/{resume_id}/extract`, idempotent, `?force=true` to redo) · `app/services/text_extraction.py`

- **PDF** → **column-aware** extraction: each page is scanned for a vertical gutter; two-column resumes are read left column first, then right — no more interleaved lines.
- **Scanned/image PDFs** → **OCR fallback**: pages are rendered at ~300 DPI and OCR'd with Tesseract (optional deps `pypdfium2` + `pytesseract`; a clear, actionable error is returned if not installed).
- **DOCX** → paragraphs **and tables**, in true document order — skills/contact tables are no longer lost.
- **Text cleaning** before persistence: NFKC unicode normalization, de-hyphenation of line-broken words, bullet-glyph normalization, whitespace collapsing — cleaner input for the LLM and ATS scoring.
- Guardrail: if the cleaned result is under 50 characters, extraction fails with a clear error instead of silently passing garbage downstream.
- Status transitions: `uploaded` → `extracted` (or `extraction_failed`). Extracted text is persisted so later stages never re-read the file.

### Stage 3 — LLM Parsing (GenAI core)
`POST /resumes/{resume_id}/parse` · `app/services/resume_parser.py`, `app/services/normalizer.py`

The raw text goes to OpenAI `gpt-4.1-mini` with a strict system prompt: extract **only** what is explicitly in the resume — no hallucinated dates, companies, or degrees. Output must be pure JSON matching the `ParsedResume` schema:

- identity: name, email, phone, location
- `total_years_experience` (estimated from date ranges)
- `skills` (explicitly listed) kept **separate** from `inferred_skills` (implied by experience — e.g. "built REST APIs in Django" ⇒ Python, Django, REST)
- experience entries with achievements, education, certifications

The response is validated against the Pydantic schema, then normalized (`normalizer.py` + `skills_taxonomy.py` map variants like `postgres`/`postgresql` → `PostgreSQL`). A confidence score is stored alongside; status becomes `parsed`.

### Stage 4 — Resume Embedding
`POST /resumes/{resume_id}/embed` · `app/services/embedding_service.py`, `app/services/resume_text_builder.py`

A compact summary text is built from the parsed data, then encoded by `all-MiniLM-L6-v2` into a **normalized 384-dim vector** (normalized so cosine similarity is a plain dot product). Cached in the DB — computed once per resume.

### Stage 5 — Job Scraping & Ingestion (multi-source)
`POST /jobs/ingest?query=...&sources=all&country=...` · `app/services/job_sources/`, `app/services/job_ingestion.py`

Every source implements the same `JobSource` contract (`base.py`) and returns one normalized shape. Registered connectors (`GET /jobs/sources` lists them):

1. **Adzuna** — keyed API, any country (`in`, `us`, `gb`, ...), salary data.
2. **Remotive** — free/keyless, remote-only listings.
3. **Arbeitnow** — free/keyless, Europe/remote-heavy (client-side term filtering).

The shared ingestion service then: skips incomplete listings → computes a **cross-source dedup key** (`sha1(title|company)` — the same role on two boards is stored once) → parses "X+ years" requirements (`experience_extractor.py`) → upserts by source job ID. One failing source never aborts the others; per-source stats are returned.

**Optional auto-sync** (`app/core/scheduler.py`): set `JOB_SYNC_QUERIES=backend engineer;data scientist` in `.env` and APScheduler re-ingests and re-embeds every `JOB_SYNC_INTERVAL_HOURS` (default 6) — the job pool stays fresh with zero manual calls. Adding LinkedIn/Indeed/Naukri later = one connector file + one registry line.

### Stage 6 — Job Embedding & Vector Indexing
`POST /jobs/embed-pending` · `app/services/matching/job_vector_store.py`

Every not-yet-embedded job gets a summary text → 384-dim vector → stored in the **`jobs.embedding_vector` pgvector column** on Neon, covered by an **HNSW index** (approximate nearest-neighbor, cosine distance). Vectors live next to the relational data — one database, one connection string, no sync between systems.

### Stage 7 — Matching Engine
`POST /resumes/{resume_id}/matches/generate` · `app/services/matching/`

Four sub-steps, funnel-shaped (cheap & broad → expensive & precise):

1. **Retrieval** (`retrieval.py`): resume vector → single pgvector SQL query → top-40 semantically similar jobs as full records (the old two-step "search vector DB, then fetch rows" is gone).
2. **Hard filters** (`hard_filters.py`): drop jobs failing concrete rules — location mismatch, salary below the requested minimum, or `min_years_required` above the candidate's experience. Pool trimmed to 15.
3. **Deep analysis** (per job): the LLM extracts required skills + ATS keywords from the job description (`job_skill_extractor.py`); `skill_gap.py` computes matched/missing skills and an overlap ratio against the candidate's skills; `ats/ats_scorer.py` checks the ATS keywords against the raw resume text and scores format.
4. **Blended ranking** (`ranker.py`):

   ```
   blended_score = 0.6 × vector_similarity + 0.4 × skill_overlap_ratio
   ```

   Results persisted to `match_results` with full transparency: scores, matched skills, missing skills, ATS found/missing keywords, and a natural-language explanation of the fit.

### Stage 8 — Review Workflow

- `GET /resumes/{resume_id}/matches` — read back stored matches instantly (no recompute), filterable by status.
- `PATCH /resumes/matches/{match_id}/status` — mark a match `saved` or `dismissed`.

The `missing_skills` per match are the direct input for the upcoming **resume tailoring** feature — the system already knows exactly what each job wants that the resume doesn't show.

---

## API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/auth/signup` | Create account (email + password, returns JWT) |
| `POST` | `/auth/login` | OAuth2 password login (returns JWT) |
| `GET` | `/auth/me` | Current user info |
| `GET` | `/resumes` | Current user's resumes (session restore) |
| `POST` | `/resumes/upload` | Upload PDF/DOCX (per-user dedup, auto-extracts in background) |
| `POST` | `/resumes/{id}/extract?force=` | Extract raw text (idempotent; runs automatically on upload) |
| `POST` | `/resumes/{id}/parse` | LLM → structured resume JSON |
| `POST` | `/resumes/{id}/embed` | Generate resume vector |
| `GET` | `/resumes/{id}/shortlist?top_n=40` | Raw vector-similarity shortlist (debug/preview) |
| `POST` | `/resumes/{id}/matches/generate?location_contains=&min_salary=` | Full matching pipeline |
| `GET` | `/resumes/{id}/matches?status=` | Read stored matches |
| `PATCH` | `/resumes/matches/{match_id}/status` | Save / dismiss a match |
| `POST` | `/resumes/matches/{match_id}/tailor` | LLM tailoring suggestions for that job (truthful rewrites, ATS keywords, honest gaps) |
| `POST` | `/resumes/matches/{match_id}/cover-letter` | Job-specific cover letter grounded in the parsed resume |
| `GET` | `/jobs/sources` | List available job source connectors |
| `POST` | `/jobs/ingest?query=&sources=&country=&location=&results=` | Scrape jobs from one or all sources (cross-source dedup) |
| `POST` | `/jobs/embed-pending` | Embed new jobs (pgvector) |
| `GET` | `/health` | Liveness check |

Interactive docs: `http://localhost:8000/docs` (Swagger, auto-generated).

---

## Database Schema (Neon PostgreSQL)

**`resumes`** — one row per unique file: `resume_id` (UUID, PK), `original_filename`, `stored_path`, `file_hash` (unique index — dedup), `status` (`uploaded` → `parsed`), `extracted_text`, `parsed_data` (JSON), `confidence_score`, `embedding` (cached), `uploaded_at`.

**`jobs`** — one row per scraped job: `job_id` (source's ID, PK), `title`, `company`, `location`, `description`, `salary_min/max`, `remote`, `min_years_required`, `apply_url`, `source`, `embedding` marker, `fetched_at`.

**`match_results`** — one row per resume×job evaluation: `match_id` (PK), `resume_id` + `job_id` (indexed), `vector_similarity`, `skill_overlap_ratio`, `blended_score`, `matched_skills` / `missing_skills` (JSON), `explanation`, `ats_score`, `ats_found_keywords` / `ats_missing_keywords` (JSON), `ats_format_score`, `status` (`new`/`saved`/`dismissed`), `generated_at`.

---

## Setup & Run

```bash
# 1. Clone and enter
git clone <repo-url> && cd AI-Job-Application-Agent

# 2. Virtual environment
python -m venv venv
venv\Scripts\activate        # Windows  (source venv/bin/activate on Linux/Mac)

# 3. Dependencies
pip install -r requirements.txt

# 4. Configure keys
copy .env.example .env       # then fill in every key (see API Keys table above)

# 5. Run — tables, pgvector extension, and indexes are created automatically at startup
uvicorn app.main:app --reload
```

> Note: the files in `alembic/versions/` describe the old (pre-hardening) schema. On a fresh Neon database the app bootstraps the current schema itself. When you next need a migration, delete the old version files and autogenerate a new baseline: `alembic revision --autogenerate -m "baseline"`.

Run the test suite with `pytest`.

Typical first workflow: `POST /jobs/ingest` → `POST /jobs/embed-pending` → `POST /resumes/upload` → `/extract` → `/parse` → `/embed` → `/matches/generate`.

---

## Production-Level Design Decisions

- **Fail-fast configuration** — the app refuses to boot with missing keys instead of dying mid-request.
- **Neon serverless Postgres** — the engine uses `pool_pre_ping=True` + `pool_recycle=300` so connections survive Neon's auto-suspend of idle databases; TLS enforced via `sslmode=require`.
- **Byte-level dedup** — identical uploads never create duplicate records or files.
- **Idempotent ingestion** — jobs are upserted by source ID; re-running ingest is always safe.
- **Layered architecture** — API routes → repositories (all DB access isolated) → services (pure logic) → models. No business logic in route handlers beyond orchestration.
- **Cost-aware pipeline** — LLM calls only run on the 15 hard-filtered finalists, never on all 40 retrieved jobs; embeddings are local and cached; `GET /matches` reads stored results without recomputing.
- **Anti-hallucination parsing** — strict prompt rules + Pydantic schema validation + explicit/inferred skill separation + confidence scoring.
- **Guardrails everywhere** — file size/type limits, near-empty extraction detection, garbage listing skips, status whitelist on match updates, proper HTTP codes (400/404/413/422).
- **Alembic migrations** — schema changes are versioned and reproducible across environments.

## Known Limitations & Planned Improvements

**Extraction quality — DONE**: column-aware PDF parsing, OCR fallback for scanned PDFs, DOCX table extraction, text cleanup before LLM parsing, magic-byte file validation, and auto-extraction on upload are all implemented.

**More job sources**: the `job_sources/` layer is built for it — LinkedIn/Indeed/Naukri clients plug in beside Adzuna.

**Resume tailoring & cover letters — DONE**: `POST /resumes/matches/{id}/tailor` returns a job-targeted summary, bullet rewrites, truthfully surfaceable skills (with evidence), ATS keywords to weave in, and honest gaps with learning suggestions. `POST /resumes/matches/{id}/cover-letter` writes a 250-350 word letter grounded strictly in the parsed resume. Both run on the premium model tier via the LLM Router and are prompt-constrained to never fabricate experience.

**Performance**: job-fit LLM analyses run in parallel (5 concurrent) during matching; the embedding model lazy-loads on first use.

**Production architecture — DONE**:
- **Schema hardening**: scores/salaries/experience are real `Float` columns (correct sorting & filtering), skills/keywords are `JSONB` (queryable), `match_results` has proper foreign keys with `ON DELETE CASCADE`, and resume embeddings live in pgvector alongside job vectors.
- **Auth**: set `API_KEY` in `.env` → every endpoint requires `X-API-Key` (timing-safe comparison); unset = open local dev.
- **Rate limiting**: per-IP sliding window (default 60 req/min, `RATE_LIMIT_PER_MINUTE`).
- **Observability**: request logging with latency, global error handler (no stack traces leak), `/health` checks DB reachability.
- **Tests**: `pytest` suite covering skill-gap scoring, hard filters, experience extraction, text cleaning, dedup keys, and the LLM router (routing, retries, overrides).

**Roadmap**:
1. **Auto-apply** — agent applies to saved matches automatically via the stored `apply_url`, submitting the tailored resume.
2. **File storage** — move resumes from local disk to object storage (S3-compatible) before cloud deployment.
