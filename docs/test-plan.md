# Test Plan — Phase 1 MVP

## Overview

This test plan covers the complete Phase 1 pipeline: PDF upload → knowledge extraction → quiz generation → grading → mastery tracking. Tests are organized by layer (unit, integration, end-to-end) and by feature.

---

## Test Materials

Prepare these before testing:

| File | Description | Purpose |
|------|-------------|---------|
| `sample-simple.pdf` | 3-5 page PDF with clear headings and short paragraphs | Happy path testing |
| `sample-textbook.pdf` | 15-20 page real textbook chapter with tables, formulas | Realistic content |
| `sample-empty.pdf` | PDF with no extractable text (scanned image) | Error handling |
| `sample-large.pdf` | 60+ MB PDF | File size limit testing |
| `not-a-pdf.txt` | A text file renamed to .txt | File type validation |

---

## 1. Document Upload & Validation

### 1.1 API: `POST /api/documents/`

| # | Test Case | Input | Expected Result |
|---|-----------|-------|-----------------|
| 1.1.1 | Upload valid PDF | `sample-simple.pdf`, valid user_id | 200, document returned with `status: "uploaded"` |
| 1.1.2 | Upload without user_id | `sample-simple.pdf`, no user_id | 422, validation error |
| 1.1.3 | Upload non-PDF file | `not-a-pdf.txt` | 400, "Unsupported file type" |
| 1.1.4 | Upload oversized file | `sample-large.pdf` (>50MB) | 400, "File too large" |
| 1.1.5 | Upload with no file | Empty request | 422, validation error |
| 1.1.6 | Upload with invalid user_id | `sample-simple.pdf`, `user_id=not-a-uuid` | 422, validation error |
| 1.1.7 | File is saved to disk | Upload any valid PDF | File exists at `./uploads/{doc_id}/{filename}` |

### 1.2 API: `GET /api/documents/`

| # | Test Case | Input | Expected Result |
|---|-----------|-------|-----------------|
| 1.2.1 | List documents for user with docs | Valid user_id | 200, array of documents |
| 1.2.2 | List documents for user with no docs | New user_id | 200, empty array |
| 1.2.3 | Response includes counts | User with processed doc | `topic_count` and `concept_count` are populated |

### 1.3 API: `GET /api/documents/{id}`

| # | Test Case | Input | Expected Result |
|---|-----------|-------|-----------------|
| 1.3.1 | Get existing document | Valid document_id | 200, document with status |
| 1.3.2 | Get non-existent document | Random UUID | 404 |

---

## 2. Ingestion Pipeline

### 2.1 IngestionAgent Unit Tests

| # | Test Case | Input | Expected Result |
|---|-----------|-------|-----------------|
| 2.1.1 | Parse simple PDF | `sample-simple.pdf` | Returns `ChunkResult[]` with text content |
| 2.1.2 | Chunks have page numbers | Any PDF | Every chunk has `page_start` and `page_end` set |
| 2.1.3 | Chunks respect token limit | PDF with long sections | No chunk exceeds `CHUNK_SIZE_TOKENS` (1500) |
| 2.1.4 | Chunks have overlap | PDF with multiple chunks | Last ~200 tokens of chunk N appear at start of chunk N+1 |
| 2.1.5 | Section headings detected | PDF with numbered headings (1.1, 1.2) | `section_path` is populated on chunks |
| 2.1.6 | Tables extracted | PDF with tables | At least one chunk with `chunk_type: "table"` |
| 2.1.7 | Empty pages skipped | PDF with blank pages | No chunks generated for empty pages |
| 2.1.8 | Unsupported file type | `.docx` file path | Raises `ValueError` |

### 2.2 Integration: Upload → Ingestion

