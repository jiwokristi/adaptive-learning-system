# Architecture — Adaptive Learning System

## Overview

AI-powered adaptive learning system that turns uploaded study materials (PDFs) into structured knowledge, generates exam simulations, grades answers, tracks performance, and adapts future tests based on mastery.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js 14)                        │
│  Upload │ Document Viewer │ Quiz Interface │ Results │ Dashboard    │
└────────────────────────────┬────────────────────────────────────────┘
                             │ REST API (proxied /api/*)
┌────────────────────────────▼────────────────────────────────────────┐
│                        API LAYER (FastAPI)                           │
│  /api/documents  │  /api/exams  │  /health                         │
│  Upload, List, Detail, Topics, Mastery │ Generate, Submit, Results  │
└──────┬──────────────────────┬───────────────────────────────────────┘
       │                      │
┌──────▼──────────┐  ┌───────▼────────────────────────────────────┐
│  BACKGROUND     │  │  SERVICE LAYER                               │
│  TASKS          │  │  DocumentService  ExamService  MasteryService│
│  (FastAPI)      │  │  Orchestrate agents + DB operations          │
└─────────────────┘  └──────────────┬──────────────────────────────┘
                                    │
                     ┌──────────────▼──────────────────────┐
                     │  AGENT LAYER                         │
                     │  IngestionAgent    (PDF → chunks)    │
                     │  DistillationAgent (chunks → graph)  │
                     │  TestGenAgent      (concepts → MCQs) │
                     └──────────────┬──────────────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────┐
       │                            │                        │
┌──────▼──────┐  ┌─────────────────▼──────┐  ┌─────────────▼─────┐
│ PostgreSQL  │  │ Local Filesystem       │  │ Claude API        │
│ + pgvector  │  │ (uploaded documents)   │  │ (Sonnet/Opus)     │
│             │  │                        │  │                   │
│ - users     │  │ ./uploads/{doc_id}/    │  │ Extraction,       │
│ - documents │  │                        │  │ Question gen      │
│ - chunks    │  └────────────────────────┘  └───────────────────┘
│ - topics    │
│ - concepts  │
│ - exams     │
│ - mastery   │
└─────────────┘
```

## Tech Stack

| Layer           | Technology                  | Rationale                                                |
|-----------------|-----------------------------|----------------------------------------------------------|
| Frontend        | Next.js 14 (App Router)     | SSR, file upload UX, TypeScript, Tailwind CSS            |
| Backend         | FastAPI (Python 3.12)       | Best LLM ecosystem, async native, Pydantic validation    |
| Database        | PostgreSQL 16 + pgvector    | Structured + vector data in one DB, simple ops           |
| File storage    | Local filesystem (MVP)      | S3/MinIO in production                                   |
| Background jobs | FastAPI BackgroundTasks      | Celery+Redis when needed                                 |
| LLM             | Claude (Anthropic API)      | Sonnet for throughput, Opus for high-stakes tasks        |
| Monitoring      | Python logging (MVP)        | OpenTelemetry + Grafana later                            |

## Agent Definitions

| Agent              | Role                                         | Inputs                              | Outputs                                    | Trigger                     |
|--------------------|----------------------------------------------|--------------------------------------|--------------------------------------------|-----------------------------|
| IngestionAgent     | Parse PDF into structured text chunks        | File path, file type                 | `ChunkResult[]` (text, pages, sections)    | On document upload          |
| DistillationAgent  | Extract concepts and topics from chunks      | `ChunkResult[]`                      | `DistillationResult` (topics + concepts)   | After ingestion completes   |
| TestGenAgent       | Generate MCQ questions from concepts         | `ConceptForQuiz[]`, num_questions    | `GeneratedQuestion[]` with answers/rubrics | On quiz generation request  |
| MCQ Grading        | Grade objective answers (deterministic)      | User answers + correct answers       | Score, per-question results                | On exam submission          |
| MasteryService     | Track % correct per concept                  | Grading results                      | Updated mastery scores                     | After grading               |

### Phase 2+ Agents (not yet implemented)
- **Essay Grading Agent** — Multi-pass rubric-based grading with adjudication
- **Summary Generation Agent** — Cheat sheets and study materials from knowledge graph
- **Retrieval Controller** — Routes between vector search and structured queries
- **Performance Analyzer** — BKT-based mastery tracking with spaced repetition

## Data Model

```sql
-- Users (MVP: no auth, hardcoded user ID)
users (id UUID PK, email, name, created_at)

-- Uploaded documents
documents (id UUID PK, user_id FK, filename, file_type, storage_path,
           status [uploaded→ingesting→distilling→ready→error],
           page_count, error_message, created_at)

-- Parsed text chunks with optional embeddings
document_chunks (id UUID PK, document_id FK, chunk_index, text,
                 section_path TEXT[], page_start, page_end,
                 chunk_type [prose|table|list], token_count,
                 embedding VECTOR(1536), created_at)

-- Topic hierarchy
topics (id UUID PK, document_id FK, name, parent_topic_id FK self,
        depth, sort_order, concept_count)

-- Atomic knowledge units
concepts (id UUID PK, topic_id FK, name, definition, concept_type
          [definition|theorem|process|fact|formula|example|principle],
          difficulty 0.0-1.0, importance 0.0-1.0,
          source_chunk_ids UUID[], source_pages INT[],
          supporting_quote, metadata JSONB, embedding VECTOR(1536),
          created_at)

-- Generated exams
exams (id UUID PK, user_id FK, document_id FK,
       status [generated→in_progress→submitted→graded],
       question_count, score, max_score, created_at, completed_at)

-- Individual questions within an exam
exam_questions (id UUID PK, exam_id FK, concept_id FK, question_index,
               question_text, question_type, options JSONB,
               correct_answer, explanation, bloom_level, difficulty)

-- User answers
exam_responses (id UUID PK, exam_question_id FK, user_answer,
               is_correct, answered_at)

-- Per-concept mastery tracking
user_concept_mastery (user_id FK, concept_id FK, — composite PK
                      mastery_score 0.0-1.0, attempts, correct,
                      last_tested_at)
```

## API Endpoints

| Method | Path                              | Description                          |
|--------|-----------------------------------|--------------------------------------|
| POST   | `/api/documents/`                 | Upload PDF, start processing         |
| GET    | `/api/documents/`                 | List user's documents                |
| GET    | `/api/documents/{id}`             | Get document details + status        |
| GET    | `/api/documents/{id}/topics`      | Get topics with concepts             |
| GET    | `/api/documents/{id}/mastery`     | Get mastery breakdown by topic       |
| POST   | `/api/exams/generate`             | Generate quiz for a document         |
| GET    | `/api/exams/{id}`                 | Get exam with questions (no answers) |
| POST   | `/api/exams/{id}/submit`          | Submit answers, get graded results   |
| GET    | `/api/exams/{id}/results`         | Get results for a graded exam        |
| GET    | `/health`                         | Health check                         |

## Phase Breakdown

### Phase 1 — MVP (current)
- PDF upload + pdfplumber text extraction
- Knowledge distillation → flat concept list organized by topic
- MCQ generation (up to 10 per quiz)
- Deterministic MCQ grading
- Basic mastery tracking (% correct per concept)
- Minimal frontend: upload → view topics → take quiz → see results

### Phase 2 — Intelligence Layer
- Concept relationships + prerequisite tracking
- BKT-based mastery model (replaces % correct)
- Adaptive question selection (prioritize weak areas)
- Essay questions + single-pass LLM grading
- Summary / cheat sheet generation
- PPT support

### Phase 3 — Production Quality
- Multi-pass essay grading with adjudication
- Spaced repetition scheduling
- Full agent orchestration with observability
- Model tiering (Haiku/Sonnet/Opus by task)
- Analytics dashboard with learning curves
- Enriched mode (controlled external knowledge)
