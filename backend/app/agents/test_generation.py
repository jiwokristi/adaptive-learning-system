"""Test Generation Agent — creates MCQ questions grounded in source material."""

import json
import logging
import uuid
from dataclasses import dataclass

import anthropic

from app.config import Settings

logger = logging.getLogger(__name__)

QUESTION_GEN_PROMPT = """\
You are generating multiple-choice exam questions to test a student's understanding.

For each concept below, generate ONE multiple-choice question with 4 options (A, B, C, D).

Requirements:
- Questions must be answerable using ONLY the provided concept definitions and quotes.
- The correct answer must be clearly supported by the source material.
- Distractors (wrong answers) must be plausible but definitively incorrect.
- Do NOT use "All of the above" or "None of the above" as options.
- Vary question styles: direct recall, application, comparison, cause-effect.
- Assign a Bloom's taxonomy level: remember, understand, apply, or analyze.

Respond with ONLY a JSON array:
[
  {
    "concept_name": "...",
    "question_text": "...",
    "options": [
      {"label": "A", "text": "...", "is_correct": false},
      {"label": "B", "text": "...", "is_correct": true},
      {"label": "C", "text": "...", "is_correct": false},
      {"label": "D", "text": "...", "is_correct": false}
    ],
    "explanation": "The correct answer is B because...",
    "bloom_level": "understand",
    "difficulty": 0.5
  }
]

CONCEPTS TO TEST:
"""


@dataclass
class ConceptForQuiz:
    concept_id: uuid.UUID
    name: str
    definition: str
    concept_type: str
    difficulty: float
    importance: float
    supporting_quote: str | None
    topic_name: str


@dataclass
class GeneratedQuestion:
    concept_id: uuid.UUID
    question_text: str
    options: list[dict]  # [{label, text, is_correct}]
    correct_answer: str  # the label (e.g., "B")
    explanation: str
    bloom_level: str
    difficulty: float


class TestGenerationAgent:
    """Generates MCQ questions from structured concepts."""

    def __init__(self, config: Settings):
        self.config = config
        self.client = anthropic.AsyncAnthropic()
        self.model = config.CLAUDE_MODEL

    async def generate_questions(
        self, concepts: list[ConceptForQuiz], num_questions: int = 10
    ) -> list[GeneratedQuestion]:
        """Generate MCQ questions for the given concepts."""
        # Limit to requested count
        concepts = concepts[:num_questions]

        # Batch into groups of 5 for efficiency
        all_questions: list[GeneratedQuestion] = []
        batch_size = 5

        for i in range(0, len(concepts), batch_size):
            batch = concepts[i : i + batch_size]
            questions = await self._generate_batch(batch)
            all_questions.extend(questions)

        return all_questions[:num_questions]

    async def _generate_batch(
        self, concepts: list[ConceptForQuiz]
    ) -> list[GeneratedQuestion]:
        """Generate questions for a batch of concepts in a single API call."""
        # Build concept descriptions for the prompt
        concept_descriptions = []
        concept_map = {}
        for c in concepts:
            concept_map[c.name] = c
            desc = {
                "name": c.name,
                "definition": c.definition,
                "type": c.concept_type,
                "topic": c.topic_name,
                "difficulty_target": c.difficulty,
            }
            if c.supporting_quote:
                desc["source_quote"] = c.supporting_quote
            concept_descriptions.append(desc)

        prompt = QUESTION_GEN_PROMPT + json.dumps(concept_descriptions, indent=2)

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.7,  # some creativity for diverse questions
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text
            questions_data = self._parse_json(content)

            results: list[GeneratedQuestion] = []
            for q in questions_data:
                concept_name = q.get("concept_name", "")
                concept = concept_map.get(concept_name)
                if not concept:
                    # Try fuzzy match
                    for name, c in concept_map.items():
                        if name.lower() in concept_name.lower() or concept_name.lower() in name.lower():
                            concept = c
                            break
                if not concept:
                    logger.warning(f"Could not match question to concept: {concept_name}")
                    continue

                # Find correct answer label
                correct_label = "A"
                for opt in q.get("options", []):
                    if opt.get("is_correct"):
                        correct_label = opt["label"]
                        break

                results.append(
                    GeneratedQuestion(
                        concept_id=concept.concept_id,
                        question_text=q["question_text"],
                        options=q["options"],
                        correct_answer=correct_label,
                        explanation=q.get("explanation", ""),
                        bloom_level=q.get("bloom_level", "remember"),
                        difficulty=float(q.get("difficulty", concept.difficulty)),
                    )
                )

            return results

        except anthropic.APIError as e:
            logger.error(f"API error generating questions: {e}")
            return []

    @staticmethod
    def _parse_json(text: str) -> list:
        """Extract JSON array from LLM response."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)