| # | Test Case | Input | Expected Result |
|---|-----------|-------|-----------------|
| 2.2.1 | Status transitions | Upload `sample-simple.pdf` | Status changes: `uploaded` → `ingesting` → `distilling` → `ready` |
| 2.2.2 | Chunks saved to DB | Upload and wait for processing | `document_chunks` table has rows for this document |
| 2.2.3 | Page count updated | Upload and wait | `documents.page_count` matches actual PDF page count |
| 2.2.4 | Error handling | Upload `sample-empty.pdf` | Status becomes `error`, `error_message` is set |

---

## 3. Knowledge Distillation

### 3.1 DistillationAgent Unit Tests

| # | Test Case | Input | Expected Result |
|---|-----------|-------|-----------------|
| 3.1.1 | Extracts concepts from chunks | 3 chunks about biology | Returns `DistillationResult` with concepts |
| 3.1.2 | Concepts have required fields | Any valid chunks | Every concept has: name, definition, concept_type, difficulty, importance |
| 3.1.3 | Supporting quotes present | Chunks with factual content | Most concepts have `supporting_quote` that appears in source text |
| 3.1.4 | Concept types are valid | Any chunks | `concept_type` is one of: definition, theorem, process, fact, formula, example, principle |
| 3.1.5 | Difficulty in range | Any chunks | All `difficulty` values between 0.0 and 1.0 |
| 3.1.6 | Importance in range | Any chunks | All `importance` values between 0.0 and 1.0 |
| 3.1.7 | Topics created | Multiple chunks | At least 1 topic in result |
| 3.1.8 | Every concept has a topic | Any chunks | No orphaned concepts |
| 3.1.9 | Deduplication works | Chunks with overlapping content | No duplicate concept names in output |
| 3.1.10 | Empty chunks handled | Chunks with no meaningful content | Returns empty result, no crash |

### 3.2 Integration: Distillation → Database

| # | Test Case | Input | Expected Result |
|---|-----------|-------|-----------------|
| 3.2.1 | Topics saved | Process `sample-simple.pdf` | `topics` table has rows for this document |
| 3.2.2 | Concepts saved | Process `sample-simple.pdf` | `concepts` table has rows linked to topics |
| 3.2.3 | Source chunk IDs mapped | Process any PDF | `concepts.source_chunk_ids` references valid chunk IDs |
| 3.2.4 | Source pages populated | Process any PDF | `concepts.source_pages` has valid page numbers |
| 3.2.5 | Topic concept_count accurate | Process any PDF | `topics.concept_count` matches actual concept count per topic |

### 3.3 Source Grounding Verification

| # | Test Case | How to verify | Pass criteria |
|---|-----------|---------------|---------------|
| 3.3.1 | Concepts are grounded in source | Compare `supporting_quote` against original PDF text | Quote exists verbatim (or near-verbatim) in the source |
| 3.3.2 | No hallucinated concepts | Review 20 extracted concepts manually | All concepts traceable to source material |
| 3.3.3 | Definitions are accurate | Compare definitions against source text | Definitions reflect source, not external knowledge |

---

## 4. Quiz Generation

### 4.1 API: `POST /api/exams/generate`

| # | Test Case | Input | Expected Result |
|---|-----------|-------|-----------------|
| 4.1.1 | Generate quiz | `{user_id, document_id, num_questions: 10}` | 200, exam with `status: "generated"`, `question_count: 10` |
| 4.1.2 | Generate for unprocessed doc | Document with `status: "ingesting"` | 400, "No concepts found" |
| 4.1.3 | Generate with custom count | `num_questions: 5` | Exam with 5 questions |
| 4.1.4 | Generate for non-existent doc | Random UUID | 400 |

### 4.2 API: `GET /api/exams/{id}`

| # | Test Case | Input | Expected Result |
|---|-----------|-------|-----------------|
| 4.2.1 | Get exam with questions | Valid exam_id | 200, exam with questions array |
| 4.2.2 | Answers not exposed | Get ungraded exam | Questions have options but NO `is_correct` field |
| 4.2.3 | Non-existent exam | Random UUID | 404 |

