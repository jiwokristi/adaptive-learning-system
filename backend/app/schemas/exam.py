import uuid
from datetime import datetime

from pydantic import BaseModel


class ExamOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: str
    question_count: int
    score: float | None = None
    max_score: float | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class OptionOut(BaseModel):
    label: str
    text: str


class ExamQuestionOut(BaseModel):
    id: uuid.UUID
    question_index: int
    question_text: str
    question_type: str
    options: list[OptionOut]
    bloom_level: str | None = None
    difficulty: float

    model_config = {"from_attributes": True}


class ExamDetailOut(ExamOut):
    questions: list[ExamQuestionOut] = []


class AnswerItem(BaseModel):
    question_id: uuid.UUID
    answer: str


class ExamSubmission(BaseModel):
    answers: list[AnswerItem]


class QuestionResultOut(BaseModel):
    question_id: uuid.UUID
    question_text: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str


class ExamResultOut(ExamOut):
    questions: list[QuestionResultOut] = []


class ConceptMasteryItem(BaseModel):
    concept_id: uuid.UUID
    concept_name: str
    mastery_score: float
    attempts: int
    correct: int


class MasteryOut(BaseModel):
    topic_id: uuid.UUID
    topic_name: str
    mastery_score: float
    attempts: int
    correct: int
    concepts: list[ConceptMasteryItem] = []


class ExamGenerateRequest(BaseModel):
    user_id: uuid.UUID
    document_id: uuid.UUID
    num_questions: int = 10
