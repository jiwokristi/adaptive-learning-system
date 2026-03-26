import uuid

from pydantic import BaseModel


class TopicOut(BaseModel):
    id: uuid.UUID
    name: str
    parent_topic_id: uuid.UUID | None = None
    depth: int
    concept_count: int

    model_config = {"from_attributes": True}


class ConceptOut(BaseModel):
    id: uuid.UUID
    name: str
    definition: str
    concept_type: str
    difficulty: float
    importance: float
    source_pages: list[int] | None = None
    supporting_quote: str | None = None
    topic_name: str | None = None

    model_config = {"from_attributes": True}


class TopicWithConceptsOut(TopicOut):
    concepts: list[ConceptOut] = []