### 4.3 TestGenerationAgent Unit Tests

| # | Test Case | Input | Expected Result |
|---|-----------|-------|-----------------|
| 4.3.1 | Generates correct number | 5 concepts, `num_questions=5` | Returns 5 questions |
| 4.3.2 | Each question has 4 options | Any concepts | All questions have exactly 4 options (A, B, C, D) |
| 4.3.3 | Exactly one correct answer | Any concepts | Each question has exactly 1 option with `is_correct: true` |
| 4.3.4 | No "all/none of the above" | Any concepts | No option text contains "all of the above" or "none of the above" |
| 4.3.5 | Explanation provided | Any concepts | Every question has non-empty `explanation` |
| 4.3.6 | Bloom level assigned | Any concepts | Every question has `bloom_level` in [remember, understand, apply, analyze] |
| 4.3.7 | Questions are grounded | Review 10 questions manually | Correct answer is supported by the source concept definition/quote |
| 4.3.8 | Distractors are plausible | Review 10 questions manually | Wrong answers are related to the topic, not obviously absurd |

### 4.4 Concept Selection (Adaptive)

| # | Test Case | Setup | Expected Result |
|---|-----------|-------|-----------------|
| 4.4.1 | First quiz: selects by importance | New user, no mastery data | Higher-importance concepts prioritized |
| 4.4.2 | Second quiz: targets weak areas | User scored 0% on concepts A,B and 100% on C,D | Next quiz prioritizes A and B |
| 4.4.3 | Mix of topics | Document with 3+ topics | Questions drawn from multiple topics, not just one |

---

## 5. Grading

### 5.1 API: `POST /api/exams/{id}/submit`

| # | Test Case | Input | Expected Result |
|---|-----------|-------|-----------------|
| 5.1.1 | Submit all correct | All answers match correct_answer | Score = question_count, all `is_correct: true` |
| 5.1.2 | Submit all wrong | All answers are wrong letter | Score = 0, all `is_correct: false` |
| 5.1.3 | Submit partial | Mix of correct and wrong | Score reflects actual correct count |
| 5.1.4 | Case insensitive | Answer "b" when correct is "B" | Marked correct |
| 5.1.5 | Missing answers | Only answer 3 of 10 | Unanswered questions marked incorrect |
| 5.1.6 | Double submit | Submit same exam twice | 400, "Exam already graded" |
| 5.1.7 | Explanation returned | Any submission | Every question result includes `explanation` |
| 5.1.8 | Correct answer revealed | Any submission | Every question result includes `correct_answer` |

### 5.2 API: `GET /api/exams/{id}/results`

| # | Test Case | Input | Expected Result |
|---|-----------|-------|-----------------|
| 5.2.1 | Get graded results | Exam that was submitted | 200, full results with per-question breakdown |
| 5.2.2 | Get ungraded exam results | Exam not yet submitted | 404, "not graded yet" |

---

## 6. Mastery Tracking

### 6.1 MasteryService Unit Tests

| # | Test Case | Setup | Expected Result |
|---|-----------|-------|-----------------|
| 6.1.1 | First attempt correct | No prior mastery | `mastery_score: 1.0`, `attempts: 1`, `correct: 1` |
| 6.1.2 | First attempt wrong | No prior mastery | `mastery_score: 0.0`, `attempts: 1`, `correct: 0` |
| 6.1.3 | Score updates correctly | 3 attempts, 2 correct | `mastery_score: 0.667`, `attempts: 3`, `correct: 2` |
| 6.1.4 | last_tested_at updated | Any attempt | Timestamp is recent |

### 6.2 API: `GET /api/documents/{id}/mastery`

