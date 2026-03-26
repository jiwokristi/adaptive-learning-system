# ADR-002: Use PostgreSQL + pgvector over Dedicated Vector Database

**Status**: Accepted
**Date**: 2026-03-26

## Context

We need vector similarity search for:
- Semantic retrieval of source passages (grounding agent outputs)
- Concept deduplication during distillation
- Future: free-form user questions about their study material

Options considered:
- **Pinecone** — Managed vector DB, excellent performance at scale
- **Weaviate** — Open-source, hybrid search, self-hostable
- **Qdrant** — Open-source, Rust-based, fast
- **PostgreSQL + pgvector** — Vector extension for Postgres

## Decision

Use PostgreSQL with the pgvector extension. Store embeddings alongside structured data in the same database.

## Rationale

1. **We need both structured and vector queries on the same data.** Concepts have structured fields (difficulty, importance, type, topic_id) AND embeddings. A dedicated vector DB would require syncing data between two stores.

2. **Operational simplicity.** One database to back up, monitor, and manage. No cross-service consistency issues.

3. **JOIN capability.** We need queries like "find concepts similar to X where difficulty < 0.5 and topic_id = Y" — this requires joining vector search with structured filters. pgvector does this natively.

4. **Scale is modest.** Per-user scale is thousands of concepts, not millions. pgvector with IVFFlat indexes handles this comfortably.

5. **Migration path exists.** If we outgrow pgvector, we can add a dedicated vector DB for the search layer while keeping PostgreSQL as the source of truth. The abstraction boundary (RetrievalController) is already designed for this.

## Consequences

**Positive**:
- Single database, simpler infrastructure
- Native JOINs between structured and vector data
- No data sync issues
- Simpler local development (one Docker container)

**Negative**:
- pgvector is slower than dedicated vector DBs for large-scale ANN search
- Limited to IVFFlat or HNSW indexes (no hybrid keyword+vector search without additional setup)
- Embedding storage increases PostgreSQL backup size

**Acceptable because**: We won't hit pgvector's performance ceiling for a long time. A user with 10 documents averaging 100 concepts each = 1,000 vectors. pgvector handles millions.
