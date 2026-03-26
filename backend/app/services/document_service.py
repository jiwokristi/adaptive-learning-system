"""Document Service — orchestrates upload, ingestion, and distillation."""

import logging
import os
import uuid
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.distillation import DistillationAgent
from app.agents.ingestion import IngestionAgent
from app.config import Settings
from app.models.concept import Concept, Topic
from app.models.document import Document, DocumentChunk

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(self, db: AsyncSession, config: Settings):
        self.db = db
        self.config = config
        self.ingestion_agent = IngestionAgent(config)
        self.distillation_agent = DistillationAgent(config)

    async def upload_document(
        self, user_id: uuid.UUID, filename: str, content: bytes
    ) -> Document:
        """Save uploaded file and create document record."""
        # Validate file type
        ext = Path(filename).suffix.lower()
        if ext not in (".pdf",):
            raise ValueError(f"Unsupported file type: {ext}. Only PDF is supported in MVP.")

        # Validate size
        size_mb = len(content) / (1024 * 1024)
        if size_mb > self.config.MAX_FILE_SIZE_MB:
            raise ValueError(
                f"File too large: {size_mb:.1f}MB (max {self.config.MAX_FILE_SIZE_MB}MB)"
            )

        # Save file
        doc_id = uuid.uuid4()
        doc_dir = Path(self.config.UPLOAD_DIR) / str(doc_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        file_path = doc_dir / filename
        file_path.write_bytes(content)

        # Create record
        document = Document(
            id=doc_id,
            user_id=user_id,
            filename=filename,
            file_type=ext.lstrip("."),
            storage_path=str(file_path),
            status="uploaded",
        )
        self.db.add(document)
        await self.db.flush()

        return document

    async def process_document(self, document_id: uuid.UUID) -> None:
        """Background task: ingest and distill a document."""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        if not document:
            logger.error(f"Document {document_id} not found")
            return

        try:
            # Phase 1: Ingestion
            document.status = "ingesting"
            await self.db.commit()

            chunks = await self.ingestion_agent.ingest(
                document.storage_path, document.file_type
            )

            # Save chunks
            for i, chunk in enumerate(chunks):
                db_chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=i,
                    text=chunk.text,
                    section_path=chunk.section_path,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    chunk_type=chunk.chunk_type,
                    token_count=chunk.token_count,
                )
                self.db.add(db_chunk)

            document.page_count = chunks[-1].page_end if chunks else 0
            await self.db.commit()

            # Phase 2: Distillation
            document.status = "distilling"
            await self.db.commit()

            distillation = await self.distillation_agent.distill(chunks)

            # Save topics and concepts
            for sort_order, topic_result in enumerate(distillation.topics):
                topic = Topic(
                    document_id=document.id,
                    name=topic_result.name,
                    depth=0,
                    sort_order=sort_order,
                    concept_count=len(topic_result.concepts),
                )
                self.db.add(topic)
                await self.db.flush()  # get topic.id

                # Get chunk IDs for source mapping
                chunk_result = await self.db.execute(
                    select(DocumentChunk.id, DocumentChunk.chunk_index).where(
                        DocumentChunk.document_id == document.id
                    )
                )
                chunk_id_map = {row.chunk_index: row.id for row in chunk_result.all()}

                for concept_result in topic_result.concepts:
                    source_chunk_ids = [
                        chunk_id_map[idx]
                        for idx in concept_result.source_chunk_indices
                        if idx in chunk_id_map
                    ]
                    # Extract source pages from chunks
                    source_pages = []
                    for idx in concept_result.source_chunk_indices:
                        if idx < len(chunks):
                            for p in range(chunks[idx].page_start, chunks[idx].page_end + 1):
                                if p not in source_pages:
                                    source_pages.append(p)

                    concept = Concept(
                        topic_id=topic.id,
                        name=concept_result.name,
                        definition=concept_result.definition,
                        concept_type=concept_result.concept_type,
                        difficulty=concept_result.difficulty,
                        importance=concept_result.importance,
                        supporting_quote=concept_result.supporting_quote,
                        source_chunk_ids=source_chunk_ids or None,
                        source_pages=sorted(source_pages) or None,
                    )
                    self.db.add(concept)

            document.status = "ready"
            await self.db.commit()
            logger.info(
                f"Document {document_id} processed: "
                f"{len(distillation.topics)} topics, {distillation.total_concepts} concepts"
            )

        except Exception as e:
            logger.exception(f"Error processing document {document_id}")
            document.status = "error"
            document.error_message = str(e)[:500]
            await self.db.commit()

    async def get_document(self, document_id: uuid.UUID) -> Document | None:
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def list_documents(self, user_id: uuid.UUID) -> list[dict]:
        """List documents with topic/concept counts."""
        result = await self.db.execute(
            select(Document).where(Document.user_id == user_id).order_by(Document.created_at.desc())
        )
        documents = result.scalars().all()

        docs_out = []
        for doc in documents:
            # Get counts
            topic_count_result = await self.db.execute(
                select(func.count(Topic.id)).where(Topic.document_id == doc.id)
            )
            topic_count = topic_count_result.scalar() or 0

            concept_count_result = await self.db.execute(
                select(func.count(Concept.id))
                .join(Topic, Concept.topic_id == Topic.id)
                .where(Topic.document_id == doc.id)
            )
            concept_count = concept_count_result.scalar() or 0

            docs_out.append(
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "status": doc.status,
                    "page_count": doc.page_count,
                    "created_at": doc.created_at,
                    "topic_count": topic_count,
                    "concept_count": concept_count,
                    "error_message": doc.error_message,
                }
            )

        return docs_out

    async def get_topics_with_concepts(self, document_id: uuid.UUID) -> list[dict]:
        """Get all topics with their concepts for a document."""
        result = await self.db.execute(
            select(Topic)
            .where(Topic.document_id == document_id)
            .order_by(Topic.sort_order)
        )
        topics = result.scalars().all()

        output = []
        for topic in topics:
            concepts_result = await self.db.execute(
                select(Concept).where(Concept.topic_id == topic.id)
            )
            concepts = concepts_result.scalars().all()

            output.append(
                {
                    "id": topic.id,
                    "name": topic.name,
                    "parent_topic_id": topic.parent_topic_id,
                    "depth": topic.depth,
                    "concept_count": len(concepts),
                    "concepts": [
                        {
                            "id": c.id,
                            "name": c.name,
                            "definition": c.definition,
                            "concept_type": c.concept_type,
                            "difficulty": c.difficulty,
                            "importance": c.importance,
                            "source_pages": c.source_pages,
                            "supporting_quote": c.supporting_quote,
                            "topic_name": topic.name,
                        }
                        for c in concepts
                    ],
                }
            )

        return output
