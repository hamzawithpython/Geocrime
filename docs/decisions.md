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