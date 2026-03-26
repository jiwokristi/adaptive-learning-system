"""Mastery Service — tracks user performance per concept and topic."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.concept import Concept, Topic
from app.models.exam import UserConceptMastery

logger = logging.getLogger(__name__)


class MasteryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_mastery(
        self, user_id: uuid.UUID, concept_id: uuid.UUID, is_correct: bool
    ) -> None:
        """Update mastery score after a question attempt. MVP: simple % correct."""
        result = await self.db.execute(
            select(UserConceptMastery).where(
                UserConceptMastery.user_id == user_id,
                UserConceptMastery.concept_id == concept_id,
            )
        )
        mastery = result.scalar_one_or_none()

        if mastery is None:
            mastery = UserConceptMastery(
                user_id=user_id,
                concept_id=concept_id,
                attempts=0,
                correct=0,
                mastery_score=0.0,
            )
            self.db.add(mastery)

        mastery.attempts += 1
        if is_correct:
            mastery.correct += 1
        mastery.mastery_score = mastery.correct / mastery.attempts
        mastery.last_tested_at = datetime.now(timezone.utc)

    async def get_document_mastery(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[dict]:
        """Get mastery breakdown by topic for a document."""
        # Get all topics for the document
        topics_result = await self.db.execute(
            select(Topic).where(Topic.document_id == document_id).order_by(Topic.sort_order)
        )
        topics = topics_result.scalars().all()

        output = []
        for topic in topics:
            # Aggregate mastery for concepts in this topic
            result = await self.db.execute(
                select(
                    func.sum(UserConceptMastery.attempts).label("total_attempts"),
                    func.sum(UserConceptMastery.correct).label("total_correct"),
                )
                .join(Concept, UserConceptMastery.concept_id == Concept.id)
                .where(
                    UserConceptMastery.user_id == user_id,
                    Concept.topic_id == topic.id,
                )
            )
            row = result.one()
            total_attempts = row.total_attempts or 0
            total_correct = row.total_correct or 0

            if total_attempts == 0:
                continue

            # Get per-concept mastery
            concepts_result = await self.db.execute(
                select(UserConceptMastery, Concept.name)
                .join(Concept, UserConceptMastery.concept_id == Concept.id)
                .where(
                    UserConceptMastery.user_id == user_id,
                    Concept.topic_id == topic.id,
                )
            )

            concepts = []
            for mastery, concept_name in concepts_result.all():
                concepts.append(
                    {
                        "concept_id": mastery.concept_id,
                        "concept_name": concept_name,
                        "mastery_score": mastery.mastery_score,
                        "attempts": mastery.attempts,
                        "correct": mastery.correct,
                    }
                )

            output.append(
                {
                    "topic_id": topic.id,
                    "topic_name": topic.name,
                    "mastery_score": total_correct / total_attempts if total_attempts > 0 else 0.0,
                    "attempts": total_attempts,
                    "correct": total_correct,
                    "concepts": concepts,
                }
            )

        return output

    async def get_weak_concepts(
        self, user_id: uuid.UUID, document_id: uuid.UUID, threshold: float = 0.5
    ) -> list[dict]:
        """Get concepts below mastery threshold, ordered by importance."""
        result = await self.db.execute(
            select(UserConceptMastery, Concept)
            .join(Concept, UserConceptMastery.concept_id == Concept.id)
            .join(Topic, Concept.topic_id == Topic.id)
            .where(
                UserConceptMastery.user_id == user_id,
                Topic.document_id == document_id,
                UserConceptMastery.mastery_score < threshold,
            )
            .order_by(Concept.importance.desc())
        )

        return [
            {
                "concept_id": mastery.concept_id,
                "concept_name": concept.name,
                "mastery_score": mastery.mastery_score,
                "importance": concept.importance,
                "topic_id": concept.topic_id,
            }
            for mastery, concept in result.all()
        ]
