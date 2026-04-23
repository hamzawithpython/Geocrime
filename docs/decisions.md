# Architectural Decisions

This document records the significant technical decisions made during the GeoCrime agent extension project, with the reasoning behind each. Inspired by the Architectural Decision Record (ADR) format, kept lightweight.

## ADR-001: Separate folder and venv for agent extension

**Date:** 2026-04-21
**Status:** Accepted

### Context

GeoCrime is an existing Django web application for crime-aware route planning in Chicago. We are extending it with a multi-agent decision-support system using LangGraph, FastAPI, XGBoost, PostGIS, and other modern tooling. The new stack has substantially different and partially conflicting dependencies compared to the existing Django stack.

### Decision

We will keep the existing Django application untouched and add the new agent system in a top-level `agent/` folder within the same Git repository, with its own isolated Python virtual environment at `agent/.venv`. The new system may import from the Django code as a library when reuse is appropriate.

### Consequences

**Positive:**
- Existing app continues to work unmodified throughout the extension build
- No dependency conflicts between Django and agent stacks
- Recruiters can see both the original project and the extension narrative in one repository
- Each subsystem can be deployed independently if needed

**Negative:**
- Two venvs to manage and remember to activate
- Some duplication of code/data references when both stacks need access to crime data


## ADR-002: Feature branch workflow

**Date:** 2026-04-21
**Status:** Accepted

### Context

We need to develop the extension over several months while keeping a stable, working version of the existing Django app available at all times.

### Decision

All extension work happens on a long-lived `feature/agent-extension` branch. The `main` branch is preserved as the working Django app. Merges to `main` will only happen when the extension reaches stable milestones.

### Consequences

- Public GitHub history clearly distinguishes "the original app" from "the extension in progress"
- Anyone cloning `main` always gets a working Django app
- Branch may live for many months, requiring occasional rebasing if `main` receives bugfixes


## ADR-003: Use Docker for PostgreSQL/PostGIS instead of native install

**Date:** 2026-04-21
**Status:** Accepted

### Context

Phase 1 requires a PostgreSQL database with the PostGIS extension for spatial queries. Options include native Windows installation, WSL-hosted Postgres, or Docker.

### Decision

Use Docker with the official `postgis/postgis:16-3.4` image, run via Docker Compose for reproducibility.

### Consequences

**Positive:**
- Identical database environment on any machine that can run Docker
- Easy to start fresh by destroying and recreating the container
- No pollution of the Windows registry or system services
- Trivial to share the project setup with others

**Negative:**
- Requires Docker Desktop running, which uses noticeable system resources
- Slightly slower disk I/O than native install (acceptable for development)


## ADR-004: Conventional Commits for all extension work

**Date:** 2026-04-21
**Status:** Accepted

### Context

Public commit history is visible to recruiters and informs future-self when revisiting the project after time away.

### Decision

All commits on the `feature/agent-extension` branch use Conventional Commits format: `type: subject`, with optional body paragraphs. Types in use: `feat`, `fix`, `docs`, `chore`, `build`, `refactor`, `test`.

### Consequences

- Cleaner, scannable commit history
- Easier to generate changelogs later if needed
- Small upfront friction (need to think about commit type)


## ADR-005: Ingest 2020-present Chicago crime data, not full historical

**Date:** 2026-04-23
**Status:** Accepted

### Context

The Chicago Open Data Portal publishes crime records back to 2001 — approximately 8 million rows totaling ~2 GB as CSV. For the forecasting agent (Phase 2), we need enough historical pattern to capture seasonal and weekly cycles. For the geospatial agent (Phase 3), we care mostly about recent incidents. Ingesting the full dataset was the default instinct, but we stopped to question whether "more data" meant "better system."

### Decision

Ingest crimes from 2020-01-01 to present (~1.5M records, ~400 MB CSV). Future ingests will append new records rather than re-downloading historical data.

### Alternatives Considered

- **Full dataset (2001-present):** Maximum flexibility, but ~8 million rows means slower development queries, 5x the disk usage, and pre-2020 patterns are less predictive of post-pandemic Chicago.
- **Two years (2024-2026):** Too short for the forecasting agent — a strong seasonal model needs at least 3 complete yearly cycles to learn reliable patterns.

### Consequences

**Positive:**
- Forecasting agent has ~5 years of seasonal patterns (summer-winter cycles, weekday-weekend splits, monthly trends) — more than enough to converge.
- Ingest completes in ~5 minutes instead of ~25 minutes for full dataset.
- Spatial queries stay fast during development without aggressive optimization.

**Negative:**
- Pre-2020 analysis (e.g., tracking decade-long trends) is out of scope for this project.
- If the agent system ever needs longer history, a separate re-ingest is required.


## ADR-006: Run PostGIS on port 5439 instead of conventional 5432 or 5433

**Date:** 2026-04-23
**Status:** Accepted

### Context

The development machine had three pre-existing Windows-native PostgreSQL services (`postgresql-x64-13`, `-17`, `-18`) running simultaneously from previous projects. Additionally, during setup, a stray PostgreSQL process was bound to port 5433. Both 5432 and 5433 were silently contested — external TCP connections from Python were being routed to the wrong process, causing consistent authentication failures despite correct credentials.

### Decision

