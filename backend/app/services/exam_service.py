"""Exam Service — orchestrates quiz generation, submission, and grading."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.test_generation import ConceptForQuiz, TestGenerationAgent
from app.config import Settings
from app.models.concept import Concept, Topic
from app.models.exam import Exam, ExamQuestion, ExamResponse, UserConceptMastery
from app.services.mastery_service import MasteryService

logger = logging.getLogger(__name__)


class ExamService:
    def __init__(self, db: AsyncSession, config: Settings):
        self.db = db
        self.config = config
        self.test_gen_agent = TestGenerationAgent(config)
        self.mastery_service = MasteryService(db)

    async def generate_exam(
        self, user_id: uuid.UUID, document_id: uuid.UUID, num_questions: int = 10
    ) -> Exam:
        """Generate a quiz by selecting concepts and creating questions."""
        # Get all concepts for the document
        result = await self.db.execute(
            select(Concept, Topic.name.label("topic_name"))
            .join(Topic, Concept.topic_id == Topic.id)
            .where(Topic.document_id == document_id)
        )
        rows = result.all()

        if not rows:
            raise ValueError("No concepts found for this document. Is it processed?")

        # Get mastery data
        concept_ids = [row.Concept.id for row in rows]
        mastery_result = await self.db.execute(
            select(UserConceptMastery).where(
                UserConceptMastery.user_id == user_id,
                UserConceptMastery.concept_id.in_(concept_ids),
            )
        )
        mastery_map = {m.concept_id: m for m in mastery_result.scalars().all()}

        # Select concepts: prioritize low mastery + high importance
        scored_concepts = []
        for row in rows:
            concept = row.Concept
            topic_name = row.topic_name
            mastery = mastery_map.get(concept.id)
            mastery_score = mastery.mastery_score if mastery else 0.0

            priority = (1.0 - mastery_score) * 0.6 + concept.importance * 0.4
            scored_concepts.append((priority, concept, topic_name))

        scored_concepts.sort(key=lambda x: x[0], reverse=True)

        # Build quiz concepts
        quiz_concepts = [
            ConceptForQuiz(
                concept_id=concept.id,
                name=concept.name,
                definition=concept.definition,
                concept_type=concept.concept_type,
                difficulty=concept.difficulty,
                importance=concept.importance,
                supporting_quote=concept.supporting_quote,
                topic_name=topic_name,
            )
            for _, concept, topic_name in scored_concepts[:num_questions]
        ]

        # Generate questions
        generated = await self.test_gen_agent.generate_questions(quiz_concepts, num_questions)

        if not generated:
            raise RuntimeError("Failed to generate questions. Please try again.")

        # Create exam record
        exam = Exam(
            user_id=user_id,
            document_id=document_id,
            status="generated",
            question_count=len(generated),
        )
        self.db.add(exam)
        await self.db.flush()

        # Create question records
        for i, q in enumerate(generated):
            question = ExamQuestion(
                exam_id=exam.id,
                concept_id=q.concept_id,
                question_index=i,
                question_text=q.question_text,
                question_type="mcq",
                options=q.options,
                correct_answer=q.correct_answer,
                explanation=q.explanation,
                bloom_level=q.bloom_level,
                difficulty=q.difficulty,
            )
            self.db.add(question)

        await self.db.flush()
        return exam

    async def get_exam(self, exam_id: uuid.UUID) -> Exam | None:
        result = await self.db.execute(
            select(Exam)
            .options(selectinload(Exam.questions))
            .where(Exam.id == exam_id)
        )
        return result.scalar_one_or_none()

    async def submit_exam(
        self, exam_id: uuid.UUID, answers: list[dict]
    ) -> dict:
        """Grade submitted answers and update mastery."""
        result = await self.db.execute(
            select(Exam)
            .options(selectinload(Exam.questions))
            .where(Exam.id == exam_id)
        )
        exam = result.scalar_one_or_none()
        if not exam:
            raise ValueError("Exam not found")
        if exam.status == "graded":
            raise ValueError("Exam already graded")

        # Build answer lookup
        answer_map = {str(a["question_id"]): a["answer"] for a in answers}

        # Grade each question
        correct_count = 0
        question_results = []

        for question in exam.questions:
            user_answer = answer_map.get(str(question.id), "")
            is_correct = user_answer.strip().upper() == question.correct_answer.strip().upper()

            if is_correct:
                correct_count += 1

            # Save response
            response = ExamResponse(
                exam_question_id=question.id,
                user_answer=user_answer,
                is_correct=is_correct,
            )
            self.db.add(response)

            # Update mastery for this concept
            await self.mastery_service.update_mastery(
                exam.user_id, question.concept_id, is_correct
            )

            question_results.append(
                {
                    "question_id": question.id,
                    "question_text": question.question_text,
                    "user_answer": user_answer,
                    "correct_answer": question.correct_answer,
                    "is_correct": is_correct,
                    "explanation": question.explanation,
                }
            )

        # Update exam
        exam.score = correct_count
        exam.max_score = len(exam.questions)
        exam.status = "graded"
        exam.completed_at = datetime.now(timezone.utc)

        await self.db.flush()

        return {
            "id": exam.id,
            "document_id": exam.document_id,
            "status": exam.status,
            "question_count": exam.question_count,
            "score": exam.score,
            "max_score": exam.max_score,
            "created_at": exam.created_at,
            "completed_at": exam.completed_at,
            "questions": question_results,
        }

    async def get_exam_results(self, exam_id: uuid.UUID) -> dict | None:
        """Retrieve graded exam results."""
        result = await self.db.execute(
            select(Exam)
            .options(selectinload(Exam.questions).selectinload(ExamQuestion.responses))
            .where(Exam.id == exam_id)
        )
        exam = result.scalar_one_or_none()
        if not exam or exam.status != "graded":
            return None

        question_results = []
        for q in exam.questions:
            response = q.responses[0] if q.responses else None
            question_results.append(
                {
                    "question_id": q.id,
                    "question_text": q.question_text,
                    "user_answer": response.user_answer if response else "",
                    "correct_answer": q.correct_answer,
                    "is_correct": response.is_correct if response else False,
                    "explanation": q.explanation,
                }
            )

        return {
            "id": exam.id,
            "document_id": exam.document_id,
            "status": exam.status,
            "question_count": exam.question_count,
            "score": exam.score,
            "max_score": exam.max_score,
            "created_at": exam.created_at,
            "completed_at": exam.completed_at,
            "questions": question_results,
        }