| # | Test Case | Setup | Expected Result |
|---|-----------|-------|-----------------|
| 6.2.1 | No mastery yet | User never took a quiz | 200, empty array |
| 6.2.2 | After one quiz | User completed one quiz | Returns mastery per topic with scores |
| 6.2.3 | Aggregation correct | User answered 2/3 correct in topic A | Topic A mastery ≈ 0.67 |
| 6.2.4 | Multiple topics | User answered questions across topics | Each topic has independent mastery |

---

## 7. End-to-End Tests

These test the full pipeline through the API, simulating a real user flow.

### 7.1 Happy Path

```
1. POST /api/documents/          → Upload sample-simple.pdf
2. Poll GET /api/documents/{id}  → Wait for status = "ready"
3. GET /api/documents/{id}/topics → Verify topics and concepts extracted
4. POST /api/exams/generate      → Generate 10-question quiz
5. GET /api/exams/{id}           → Verify 10 questions, 4 options each, no answers exposed
6. POST /api/exams/{id}/submit   → Submit answers (mix of correct/wrong)
7. Verify response has score, per-question results, explanations
8. GET /api/documents/{id}/mastery → Verify mastery scores reflect quiz results
9. POST /api/exams/generate      → Generate second quiz
10. Verify second quiz prioritizes concepts the user got wrong
```

**Pass criteria**: All steps succeed, status transitions are correct, mastery updates reflect performance, second quiz adapts to weaknesses.

### 7.2 Error Recovery

```
1. Upload sample-empty.pdf (no text)
2. Wait for processing
3. Verify status = "error" with meaningful error_message
4. Upload sample-simple.pdf (valid)
5. Verify it processes successfully despite previous error
```

### 7.3 Multiple Documents

```
1. Upload document A (biology chapter)
2. Upload document B (history chapter)
3. Wait for both to process
4. Generate quiz for document A → verify questions are about biology
5. Generate quiz for document B → verify questions are about history
6. Check mastery for A and B are independent
```

---

## 8. Frontend Smoke Tests

Manual tests in the browser at `http://localhost:3000`.

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 8.1 | Home page loads | Navigate to `/` | "Your Documents" heading, upload button visible |
| 8.2 | Upload flow | Click upload, select PDF | Document appears in list with "uploaded" status |
| 8.3 | Status polling | Wait after upload | Status updates through ingesting → distilling → ready |
| 8.4 | Document detail | Click a "ready" document | Topics listed, expandable to show concepts |
| 8.5 | Concept display | Expand a topic | Concepts show name, definition, type badge, supporting quote |
| 8.6 | Quiz generation | Click "Practice Quiz" | Redirects to quiz page with first question |
| 8.7 | Answer selection | Click an option | Option highlights blue, answer recorded |
| 8.8 | Question navigation | Click numbered buttons and Next/Previous | Can navigate between questions, answers persist |
| 8.9 | Submit quiz | Answer questions, click Submit | Results page shows score, correct/wrong per question |
| 8.10 | Results display | View results | Correct answers green, wrong answers red, explanations shown |
| 8.11 | Mastery bars | Return to document detail after quiz | Mastery progress bars visible per topic |
| 8.12 | Error document | Upload empty PDF, wait | Shows "error" status with error message |

---

## 9. Performance Benchmarks

Not pass/fail — measure and record baselines for future comparison.

| Metric | How to measure | Target |
|--------|----------------|--------|
| PDF processing time (5 pages) | Time from upload to `status: ready` | < 60s |
| PDF processing time (20 pages) | Same | < 3 min |
| Quiz generation time (10 questions) | Time from generate request to response | < 30s |
| Concepts per page | Count concepts / page count | 3-10 per page |
| API response time (list documents) | Measure `GET /api/documents/` latency | < 200ms |
| API response time (get topics) | Measure `GET /api/documents/{id}/topics` latency | < 500ms |

---

## Running Tests

```bash
# Unit + integration tests (once test files are written)
cd backend && pytest

# Manual E2E: start the system, then follow section 7 and 8
make dev
```
