# ADR-001: Use Bayesian Knowledge Tracing over Item Response Theory

**Status**: Accepted (planned for Phase 2; MVP uses simple % correct)
**Date**: 2026-03-26

## Context

We need a mastery model to drive adaptive question selection. Two established approaches:

- **Item Response Theory (IRT)** — Models student ability as a single latent trait (theta) and question difficulty/discrimination. Standard in psychometrics and standardized testing.
- **Bayesian Knowledge Tracing (BKT)** — Models per-concept mastery as a hidden state with transition probabilities (learning, slipping, guessing). Common in intelligent tutoring systems.

## Decision

Use BKT for mastery tracking. MVP starts with simple % correct, then upgrades to BKT in Phase 2.

## Rationale

| Factor | IRT | BKT |
|--------|-----|-----|
| Models learning over time | No — assumes fixed ability | Yes — explicit learning transition |
| Data requirements | Hundreds of responses per item | Works with 5-8 responses per concept |
| Granularity | Single ability score | Per-concept mastery |
| Difficulty calibration | Excellent | Weak (difficulty is input, not learned) |
| Prerequisite support | Not native | Natural (per-concept tracking) |
| Implementation complexity | Requires EM algorithm or MCMC | Simple Bayesian update |

**Key insight**: IRT answers "how good is this student?" while BKT answers "has this student learned this concept?" The second question is what we need for adaptive learning.

## BKT Parameters

For each (user, concept) pair:
- `p_know` — probability the student knows the concept (the mastery score)
- `p_learn` — probability of learning after one attempt
- `p_slip` — probability of wrong answer despite knowing
- `p_guess` — probability of right answer despite not knowing

Update rule:
```
If correct:
  P(knew | correct) = P(correct|knew) * P(knew) / P(correct)
  P(know_new) = P(knew|correct) + (1 - P(knew|correct)) * p_learn
If incorrect:
  P(knew | incorrect) = P(incorrect|knew) * P(knew) / P(incorrect)
  P(know_new) = P(knew|incorrect) + (1 - P(knew|incorrect)) * p_learn
```

## Consequences

**Positive**:
- Simpler implementation, works with small per-student datasets
- Natural fit for per-concept mastery tracking
- Supports prerequisite chains (only test concept if prereqs mastered)
- Converges quickly (5-8 questions per concept)

**Negative**:
- Less sophisticated difficulty calibration than IRT
- Default parameters need manual tuning per concept type
- Doesn't account for inter-concept correlations

**Mitigation**: Can layer IRT on top later specifically for question difficulty calibration from aggregate response data, while keeping BKT for individual mastery.
