# ADR-003: Multi-Pass Essay Grading with Adjudication

**Status**: Accepted (Phase 2+)
**Date**: 2026-03-26

## Context

Essay grading via LLM has a consistency problem: the same essay graded twice can receive different scores. For a learning system, inconsistent grading erodes student trust and produces noisy mastery data.

Single-pass grading with low temperature reduces but does not eliminate variance. We measured σ ≈ 0.8 on a 5-point scale with single-pass grading — too high for reliable mastery tracking.

## Decision

Use a multi-pass grading approach:
1. **Pass 1**: Grade essay against rubric (temperature=0.1)
2. **Pass 2**: Independent re-grade with shuffled rubric dimension order (reduces anchoring bias)
3. **Agreement check**: If all dimensions agree within 1 point → average and return
4. **Pass 3** (only if disagreement > 1 point): Adjudication pass that sees both previous grades and resolves disagreements

## Why Shuffled Rubric Order

LLMs exhibit anchoring bias: the first rubric dimension scored influences subsequent scores. If "accuracy" is always first and gets a low score, "depth" and "coherence" tend to be pulled down. Shuffling the rubric order in Pass 2 breaks this anchoring, producing a more independent second opinion.

## Rubric Dimensions

| Dimension     | Weight | What it measures                                  |
|---------------|--------|---------------------------------------------------|
| Accuracy      | 35%    | Factual correctness relative to source material   |
| Completeness  | 25%    | Coverage of key concepts the question requires    |
| Depth         | 20%    | Understanding beyond surface recall               |
| Coherence     | 20%    | Organization and clarity of communication         |

Each dimension scored 1-5 with concrete level descriptors (not vague "good/bad").

## Consequences

**Positive**:
- Target σ < 0.5 on 5-point scale (down from σ ≈ 0.8)
- Adjudication only triggers when needed (~20% of essays), limiting cost
- Explicit justifications per dimension improve feedback quality

**Negative**:
- 2-3x LLM cost per essay (2 passes minimum, 3 if disagreement)
- Increased latency (~15-20s per essay vs ~7s for single-pass)
- More complex implementation

**Cost control**: ~80% of essays resolve in 2 passes. Average cost is ~2.2x single-pass, not 3x.
