# ADR-004: Structured Knowledge Graph over Embeddings-Only Approach

**Status**: Accepted
**Date**: 2026-03-26

## Context

Most RAG-based educational tools use a simple architecture: embed document chunks → vector search → generate answers. This works for Q&A but fails for adaptive learning because embeddings cannot represent:
- Prerequisite relationships
- Concept difficulty
- Mastery per concept
- Topic hierarchy

We need to decide between an embeddings-only approach and a structured knowledge graph that exists alongside embeddings.

## Decision

Build a structured knowledge graph (concepts, relationships, topics) as the primary knowledge representation. Use embeddings as a complementary retrieval mechanism for fuzzy/semantic search.

## Capability Comparison

| Capability                                    | Embeddings Only | Knowledge Graph + Embeddings |
|-----------------------------------------------|-----------------|------------------------------|
| "Find content about topic X"                  | Yes (fuzzy)     | Yes (exact + fuzzy)          |
| "What are the prerequisites for concept X?"   | Cannot do       | Direct graph traversal       |
| "Which topics is the student weakest in?"     | No structure     | Aggregate mastery up topic tree |
| "Generate a question at difficulty 0.6"       | No metadata      | Filter concepts by difficulty |
| "What concepts did this question test?"       | No mapping       | Explicit concept_ids_tested  |
| "Show me concepts similar to X"              | Yes             | Yes                          |
| "What are the key formulas in chapter 3?"     | Unreliable       | Filter by type + section     |
| "Track mastery of specific concepts"          | No structure     | Per-concept mastery scores   |
| "Identify knowledge gaps"                     | Cannot do       | Compare mastery across graph |
| "Adaptive question selection"                 | Cannot do       | Query by mastery + importance + difficulty |

## Knowledge Graph Schema

```
Topics (hierarchical)
  └── Concepts (atomic knowledge units)
        ├── name, definition, type, difficulty, importance
        ├── source_chunk_ids (provenance)
        ├── supporting_quote (exact source text)
        └── embedding (for semantic search)

Relationships (Phase 2)
  └── prerequisite, related, example_of, contrasts_with, part_of
```

## Extraction Pipeline

Two-pass LLM extraction:
1. **Per-chunk extraction**: Extract concepts independently from each chunk (parallelizable)
2. **Global consolidation**: Deduplicate, organize into topics, establish relationships

This is more expensive than simple embedding, but produces a queryable knowledge structure.

## Consequences

**Positive**:
- Enables adaptive learning features impossible with embeddings alone
- The knowledge graph IS the product differentiator
- Structured queries are fast, deterministic, and debuggable
- Provenance tracking (every concept traces back to source text)
- Supports prerequisite chains, gap analysis, difficulty ordering

**Negative**:
- More expensive extraction (2 LLM passes vs 1 embedding call)
- Extraction quality depends on LLM reliability
- Schema is more rigid — new concept types require schema changes
- Graph quality varies with document quality (noisy PDFs → noisy graphs)

**Mitigation**:
- Quality scoring during extraction: flag low-confidence concepts
- User can review and correct extracted concepts (Phase 3)
- Embeddings still available as fallback for fuzzy retrieval
- Schema uses JSONB metadata field for flexibility
