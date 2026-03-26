# Data Flow — Adaptive Learning System

## Pipeline Overview

```
Upload → Ingest → Distill → [Ready]
                                ↓
                    Generate Quiz → Take Quiz → Grade → Update Mastery
                         ↑                                    │
                         └────────── Adaptation Loop ─────────┘
```

---

## 1. Upload → Ingestion Pipeline

**Trigger**: User uploads a PDF via `POST /api/documents/`

### Steps

1. **Validation** — API validates file type (.pdf), file size (< 50MB), and filename
2. **Storage** — File saved to `./uploads/{document_id}/{filename}`
3. **Record creation** — `documents` row created with `status = "uploaded"`
4. **Background task launched** — `DocumentService.process_document()` runs async
5. **Status → "ingesting"** — Document status updated

6. **PDF parsing** (IngestionAgent)
   - Open PDF with `pdfplumber`
   - For each page:
     - Extract text via `page.extract_text()`
     - Extract tables via `page.extract_tables()` → format as pipe-delimited text
     - Split text into paragraphs (blank line delimiter)
     - Detect section headings (short lines, numbered patterns, ALL CAPS)
     - Track `section_path[]` as headings nest

7. **Chunking**
   - Merge paragraphs into chunks up to `CHUNK_SIZE_TOKENS` (1500)
   - Maintain `CHUNK_OVERLAP_TOKENS` (200) between consecutive chunks
   - Each chunk records: `text`, `section_path`, `page_start`, `page_end`, `chunk_type`, `token_count`

8. **Persist** — Save `document_chunks` rows to database

**Output**: `DocumentChunk[]` — each with text, page range, section path, chunk type

---

## 2. Distillation Pipeline

**Trigger**: Immediately after ingestion completes (same background task)

### Steps

1. **Status → "distilling"**

2. **Pass 1: Per-chunk extraction** (DistillationAgent)
   - Process chunks in batches of 2
   - For each batch, call Claude with extraction prompt:
     ```
     Extract every distinct concept from this text.
     For each: name, definition, concept_type, difficulty, importance, supporting_quote
     ONLY use information in the text. Do NOT add external knowledge.
     ```
   - Parse JSON response into `RawConcept[]`
   - Each concept tagged with its source `chunk_index`

3. **Pass 2: Global consolidation**
   - Send all raw concepts to Claude with consolidation prompt:
     ```
     Deduplicate, organize into topics, refine difficulty/importance scores.
     Do NOT invent new concepts.
     ```
   - Parse into `TopicResult[]`, each containing `ConceptResult[]`

4. **Persist**
   - Create `topics` rows (name, document_id, sort_order)
   - Create `concepts` rows (name, definition, type, difficulty, importance, source_chunk_ids, source_pages, supporting_quote)
   - Update `topic.concept_count`

5. **Status → "ready"**

**Output**: Knowledge graph stored in `topics` + `concepts` tables

**Data flow between passes**:
```
Chunks[0..N] → Pass 1 → RawConcept[] (name, definition, type, difficulty, importance, quote, chunk_idx)
                              ↓
                         Pass 2 → TopicResult[] → ConceptResult[] (deduplicated, organized, with source_chunk_indices)
```

---

## 3. Exam Generation Pipeline

**Trigger**: User requests `POST /api/exams/generate` with `{user_id, document_id, num_questions}`

### Steps

1. **Fetch concepts** — Load all concepts for the document, joined with topics
2. **Fetch mastery** — Load `user_concept_mastery` for this user + these concepts
3. **Concept selection** — Score each concept:
   ```
   priority = (1.0 - mastery_score) * 0.6 + importance * 0.4
   ```
   Sort descending, take top `num_questions`

4. **Question generation** (TestGenerationAgent)
   - Batch concepts into groups of 5
   - For each batch, call Claude:
     ```
     Generate ONE MCQ per concept. 4 options (A-D), one correct.
     Distractors must be plausible but incorrect.
     Include explanation and Bloom's taxonomy level.
     ```
   - Parse JSON into `GeneratedQuestion[]`

5. **Persist**
   - Create `exams` row (status = "generated")
   - Create `exam_questions` rows (question_text, options JSONB, correct_answer, explanation)

**Output**: `Exam` with `ExamQuestion[]`, served to frontend

**Key constraint**: Questions are generated WITH their answers and explanations simultaneously — this prevents answer drift between generation and grading.

---

## 4. Grading Pipeline

**Trigger**: User submits `POST /api/exams/{id}/submit` with `{answers: [{question_id, answer}]}`

### Steps

1. **Load exam** — Fetch exam with questions
2. **Grade each question** — Deterministic comparison:
   ```python
   is_correct = user_answer.strip().upper() == correct_answer.strip().upper()
   ```
3. **Save responses** — Create `exam_responses` rows with `user_answer`, `is_correct`
4. **Calculate score** — `score = correct_count`, `max_score = total_questions`
5. **Update mastery** — For each question, call `MasteryService.update_mastery()`
6. **Update exam** — Set `status = "graded"`, `completed_at = now()`

**Output**: `ExamResult` with per-question breakdown (question, user answer, correct answer, is_correct, explanation)

---

## 5. Mastery Update Pipeline

**Trigger**: Called by grading pipeline for each answered question

### Steps

1. **Load or create** `user_concept_mastery` record for (user_id, concept_id)
2. **Update counters**:
   ```python
   mastery.attempts += 1
   if is_correct:
       mastery.correct += 1
   mastery.mastery_score = mastery.correct / mastery.attempts
   mastery.last_tested_at = now()
   ```
3. **Persist** — Save updated mastery

**Phase 2 upgrade**: Replace `% correct` with Bayesian Knowledge Tracing:
```python
# BKT update (future)
p_know = bkt_update(prior_p_know, p_learn, p_slip, p_guess, is_correct)
```

---

## 6. Adaptation Loop

The adaptation happens implicitly through the concept selection algorithm in step 3 of the exam generation pipeline:

```
User takes quiz → scores graded → mastery updated per concept
                                         ↓
Next quiz request → concept selection prioritizes:
  - Low mastery concepts (weight 0.6)
  - High importance concepts (weight 0.4)
                                         ↓
Questions generated for weak areas → user takes quiz → ...
```

**Phase 2 additions**:
- Prerequisite checking: don't test concept X if prerequisites aren't mastered
- Spaced repetition: factor in `time_since_last_test` and `next_review_at`
- Difficulty calibration: target ~70% success rate for optimal learning
