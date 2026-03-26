"""Document API routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.concept import TopicWithConceptsOut
from app.schemas.document import DocumentOut
from app.schemas.exam import MasteryOut
from app.services.document_service import DocumentService
from app.services.mastery_service import MasteryService

router = APIRouter(prefix="/api/documents", tags=["documents"])

DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/", response_model=DocumentOut)
async def upload_document(
    file: UploadFile,
    user_id: uuid.UUID = Query(..., description="User ID (no auth in MVP)"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF and start processing."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    service = DocumentService(db, settings)
    content = await file.read()

    try:
        document = await service.upload_document(user_id, file.filename, content)
    except ValueError as e:
        raise HTTPException(400, str(e))

    await db.commit()

    # Process in background (new session needed for background task)
    async def process_in_background(doc_id: uuid.UUID):
        from app.database import async_session

        async with async_session() as bg_db:
            bg_service = DocumentService(bg_db, settings)
            await bg_service.process_document(doc_id)
            await bg_db.commit()

    background_tasks.add_task(process_in_background, document.id)

    return DocumentOut(
        id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        status=document.status,
        page_count=document.page_count,
        created_at=document.created_at,
    )


@router.get("/", response_model=list[DocumentOut])
async def list_documents(
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """List all documents for a user."""
    service = DocumentService(db, settings)
    docs = await service.list_documents(user_id)
    return [DocumentOut(**doc) for doc in docs]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get document details."""
    service = DocumentService(db, settings)
    doc = await service.get_document(document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/{document_id}/topics", response_model=list[TopicWithConceptsOut])
async def get_topics(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get topics with concepts for a document."""
    service = DocumentService(db, settings)
    return await service.get_topics_with_concepts(document_id)


@router.get("/{document_id}/mastery", response_model=list[MasteryOut])
async def get_mastery(
    document_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get mastery breakdown by topic."""
    service = MasteryService(db)
    return await service.get_document_mastery(user_id, document_id)