Bind the PostGIS Docker container to host port 5439 (`-p 5439:5432`). Internal container port remains 5432; only the host-facing port is relocated.

### Alternatives Considered

- **Uninstall the native Postgres services:** Long-term correct, but risks breaking other local projects that may depend on them. Deferred as a standalone cleanup task.
- **Stop native services temporarily:** Works until reboot; fragile and easy to forget.

### Consequences

**Positive:**
- Zero port conflicts; `agent/.env` unambiguously points to our container.
- No changes needed to existing Windows services.
- Documented quirk helps future readers of the repo understand why the unusual port appears everywhere.

**Negative:**
- `DB_PORT=5439` deviates from Postgres convention; every developer who clones the project must either read this ADR or hit the same conflict themselves.
- Long-term fix (cleaning up Windows services) is still owed.


## ADR-007: Use trust authentication for PostGIS in local development

**Date:** 2026-04-23
**Status:** Accepted (dev only — MUST change before any deployment)

### Context

The `postgis/postgis:16-3.4` Docker image has an initialization quirk: its entrypoint script sets up `pg_hba.conf` with `trust` auth for local connections and enforces `scram-sha-256` for external connections, but it doesn't set an actual password on the `postgres` user during first-run initialization — even though `POSTGRES_PASSWORD` is passed via environment. This results in external connections (from Python on the Windows host) failing with "password authentication failed" regardless of the password supplied. Attempts to set the password manually via `ALTER USER` did not resolve the issue during the initial session.

### Decision

For local development, modify `pg_hba.conf` to use `trust` authentication for all connection types. This means any connection claiming to be `postgres` is accepted without password verification.

### Alternatives Considered

- **Debug the auth issue further:** Time investment was already excessive; trust auth unblocked development immediately.
- **Switch to the official `postgres:16` image and install PostGIS manually:** Viable but adds its own setup complexity and divergence from upstream.

### Consequences

**Positive:**
- Unblocks all downstream development work.
- Standard pattern for local-only Postgres development (many tutorials use trust auth for this reason).

**Negative / Action Required:**
- **This configuration is unsafe for any deployment.** Before Phase 5 (deployment), we must:
  1. Set a real password on the `postgres` user.
  2. Create a non-superuser application role with limited privileges.
  3. Revert `pg_hba.conf` to require `scram-sha-256` for non-local connections.
  4. Store the password in a proper secrets manager, not `.env`.
- Container is only accessible from localhost, so risk is contained to the dev machine.


## ADR-008: Stored `geog` column for spatial index-aware distance queries

**Date:** 2026-04-23
**Status:** Accepted

### Context

Our `crimes.geom` column is of type `geometry(Point, 4326)`, which uses WGS84 coordinates (degrees). Distance queries in meters require casting to `geography` type: `ST_DWithin(geom::geography, point, 500)`. However, casting a column in the WHERE clause prevents PostgreSQL from using an index on that column, because the index is built on the raw values, not the transformed expression. A test query for "crimes within 500 m of Willis Tower in 2024" took ~1.2 seconds despite appropriate indexes existing, because the spatial index was bypassed.

### Decision

Add a STORED generated column `crimes.geog GEOGRAPHY(POINT, 4326) GENERATED ALWAYS AS (geom::geography) STORED`, plus a dedicated GIST index on it. Queries use `geog` directly, enabling the spatial index.

### Alternatives Considered

- **Rewrite queries using degree-based `ST_DWithin(geom, point, 0.0045)`:** Uses the existing geom index but approximates 500 meters with ~0.0045 degrees — crude, doesn't generalize, loses meter accuracy.
- **VIRTUAL generated column:** Computed at read-time, so it behaves identically to inline casting and provides no performance benefit.

### Consequences

**Positive:**
- Willis Tower 500m query dropped from 1,239 ms to 224 ms (5.5× speedup), with plan now showing `Bitmap Index Scan on idx_crimes_geog`.
- Pattern is idiomatic — same technique scales to future spatial columns or transformations.
- Automatic: writes to `geom` propagate to `geog` with no application code changes.

**Negative:**
- ~47 MB extra storage at 1.48M rows (negligible at this scale).
- One additional index to maintain during inserts (also negligible — ingest is batch, not real-time).


## ADR-009: Use Chicago Open Data Portal SODA API with date filter for ingest

**Date:** 2026-04-23
**Status:** Accepted

### Context

Chicago's Crimes dataset is distributed via Socrata's SODA API at `data.cityofchicago.org/resource/ijzp-q8t2.csv`. Options for bulk export include a manual CSV download from the website (entire ~8M record dataset, all or nothing) or programmatic access via SODA with filters.

### Decision

Download via SODA API with a server-side `$where=date>='2020-01-01T00:00:00.000'` filter and explicit `$limit=2000000`. This returns only the date range we need in a single HTTP request.

### Consequences

**Positive:**
- Reproducible — the exact URL is committed in the ingest context and can be re-run.
- Smaller download (~400 MB instead of ~2 GB).
- SODA's `$where` is server-side, so we aren't bandwidth-bound by the full dataset.

**Negative:**
- API silently caps responses at 1000 records if `$limit` is not specified — a common footgun. Always set explicitly.
- Future incremental ingests will need a separate date-range filter to avoid re-downloading existing data.