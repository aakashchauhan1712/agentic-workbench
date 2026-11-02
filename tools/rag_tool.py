"""
RAG tool – FAISS-backed PDF retrieval registered as a Copilot SDK tool.

Pipeline
--------
1. PDF upload  →  text extraction  (pypdf)
2. Text        →  chunks           (fixed-size with overlap)
3. Chunks      →  embeddings       (sentence-transformers locally)
4. Embeddings  →  FAISS index      (saved to disk per document)
5. At query time: embed query → search FAISS → return top-k chunks
6. Result injected back into the Copilot session as tool output.
"""
import json
import os
import pickle
import sys
from pathlib import Path
from typing import Optional

import numpy as np

sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")

from pydantic import BaseModel, Field

from copilot import Tool, ToolInvocation, define_tool

# Lazy imports for heavy libraries
_faiss = None
_embedder = None
_embedder_name: Optional[str] = None


def _get_faiss():
    global _faiss
    if _faiss is None:
        import faiss
        _faiss = faiss
    return _faiss


def _get_embedder(model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    global _embedder, _embedder_name
    if _embedder is None or _embedder_name != model_name:
        from sentence_transformers import SentenceTransformer
        try:
            # Prefer local cached files to avoid online latency / timeouts
            _embedder = SentenceTransformer(model_name, local_files_only=True)
        except Exception:
            _embedder = SentenceTransformer(model_name)
        _embedder_name = model_name
    return _embedder


# -----------------------------------------------------------------------
# Text chunking
# -----------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """Split text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]


# -----------------------------------------------------------------------
# Index management
# -----------------------------------------------------------------------

def build_index(
    doc_id: str,
    text: str,
    store_dir: Path,
    model_name: str,
) -> dict:
    """
    Embed and index all chunks of *text*.
    Returns a metadata dict with stats.
    """
    faiss = _get_faiss()
    embedder = _get_embedder(model_name)

    chunks = chunk_text(text)
    if not chunks:
        return {"doc_id": doc_id, "chunks": 0}

    embeddings = embedder.encode(chunks, show_progress_bar=False)
    embeddings = np.array(embeddings, dtype="float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    # Persist
    store_dir.mkdir(parents=True, exist_ok=True)
    idx_path = store_dir / f"{doc_id}.index"
    meta_path = store_dir / f"{doc_id}.meta"

    faiss.write_index(index, str(idx_path))
    with open(meta_path, "wb") as f:
        pickle.dump({"chunks": chunks, "doc_id": doc_id}, f)

    return {"doc_id": doc_id, "chunks": len(chunks)}


def load_index(doc_id: str, store_dir: Path):
    """Return (faiss_index, chunks) or (None, []) if not found."""
    faiss = _get_faiss()
    idx_path = store_dir / f"{doc_id}.index"
    meta_path = store_dir / f"{doc_id}.meta"
    if not idx_path.exists() or not meta_path.exists():
        return None, []
    index = faiss.read_index(str(idx_path))
    with open(meta_path, "rb") as f:
        meta = pickle.load(f)
    return index, meta["chunks"]


def query_index(
    doc_ids: list[str],
    query: str,
    store_dir: Path,
    model_name: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Search across one or more FAISS indexes.
    Returns list of {doc_id, chunk, score} dicts sorted by relevance.
    """
    embedder = _get_embedder(model_name)
    q_vec = embedder.encode([query], show_progress_bar=False)
    q_vec = np.array(q_vec, dtype="float32")

    results = []
    for doc_id in doc_ids:
        index, chunks = load_index(doc_id, store_dir)
        if index is None:
            continue
        k = min(top_k, index.ntotal)
        distances, indices = index.search(q_vec, k)
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            results.append(
                {"doc_id": doc_id, "chunk": chunks[idx], "score": float(dist)}
            )

    results.sort(key=lambda x: x["score"])
    return results[:top_k]


# -----------------------------------------------------------------------
# Copilot SDK tool factory
# -----------------------------------------------------------------------

class RAGQueryParams(BaseModel):
    question: str = Field(description="The user's question about the uploaded PDF documents")
    doc_ids: list[str] = Field(
        default_factory=list,
        description="List of document IDs to search (empty = search all indexed docs)",
    )


def build_rag_tool(
    store_dir: Path,
    model_name: str,
    active_doc_ids_fn,  # callable() -> list[str]
) -> Tool:
    """
    Build and return a Copilot SDK Tool that performs RAG retrieval.
    `active_doc_ids_fn` is called at query-time so it reflects the current
    set of uploaded documents.
    """

    @define_tool(
        name="retrieve_from_documents",
        description=(
            "Search the uploaded PDF documents and retrieve relevant text passages "
            "to answer the user's question. Always use this tool when the user asks "
            "about the content of any uploaded PDF."
        ),
        skip_permission=True,
    )
    async def retrieve_from_documents(
        params: RAGQueryParams, invocation: ToolInvocation
    ) -> str:
        doc_ids = params.doc_ids or active_doc_ids_fn()
        if not doc_ids:
            return json.dumps({"error": "No documents are indexed yet. Please upload a PDF first."})

        results = query_index(
            doc_ids=doc_ids,
            query=params.question,
            store_dir=store_dir,
            model_name=model_name,
            top_k=5,
        )
        if not results:
            return json.dumps({"error": "No relevant content found in documents."})

        formatted = []
        for r in results:
            formatted.append(
                f"[Source: {r['doc_id']} | Relevance: {r['score']:.2f}]\n{r['chunk']}"
            )
        return json.dumps({"passages": formatted}, ensure_ascii=False)

    return retrieve_from_documents

