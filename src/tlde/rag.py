"""RAG (Retrieval-Augmented Generation) module for TLDE.

Ingests PDFs and web pages, chunks the text, embeds with
sentence-transformers, and stores in ChromaDB for retrieval.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path

import chromadb
import httpx
import pymupdf4llm
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class KnowledgeBase:
    """Vector store backed by ChromaDB for spec document retrieval."""

    def __init__(self, persist_dir: str | None = None):
        embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL,
        )
        if persist_dir:
            self._client = chromadb.PersistentClient(path=persist_dir)
        else:
            self._client = chromadb.EphemeralClient()

        self._collection = self._client.get_or_create_collection(
            name="specs",
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    async def ingest_source(self, source: str) -> int:
        """Ingest a URL (web page or PDF) or local file path.

        Returns the number of chunks added.
        """
        if source.startswith(("http://", "https://")):
            return await self._ingest_url(source)
        else:
            path = Path(source).expanduser().resolve()
            if not path.exists():
                print(f"[RAG] WARNING: file not found: {path}")
                return 0
            if path.suffix.lower() == ".pdf":
                return self._ingest_pdf(path)
            else:
                return self._ingest_text_file(path)

    async def _ingest_url(self, url: str) -> int:
        """Fetch a URL. If it's a PDF, save to temp and ingest; otherwise treat as text."""
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")

        if "pdf" in content_type or url.lower().endswith(".pdf"):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(resp.content)
                tmp_path = Path(f.name)
            try:
                return self._ingest_pdf(tmp_path, source_label=url)
            finally:
                tmp_path.unlink(missing_ok=True)
        else:
            text = resp.text
            text = self._strip_html(text)
            return self._add_chunks(text, source=url)

    def _ingest_pdf(self, path: Path, source_label: str | None = None) -> int:
        """Extract markdown from a PDF and chunk it."""
        md_text = pymupdf4llm.to_markdown(str(path))
        label = source_label or str(path)
        return self._add_chunks(md_text, source=label)

    def _ingest_text_file(self, path: Path) -> int:
        """Read a plain text / markdown file and chunk it."""
        text = path.read_text(errors="replace")
        return self._add_chunks(text, source=str(path))

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def query(self, question: str, n_results: int = 10) -> list[dict]:
        """Retrieve the top-k most relevant chunks for a query.

        Returns a list of dicts with keys: text, source, distance.
        """
        results = self._collection.query(
            query_texts=[question],
            n_results=min(n_results, self._collection.count() or 1),
        )
        chunks = []
        for text, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "text": text,
                "source": meta.get("source", "unknown"),
                "distance": dist,
            })
        return chunks

    def format_context(self, question: str, n_results: int = 10) -> str:
        """Retrieve chunks and format them as a context block for a prompt."""
        if self._collection.count() == 0:
            return ""
        chunks = self.query(question, n_results=n_results)
        parts = ["# Reference Documentation\n"]
        for i, chunk in enumerate(chunks, 1):
            parts.append(
                f"## Chunk {i} (source: {chunk['source']})\n"
                f"{chunk['text']}\n"
            )
        return "\n".join(parts)

    @property
    def chunk_count(self) -> int:
        return self._collection.count()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_chunks(self, text: str, source: str) -> int:
        """Split text into overlapping chunks and add to the collection."""
        chunks = self._chunk_text(text)
        if not chunks:
            return 0

        ids = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = hashlib.sha256(
                f"{source}:{i}:{chunk[:100]}".encode()
            ).hexdigest()[:16]
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({"source": source, "chunk_index": i})

        # Upsert to handle re-ingestion gracefully
        self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(chunks)

    @staticmethod
    def _chunk_text(text: str) -> list[str]:
        """Split text into chunks, preferring section boundaries."""
        # Split on markdown headings or double newlines
        sections = re.split(r"\n(?=#{1,3} )", text)

        chunks = []
        for section in sections:
            if len(section) <= CHUNK_SIZE:
                if section.strip():
                    chunks.append(section.strip())
            else:
                # Sub-split long sections by paragraphs
                paragraphs = section.split("\n\n")
                current = ""
                for para in paragraphs:
                    if len(current) + len(para) + 2 > CHUNK_SIZE:
                        if current.strip():
                            chunks.append(current.strip())
                        # Overlap: keep the tail of the current chunk
                        if len(current) > CHUNK_OVERLAP:
                            current = current[-CHUNK_OVERLAP:] + "\n\n" + para
                        else:
                            current = para
                    else:
                        current = current + "\n\n" + para if current else para
                if current.strip():
                    chunks.append(current.strip())

        return chunks

    @staticmethod
    def _strip_html(html: str) -> str:
        """Rough HTML-to-text conversion for web pages."""
        # Remove script/style blocks
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.I)
        # Convert common block elements to newlines
        text = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*>", "\n", text, flags=re.I)
        # Strip remaining tags
        text = re.sub(r"<[^>]+>", "", text)
        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
