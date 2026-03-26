"""Exam API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.exam import (
    ExamDetailOut,
    ExamGenerateRequest,
    ExamOut,
    ExamQuestionOut,
    ExamResultOut,
    ExamSubmission,
    OptionOut,
    QuestionResultOut,
)
from app.services.exam_service import ExamService

router = APIRouter(prefix="/api/exams", tags=["exams"])


@router.post("/generate", response_model=ExamOut)
async def generate_exam(
    request: ExamGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a quiz for a document."""
    service = ExamService(db, settings)
    try:
        exam = await service.generate_exam(
            request.user_id, request.document_id, request.num_questions
        )
        await db.commit()
        return exam
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@router.get("/{exam_id}", response_model=ExamDetailOut)
async def get_exam(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get exam with questions (no answers revealed)."""
    service = ExamService(db, settings)
    exam = await service.get_exam(exam_id)
    if not exam:
        raise HTTPException(404, "Exam not found")

    # Strip correct answers from options
    questions = []
    for q in exam.questions:
        options = [
            OptionOut(label=opt["label"], text=opt["text"])
            for opt in (q.options or [])
        ]
        questions.append(
            ExamQuestionOut(
                id=q.id,
                question_index=q.question_index,
                question_text=q.question_text,
                question_type=q.question_type,
                options=options,
                bloom_level=q.bloom_level,
                difficulty=q.difficulty,
            )
        )

    return ExamDetailOut(
        id=exam.id,
        document_id=exam.document_id,
        status=exam.status,
        question_count=exam.question_count,
        score=exam.score,
        max_score=exam.max_score,
        created_at=exam.created_at,
        completed_at=exam.completed_at,
        questions=questions,
    )


@router.post("/{exam_id}/submit", response_model=ExamResultOut)
async def submit_exam(
    exam_id: uuid.UUID,
    submission: ExamSubmission,
    db: AsyncSession = Depends(get_db),
):
    """Submit exam answers and get graded results."""
    service = ExamService(db, settings)
    try:
        result = await service.submit_exam(
            exam_id, [a.model_dump() for a in submission.answers]
        )
        await db.commit()
        return ExamResultOut(
            id=result["id"],
            document_id=result["document_id"],
            status=result["status"],
            question_count=result["question_count"],
            score=result["score"],
            max_score=result["max_score"],
            created_at=result["created_at"],
            completed_at=result["completed_at"],
            questions=[QuestionResultOut(**q) for q in result["questions"]],
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{exam_id}/results", response_model=ExamResultOut)
async def get_exam_results(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get results for a graded exam."""
    service = ExamService(db, settings)
    result = await service.get_exam_results(exam_id)
    if not result:
        raise HTTPException(404, "Results not found (exam may not be graded yet)")

    return ExamResultOut(
        id=result["id"],
        document_id=result["document_id"],
        status=result["status"],
        question_count=result["question_count"],
        score=result["score"],
        max_score=result["max_score"],
        created_at=result["created_at"],
        completed_at=result["completed_at"],
        questions=[QuestionResultOut(**q) for q in result["questions"]],
    )
