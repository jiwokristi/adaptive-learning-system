import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    status: str
    page_count: int | None = None
    created_at: datetime
    topic_count: int | None = None
    concept_count: int | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class DocumentChunkOut(BaseModel):
    id: uuid.UUID
    chunk_index: int
    text: str
    section_path: list[str] | None = None
    page_start: int | None = None
    page_end: int | None = None
    chunk_type: str

    model_config = {"from_attributes": True}
