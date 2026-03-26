# Adaptive Learning System

AI-powered adaptive learning system that turns uploaded study materials (PDFs) into structured knowledge, generates exam simulations, grades answers, and adapts future tests based on your mastery.

## How It Works

1. **Upload** a PDF (textbook chapter, lecture notes, etc.)
2. The system **extracts and structures** key concepts, definitions, and facts
3. **Take a quiz** — AI generates multiple-choice questions grounded in your material
4. **Get graded** with explanations for every answer
5. **Track mastery** — the system identifies your weak areas and targets them in future quizzes

## Architecture

```
Next.js Frontend → FastAPI Backend → Claude AI (Anthropic)
                                   → PostgreSQL + pgvector
```

**Multi-agent pipeline:**
- **Ingestion Agent** — Parses PDFs into structured text chunks
- **Distillation Agent** — Extracts concepts, topics, and definitions (two-pass LLM pipeline)
- **Test Generation Agent** — Creates MCQs with answers, explanations, and Bloom's taxonomy levels
- **Mastery Tracker** — Tracks performance per concept, prioritizes weak areas in future quizzes

See [docs/architecture.md](docs/architecture.md) for the full system design and [docs/data-flow.md](docs/data-flow.md) for the step-by-step pipeline.

## Tech Stack

| Layer     | Technology                        |
|-----------|-----------------------------------|
| Frontend  | Next.js 14, TypeScript, Tailwind  |
| Backend   | FastAPI, Python 3.12+             |
| Database  | PostgreSQL 16 + pgvector          |
| AI        | Claude (Anthropic API)            |
| Infra     | Docker Compose                    |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker
- [Anthropic API key](https://console.anthropic.com/)

### Setup (first time)

```bash
# Start database and install dependencies
make setup

# Add your API key
nano backend/.env   # set ANTHROPIC_API_KEY=sk-ant-...

# Create database tables and seed test user
make migrate
make seed
```

### Run

```bash
make dev
```

This starts both servers:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

Ctrl+C stops everything.

### Other Commands

```bash
make backend    # start backend only
make frontend   # start frontend only
make stop       # shut down database
```

See [docs/makefile-guide.md](docs/makefile-guide.md) for a detailed breakdown of every command.

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── agents/        # LLM-powered agents (ingestion, distillation, test generation)
│   │   ├── api/           # FastAPI route handlers
│   │   ├── models/        # SQLAlchemy database models
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── services/      # Business logic orchestration
│   │   └── main.py        # FastAPI app entrypoint
│   └── alembic/           # Database migrations
├── frontend/
│   └── src/
│       ├── app/           # Next.js pages (upload, document view, quiz, results)
│       └── lib/           # API client
├── docs/
│   ├── architecture.md    # System design
│   ├── data-flow.md       # Pipeline documentation
│   ├── makefile-guide.md  # Command reference
│   └── adr/               # Architecture Decision Records
└── docker-compose.yml     # PostgreSQL + Redis
```

## Architecture Decision Records

- [ADR-001: BKT over IRT](docs/adr/001-bkt-over-irt.md) — Why Bayesian Knowledge Tracing for mastery modeling
- [ADR-002: pgvector over Pinecone](docs/adr/002-pgvector-over-pinecone.md) — Why a single database for structured + vector data
- [ADR-003: Multi-pass grading](docs/adr/003-multi-pass-grading.md) — Consistent essay grading design
- [ADR-004: Knowledge graph over embeddings](docs/adr/004-knowledge-graph-over-embeddings.md) — Why structured knowledge extraction matters

## Roadmap

- [x] **Phase 1 (MVP)** — PDF upload, concept extraction, MCQ generation, basic mastery tracking
- [ ] **Phase 2** — Concept relationships, BKT mastery model, adaptive difficulty, essay grading
- [ ] **Phase 3** — Multi-pass grading, spaced repetition, analytics dashboard, model tiering

## License

MIT
