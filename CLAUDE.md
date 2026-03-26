# Adaptive Learning System

AI-powered adaptive learning system that turns uploaded study materials into structured knowledge, summaries, and exam simulations.

## Project Structure

- `backend/` — FastAPI backend (Python 3.12)
- `frontend/` — Next.js 14 frontend (App Router)
- `docs/` — Architecture docs and ADRs

## Backend

### Setup
```bash
cd backend
pip install -e ".[dev]"
```

### Run
```bash
# Start PostgreSQL + Redis
docker compose up -d

# Run migrations
cd backend && alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

### Key directories
- `app/models/` — SQLAlchemy models (User, Document, DocumentChunk, Topic, Concept, Exam, ExamQuestion, ExamResponse, UserConceptMastery)
- `app/agents/` — LLM-powered agents (ingestion, distillation, test_generation)
- `app/services/` — Business logic (document_service, exam_service, mastery_service)
- `app/api/` — FastAPI route handlers
- `app/schemas/` — Pydantic request/response schemas

### Architecture
- Agents are the LLM orchestration layer — each has a single responsibility
- Services coordinate agents and database operations
- API routes are thin — delegate to services
- All DB operations are async (asyncpg + SQLAlchemy async)
- Background tasks handle document processing (ingestion + distillation)

### Database
- PostgreSQL 16 with pgvector extension
- Alembic for migrations
- Key tables: documents, document_chunks, topics, concepts, exams, exam_questions, user_concept_mastery

## Frontend

### Setup
```bash
cd frontend
npm install
npm run dev
```

## Current Phase: MVP (Phase 1)
- PDF upload + text extraction
- Knowledge distillation (flat concept list)
- MCQ generation and deterministic grading
- Basic mastery tracking (% correct per topic)

## Conventions
- Use async/await everywhere in backend
- UUID primary keys on all models
- Pydantic for all API schemas
- Claude API via anthropic Python SDK
- No auth in MVP — user_id passed as query param
