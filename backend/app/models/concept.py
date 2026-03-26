import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True
    )
    depth: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    concept_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    concepts: Mapped[list["Concept"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    concept_type: Mapped[str] = mapped_column(String(50), nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, server_default=text("0.5"))
    importance: Mapped[float] = mapped_column(Float, server_default=text("0.5"))
    source_chunk_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    source_pages: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    supporting_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, server_default=text("'{}'"))
    embedding = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    topic: Mapped["Topic"] = relationship(back_populates="concepts")
