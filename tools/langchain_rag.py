"""
LangChain-powered RAG pipeline with Google Gemini 2.5 and FAISS vector database.

Pipeline
--------
1. PDF Loading: Extracts page-by-page text with page number metadata.
2. Semantic Chunking: RecursiveCharacterTextSplitter for optimal context preservation.
3. Embedding: Google Generative AI Embeddings (gemini-embedding-001) or local MiniLM fallback.
4. Vector Store: LangChain FAISS index saved and loaded per document.
5. Grounded Answering: Powered by ChatGoogleGenerativeAI (gemini-2.5-flash) with explicit citations.
6. Copilot Tool: Also exposed as a @define_tool for Copilot SDK integration.
"""
import asyncio
import io
import json
import os
import sys
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")

from pypdf import PdfReader
from pydantic import BaseModel, Field

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores.faiss import FAISS

# Copilot SDK tool imports
from copilot import Tool, ToolInvocation, define_tool


def _ensure_event_loop() -> asyncio.AbstractEventLoop:
    """Ensure that the calling thread (e.g. Streamlit worker) has an active asyncio event loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


# ---------------------------------------------------------------------------
# Embedding selector
# ---------------------------------------------------------------------------

def get_langchain_embeddings(google_api_key: Optional[str] = None):
    """
    Return GoogleGenerativeAIEmbeddings if an API key is provided,
    otherwise fallback to local sentence-transformers.
    """
    _ensure_event_loop()
    key = (google_api_key or "").strip()
    if key:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        # Try gemini-embedding-001 (supported by current Gemini API)
        for model_name in [
            "models/gemini-embedding-001",
            "models/gemini-embedding-2",
            "models/text-embedding-004",
            "models/embedding-001",
        ]:
            try:
                emb = GoogleGenerativeAIEmbeddings(model=model_name, google_api_key=key)
                return emb
            except Exception:
                continue

    # Local fallback
    from sentence_transformers import SentenceTransformer

    class LocalMiniLMEmbeddings:
        def __init__(self):
            try:
                self.model = SentenceTransformer(
                    "sentence-transformers/all-MiniLM-L6-v2", local_files_only=True
                )
            except Exception:
                self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            vecs = self.model.encode(texts, show_progress_bar=False)
            return [v.tolist() for v in vecs]

        def embed_query(self, text: str) -> list[float]:
            v = self.model.encode([text], show_progress_bar=False)[0]
            return v.tolist()

    return LocalMiniLMEmbeddings()


# ---------------------------------------------------------------------------
# PDF Loading & Chunking
# ---------------------------------------------------------------------------

def load_and_split_pdf(file_bytes: bytes, filename: str) -> list[Document]:
    """Extract text from PDF pages and split into semantic chunks with metadata."""
    reader = PdfReader(io.BytesIO(file_bytes))
    raw_docs: list[Document] = []

    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            raw_docs.append(
                Document(
                    page_content=text,
                    metadata={"source": filename, "page": idx + 1},
                )
            )

    if not raw_docs:
        return []

    # Semantic splitter with smart separators
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(raw_docs)


# ---------------------------------------------------------------------------
# FAISS Index Operations
# ---------------------------------------------------------------------------

def index_pdf_document(
    doc_id: str,
    file_bytes: bytes,
    filename: str,
    store_dir: Path,
    google_api_key: Optional[str] = None,
) -> dict:
    """Split, embed, and save a FAISS vector index for a document."""
    _ensure_event_loop()
    chunks = load_and_split_pdf(file_bytes, filename)
    if not chunks:
        return {"doc_id": doc_id, "chunks": 0, "error": "No text extracted from PDF"}

    embeddings = get_langchain_embeddings(google_api_key)
    vectorstore = FAISS.from_documents(chunks, embeddings)

    # Save to data/vector_stores/<doc_id>
    doc_store_path = store_dir / doc_id
    doc_store_path.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(doc_store_path))

    return {
        "doc_id": doc_id,
        "chunks": len(chunks),
        "source": filename,
    }


def load_doc_vectorstore(
    doc_id: str, store_dir: Path, google_api_key: Optional[str] = None
) -> Optional[FAISS]:
    """Load an existing FAISS vectorstore from disk."""
    _ensure_event_loop()
    doc_store_path = store_dir / doc_id
    if not doc_store_path.exists():
        return None
    embeddings = get_langchain_embeddings(google_api_key)
    try:
        return FAISS.load_local(
            str(doc_store_path),
            embeddings,
            allow_dangerous_deserialization=True,
        )
    except Exception:
        return None


def search_documents(
    query: str,
    doc_ids: list[str],
    store_dir: Path,
    google_api_key: Optional[str] = None,
    top_k: int = 4,
) -> list[Document]:
    """Perform similarity search across all selected document indexes."""
    _ensure_event_loop()
    all_results: list[tuple[Document, float]] = []

    for did in doc_ids:
        vs = load_doc_vectorstore(did, store_dir, google_api_key)
        if vs is None:
            continue
        try:
            hits = vs.similarity_search_with_relevance_scores(query, k=top_k)
            all_results.extend(hits)
        except Exception:
            docs = vs.similarity_search(query, k=top_k)
            all_results.extend([(d, 1.0) for d in docs])

    all_results.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in all_results[:top_k]]


# ---------------------------------------------------------------------------
# Gemini Generation with Grounded Context
# ---------------------------------------------------------------------------

def answer_with_gemini(
    query: str,
    doc_ids: list[str],
    store_dir: Path,
    google_api_key: str,
    model_name: str = "gemini-2.5-flash",
) -> dict:
    """
    Search relevant chunks and generate a grounded answer using Google Gemini.
    Returns: {"answer": str, "sources": list[dict]}
    """
    _ensure_event_loop()
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import SystemMessage, HumanMessage

    matched_docs = search_documents(
        query=query,
        doc_ids=doc_ids,
        store_dir=store_dir,
        google_api_key=google_api_key,
        top_k=4,
    )

    if not matched_docs:
        return {
            "answer": "No relevant information found in the indexed documents for your question.",
            "sources": [],
        }

    context_blocks = []
    sources_meta = []
    for i, doc in enumerate(matched_docs, start=1):
        src = doc.metadata.get("source", "Document")
        page = doc.metadata.get("page", 1)
        context_blocks.append(f"Passage {i} [Source: {src}, Page: {page}]:\n{doc.page_content}")
        sources_meta.append({"source": src, "page": page, "content": doc.page_content})

    context_str = "\n\n---\n\n".join(context_blocks)

    system_prompt = (
        "You are an expert AI document assistant.\n"
        "Your task is to answer the user's question accurately using ONLY the provided document passages.\n"
        "Rules:\n"
        "1. Strictly base your answer on the context passages provided below.\n"
        "2. If the context does not contain enough information to answer, state that clearly.\n"
        "3. Always cite the document source name and page number when stating facts.\n"
        "4. Format your answer with clean Markdown bullet points and bold headers where appropriate."
    )

    user_prompt = (
        f"Context from uploaded documents:\n\n{context_str}\n\n"
        f"User Question: {query}\n\n"
        "Provide a clear, well-structured answer with citations:"
    )

    llm = ChatGoogleGenerativeAI(
        model=model_name or "gemini-2.5-flash",
        google_api_key=google_api_key,
        temperature=0.1,
    )

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    return {
        "answer": response.content,
        "sources": sources_meta,
    }


# ---------------------------------------------------------------------------
# Copilot SDK Tool Registration
# ---------------------------------------------------------------------------

class LangChainRAGParams(BaseModel):
    question: str = Field(description="The user's question regarding the uploaded PDF documents")
    doc_ids: list[str] = Field(
        default_factory=list,
        description="Optional list of specific document IDs to search",
    )


def build_copilot_rag_tool(
    store_dir: Path,
    active_doc_ids_fn: Callable[[], list[str]],
    get_google_api_key_fn: Callable[[], str],
) -> Tool:
    """Register LangChain FAISS retrieval as a custom tool in Copilot SDK."""

    @define_tool(
        name="retrieve_from_documents",
        description=(
            "Search indexed PDF documents using LangChain and FAISS to retrieve relevant passages. "
            "Use this tool whenever the user asks questions about uploaded documents."
        ),
        skip_permission=True,
    )
    async def retrieve_from_documents(
        params: LangChainRAGParams, invocation: ToolInvocation
    ) -> str:
        _ensure_event_loop()
        doc_ids = params.doc_ids or active_doc_ids_fn()
        if not doc_ids:
            return json.dumps({"error": "No documents are currently indexed. Please upload a PDF first."})

        docs = search_documents(
            query=params.question,
            doc_ids=doc_ids,
            store_dir=store_dir,
            google_api_key=get_google_api_key_fn(),
            top_k=4,
        )

        if not docs:
            return json.dumps({"error": "No relevant passages found for this question."})

        passages = [
            f"[Source: {d.metadata.get('source', 'doc')} | Page: {d.metadata.get('page', '?')}]\n{d.page_content}"
            for d in docs
        ]
        return json.dumps({"passages": passages}, ensure_ascii=False)

    return retrieve_from_documents
