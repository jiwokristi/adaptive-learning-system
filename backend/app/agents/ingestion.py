"""Document Ingestion Agent — parses PDFs into structured text chunks."""

import logging
from dataclasses import dataclass, field

import pdfplumber
import tiktoken

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class ChunkResult:
    text: str
    section_path: list[str]
    page_start: int
    page_end: int
    chunk_type: str  # prose, table, list
    token_count: int


class IngestionAgent:
    """Parses uploaded documents into structured, overlapping text chunks."""

    def __init__(self, config: Settings):
        self.config = config
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def _detect_heading(self, line: str) -> bool:
        """Heuristic: short lines that look like section headings."""
        stripped = line.strip()
        if not stripped or len(stripped) > 120:
            return False
        # Numbered headings: "1.", "1.1", "Chapter 3", "Section 2.1"
        if any(
            stripped.lower().startswith(prefix)
            for prefix in ("chapter ", "section ", "part ")
        ):
            return True
        # Numbered patterns like "1.", "1.1.", "1.1.1"
        parts = stripped.split(".", 1)
        if parts[0].isdigit() and len(stripped) < 80:
            return True
        # ALL CAPS headings
        if stripped.isupper() and len(stripped) > 3 and len(stripped) < 80:
            return True
        return False

    def _chunk_paragraphs(
        self,
        paragraphs: list[dict],
    ) -> list[ChunkResult]:
        """Merge paragraphs into chunks respecting token limits with overlap."""
        chunks: list[ChunkResult] = []
        current_texts: list[str] = []
        current_tokens = 0
        current_section_path: list[str] = []
        current_page_start: int = 1
        current_page_end: int = 1

        for para in paragraphs:
            para_tokens = para["token_count"]

            # If a single paragraph exceeds chunk size, make it its own chunk
            if para_tokens > self.config.CHUNK_SIZE_TOKENS:
                # Flush current buffer first
                if current_texts:
                    chunks.append(
                        ChunkResult(
                            text="\n\n".join(current_texts),
                            section_path=list(current_section_path),
                            page_start=current_page_start,
                            page_end=current_page_end,
                            chunk_type="prose",
                            token_count=current_tokens,
                        )
                    )
                    current_texts = []
                    current_tokens = 0

                chunks.append(
                    ChunkResult(
                        text=para["text"],
                        section_path=list(para.get("section_path", [])),
                        page_start=para["page"],
                        page_end=para["page"],
                        chunk_type=para.get("chunk_type", "prose"),
                        token_count=para_tokens,
                    )
                )
                current_page_start = para["page"]
                continue

            # If adding this paragraph would exceed limit, flush
            if current_tokens + para_tokens > self.config.CHUNK_SIZE_TOKENS and current_texts:
                chunks.append(
                    ChunkResult(
                        text="\n\n".join(current_texts),
                        section_path=list(current_section_path),
                        page_start=current_page_start,
                        page_end=current_page_end,
                        chunk_type="prose",
                        token_count=current_tokens,
                    )
                )
                # Overlap: keep last paragraph(s) up to CHUNK_OVERLAP_TOKENS
                overlap_texts: list[str] = []
                overlap_tokens = 0
                for t in reversed(current_texts):
                    t_tokens = self._count_tokens(t)
                    if overlap_tokens + t_tokens > self.config.CHUNK_OVERLAP_TOKENS:
                        break
                    overlap_texts.insert(0, t)
                    overlap_tokens += t_tokens
                current_texts = overlap_texts
                current_tokens = overlap_tokens
                current_page_start = current_page_end

            if not current_texts:
                current_page_start = para["page"]
                current_section_path = para.get("section_path", [])

            current_texts.append(para["text"])
            current_tokens += para_tokens
            current_page_end = para["page"]
            if para.get("section_path"):
                current_section_path = para["section_path"]

        # Flush remaining
        if current_texts:
            chunks.append(
                ChunkResult(
                    text="\n\n".join(current_texts),
                    section_path=list(current_section_path),
                    page_start=current_page_start,
                    page_end=current_page_end,
                    chunk_type="prose",
                    token_count=current_tokens,
                )
            )

        return chunks

    async def ingest(self, file_path: str, file_type: str) -> list[ChunkResult]:
        """Parse a document into structured text chunks."""
        if file_type == "pdf":
            return await self._ingest_pdf(file_path)
        raise ValueError(f"Unsupported file type: {file_type}")

    async def _ingest_pdf(self, file_path: str) -> list[ChunkResult]:
        """Extract text from PDF, preserving structure."""
        paragraphs: list[dict] = []
        section_path: list[str] = []

        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            logger.info(f"Parsing PDF: {page_count} pages")

            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if not text.strip():
                    continue

                # Also extract tables
                tables = page.extract_tables() or []
                for table in tables:
                    table_text = self._format_table(table)
                    if table_text.strip():
                        paragraphs.append(
                            {
                                "text": table_text,
                                "page": page_num,
                                "section_path": list(section_path),
                                "chunk_type": "table",
                                "token_count": self._count_tokens(table_text),
                            }
                        )

                # Process text line by line
                lines = text.split("\n")
                current_paragraph: list[str] = []

                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        # Empty line = paragraph break
                        if current_paragraph:
                            para_text = " ".join(current_paragraph)
                            paragraphs.append(
                                {
                                    "text": para_text,
                                    "page": page_num,
                                    "section_path": list(section_path),
                                    "chunk_type": "prose",
                                    "token_count": self._count_tokens(para_text),
                                }
                            )
                            current_paragraph = []
                        continue

                    if self._detect_heading(stripped):
                        # Flush current paragraph
                        if current_paragraph:
                            para_text = " ".join(current_paragraph)
                            paragraphs.append(
                                {
                                    "text": para_text,
                                    "page": page_num,
                                    "section_path": list(section_path),
                                    "chunk_type": "prose",
                                    "token_count": self._count_tokens(para_text),
                                }
                            )
                            current_paragraph = []

                        # Update section path
                        depth = self._heading_depth(stripped)
                        section_path = section_path[:depth] + [stripped]
                        continue

                    current_paragraph.append(stripped)

                # Flush final paragraph on page
                if current_paragraph:
                    para_text = " ".join(current_paragraph)
                    paragraphs.append(
                        {
                            "text": para_text,
                            "page": page_num,
                            "section_path": list(section_path),
                            "chunk_type": "prose",
                            "token_count": self._count_tokens(para_text),
                        }
                    )

        chunks = self._chunk_paragraphs(paragraphs)
        logger.info(f"Ingestion complete: {len(paragraphs)} paragraphs → {len(chunks)} chunks")
        return chunks

    def _heading_depth(self, heading: str) -> int:
        """Estimate heading depth from numbering pattern."""
        parts = heading.split(".")
        if parts[0].isdigit():
            # Count numeric parts: "1" = depth 0, "1.1" = depth 1, "1.1.1" = depth 2
            depth = 0
            for part in parts:
                cleaned = part.strip()
                if cleaned.isdigit():
                    depth += 1
                else:
                    break
            return max(0, depth - 1)
        return 0

    @staticmethod
    def _format_table(table: list[list[str | None]]) -> str:
        """Format a pdfplumber table as readable text."""
        rows = []
        for row in table:
            cells = [str(cell).strip() if cell else "" for cell in row]
            rows.append(" | ".join(cells))
        return "\n".join(rows)
