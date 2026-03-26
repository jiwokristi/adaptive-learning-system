"""Knowledge Distillation Agent — extracts structured concepts from document chunks."""

import json
import logging
from dataclasses import dataclass, field

import anthropic

from app.agents.ingestion import ChunkResult
from app.config import Settings

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are a knowledge extraction system. Extract every distinct concept from the text below.

For each concept, provide:
- name: a concise label (2-6 words)
- definition: 1-2 sentence definition using ONLY information in the text
- concept_type: one of [definition, theorem, process, fact, formula, example, principle]
- difficulty: 0.0 (trivial) to 1.0 (expert-level)
- importance: 0.0 (minor detail) to 1.0 (core concept critical for understanding)
- supporting_quote: an exact quote from the text that supports this concept

Rules:
- ONLY use information present in the provided text. Do NOT add external knowledge.
- Keep concepts atomic — one idea per concept.
- Do NOT merge distinct concepts.
- If the text contains no extractable concepts, return an empty list.

Respond with ONLY a JSON array:
[
  {
    "name": "...",
    "definition": "...",
    "concept_type": "...",
    "difficulty": 0.0,
    "importance": 0.0,
    "supporting_quote": "..."
  }
]

TEXT:
"""

CONSOLIDATION_PROMPT = """\
You are organizing extracted knowledge into a structured topic hierarchy.

Below is a list of raw concepts extracted from a document. Your tasks:
1. DEDUPLICATE: merge concepts that refer to the same idea (keep the best definition).
2. ORGANIZE: group concepts into topics. Create a topic hierarchy (max 2 levels deep).
3. REFINE: adjust difficulty and importance scores for consistency across all concepts.

Rules:
- Do NOT invent new concepts. Only reorganize what is provided.
- Every concept must belong to exactly one topic.
- Topic names should be descriptive and concise.

Respond with ONLY this JSON structure:
{
  "topics": [
    {
      "name": "Topic Name",
      "parent_topic": null,
      "concepts": [
        {
          "name": "...",
          "definition": "...",
          "concept_type": "...",
          "difficulty": 0.0,
          "importance": 0.0,
          "supporting_quote": "...",
          "source_chunk_indices": [0, 1]
        }
      ]
    }
  ]
}

RAW CONCEPTS (with source chunk index):
"""


@dataclass
class RawConcept:
    name: str
    definition: str
    concept_type: str
    difficulty: float
    importance: float
    supporting_quote: str
    chunk_index: int


@dataclass
class ConceptResult:
    name: str
    definition: str
    concept_type: str
    difficulty: float
    importance: float
    supporting_quote: str
    source_chunk_indices: list[int]
    topic_name: str


@dataclass
class TopicResult:
    name: str
    parent_topic_name: str | None
    concepts: list[ConceptResult]


@dataclass
class DistillationResult:
    topics: list[TopicResult]
    total_concepts: int


class DistillationAgent:
    """Extracts structured knowledge from document chunks using a two-pass approach."""

    def __init__(self, config: Settings):
        self.config = config
        self.client = anthropic.AsyncAnthropic()
        self.model = config.CLAUDE_DISTILL_MODEL

    async def distill(self, chunks: list[ChunkResult]) -> DistillationResult:
        """Two-pass distillation: extract per-chunk, then consolidate globally."""
        # Pass 1: Extract concepts from each chunk (or small batches)
        raw_concepts = await self._extract_pass(chunks)
        logger.info(f"Pass 1 complete: {len(raw_concepts)} raw concepts from {len(chunks)} chunks")

        if not raw_concepts:
            return DistillationResult(topics=[], total_concepts=0)

        # Pass 2: Consolidate, deduplicate, organize into topics
        result = await self._consolidation_pass(raw_concepts)
        logger.info(
            f"Pass 2 complete: {len(result.topics)} topics, {result.total_concepts} concepts"
        )
        return result

    async def _extract_pass(self, chunks: list[ChunkResult]) -> list[RawConcept]:
        """Extract concepts from each chunk independently."""
        all_concepts: list[RawConcept] = []

        # Process chunks in batches of 2-3 to reduce API calls
        batch_size = 2
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            batch_text = "\n\n---\n\n".join(
                f"[Chunk {i + j}]\n{chunk.text}" for j, chunk in enumerate(batch)
            )

            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    temperature=0.0,
                    messages=[{"role": "user", "content": EXTRACTION_PROMPT + batch_text}],
                )

                content = response.content[0].text
                concepts_data = self._parse_json(content)

                if isinstance(concepts_data, list):
                    for concept_dict in concepts_data:
                        try:
                            all_concepts.append(
                                RawConcept(
                                    name=concept_dict["name"],
                                    definition=concept_dict["definition"],
                                    concept_type=concept_dict.get("concept_type", "fact"),
                                    difficulty=float(concept_dict.get("difficulty", 0.5)),
                                    importance=float(concept_dict.get("importance", 0.5)),
                                    supporting_quote=concept_dict.get("supporting_quote", ""),
                                    chunk_index=i,
                                )
                            )
                        except (KeyError, ValueError) as e:
                            logger.warning(f"Skipping malformed concept: {e}")

            except anthropic.APIError as e:
                logger.error(f"API error extracting chunk batch {i}: {e}")
                continue

        return all_concepts

    async def _consolidation_pass(self, raw_concepts: list[RawConcept]) -> DistillationResult:
        """Consolidate raw concepts into organized topics."""
        # Format raw concepts for the consolidation prompt
        concepts_for_prompt = []
        for rc in raw_concepts:
            concepts_for_prompt.append(
                {
                    "name": rc.name,
                    "definition": rc.definition,
                    "concept_type": rc.concept_type,
                    "difficulty": rc.difficulty,
                    "importance": rc.importance,
                    "supporting_quote": rc.supporting_quote,
                    "source_chunk_index": rc.chunk_index,
                }
            )

        prompt = CONSOLIDATION_PROMPT + json.dumps(concepts_for_prompt, indent=2)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        data = self._parse_json(content)

        topics: list[TopicResult] = []
        total_concepts = 0

        for topic_data in data.get("topics", []):
            concepts: list[ConceptResult] = []
            for c in topic_data.get("concepts", []):
                concepts.append(
                    ConceptResult(
                        name=c["name"],
                        definition=c["definition"],
                        concept_type=c.get("concept_type", "fact"),
                        difficulty=float(c.get("difficulty", 0.5)),
                        importance=float(c.get("importance", 0.5)),
                        supporting_quote=c.get("supporting_quote", ""),
                        source_chunk_indices=c.get("source_chunk_indices", []),
                        topic_name=topic_data["name"],
                    )
                )
            topics.append(
                TopicResult(
                    name=topic_data["name"],
                    parent_topic_name=topic_data.get("parent_topic"),
                    concepts=concepts,
                )
            )
            total_concepts += len(concepts)

        return DistillationResult(topics=topics, total_concepts=total_concepts)

    @staticmethod
    def _parse_json(text: str) -> dict | list:
        """Extract JSON from LLM response, handling markdown code fences."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (``` markers)
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)
