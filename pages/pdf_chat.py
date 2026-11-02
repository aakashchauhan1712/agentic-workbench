"""
Page: 📄 PDF Chat (LangChain + Google Gemini RAG)
------------------------------------------------
Upload one or more PDFs → chunk with LangChain RecursiveCharacterTextSplitter
→ embed & store in FAISS vector database
→ generate grounded answers with Google Gemini 2.5 and explicit source citations.
"""
import asyncio
import sys
sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")

import hashlib
from pathlib import Path

import streamlit as st

from core.agent import create_session, send_message, run_sync
from core.config import Settings
from core.conversation_store import ConversationStore
from tools.langchain_rag import (
    index_pdf_document,
    answer_with_gemini,
    build_copilot_rag_tool,
    search_documents,
    _ensure_event_loop,
)

# ── Ensure Streamlit worker thread has an asyncio loop ────────────────
_ensure_event_loop()

# ── Shared state ───────────────────────────────────────────────────────
settings: Settings = st.session_state["settings"]
conv_store: ConversationStore = st.session_state["conv_store"]
copilot_client = st.session_state.get("copilot_client")

# ── Page header ────────────────────────────────────────────────────────
st.title("📄 PDF Chat (LangChain + Gemini RAG)")
st.caption(
    "Semantic PDF retrieval using LangChain, local FAISS vector search, and Google Gemini 2.5."
)

store_dir = settings.vector_stores_dir
store_dir.mkdir(parents=True, exist_ok=True)

# ── Session state initialisation ───────────────────────────────────────
if "rag_doc_ids" not in st.session_state:
    st.session_state["rag_doc_ids"] = []
if "rag_doc_names" not in st.session_state:
    st.session_state["rag_doc_names"] = {}
if "rag_messages" not in st.session_state:
    st.session_state["rag_messages"] = []

doc_ids: list[str] = st.session_state["rag_doc_ids"]
doc_names: dict[str, str] = st.session_state["rag_doc_names"]
messages: list[dict] = st.session_state["rag_messages"]

google_api_key = settings.resolved_google_api_key


def doc_id_for(filename: str, content: bytes) -> str:
    h = hashlib.md5(content).hexdigest()[:8]
    safe_name = "".join(c if c.isalnum() else "_" for c in filename)
    return f"{safe_name}_{h}"


# ── Sidebar: Configuration & Document Management ─────────────────────
with st.sidebar:
    st.subheader("⚙️ RAG Engine")

    if google_api_key:
        st.success("Google Gemini Connected", icon="✨")
    else:
        st.warning("No GOOGLE_API_KEY in .env. Using local embeddings.", icon="⚠️")

    # Engine Selection
    rag_engine = st.radio(
        "Answering Engine",
        [
            "⚡ LangChain + Google Gemini 2.5",
            "🤖 Copilot SDK + LangChain Tool",
        ],
        index=0 if google_api_key else 1,
        help="Select whether answers are generated via Google Gemini 2.5 or GitHub Copilot.",
    )

    st.divider()
    st.subheader("📂 Upload PDF Documents")
    uploaded = st.file_uploader(
        "Select PDF file(s)",
        type=["pdf"],
        accept_multiple_files=True,
        key="pdf_uploader",
    )

    if uploaded:
        for uf in uploaded:
            file_bytes = uf.read()
            did = doc_id_for(uf.name, file_bytes)
            if did not in doc_ids:
                with st.spinner(f"Chunking and embedding {uf.name}…"):
                    try:
                        _ensure_event_loop()
                        res = index_pdf_document(
                            doc_id=did,
                            file_bytes=file_bytes,
                            filename=uf.name,
                            store_dir=store_dir,
                            google_api_key=google_api_key or None,
                        )
                        if res.get("chunks", 0) > 0:
                            doc_ids.append(did)
                            doc_names[did] = uf.name
                            st.session_state["rag_doc_ids"] = doc_ids
                            st.session_state["rag_doc_names"] = doc_names
                            st.session_state.pop("copilot_session_rag", None)
                            st.success(f"Indexed **{uf.name}** ({res['chunks']} chunks)", icon="✅")
                        else:
                            st.error(f"Could not extract text from {uf.name}")
                    except Exception as e:
                        st.error(f"Error indexing {uf.name}: {e}")

    st.divider()
    st.subheader("Indexed Documents")
    if not doc_ids:
        st.caption("No documents indexed yet.")
    for did in doc_ids:
        col1, col2 = st.columns([4, 1])
        with col1:
            name = doc_names.get(did, did)
            st.caption(f"📄 **{name}**")
        with col2:
            if st.button("✕", key=f"rm_{did}"):
                doc_ids.remove(did)
                doc_names.pop(did, None)
                st.session_state["rag_doc_ids"] = doc_ids
                st.session_state["rag_doc_names"] = doc_names
                st.session_state.pop("copilot_session_rag", None)
                st.rerun()

    if doc_ids and st.button("🗑️ Clear All Documents", use_container_width=True):
        st.session_state["rag_doc_ids"] = []
        st.session_state["rag_doc_names"] = {}
        st.session_state.pop("copilot_session_rag", None)
        st.rerun()

    if st.button("🔄 New Chat", use_container_width=True):
        st.session_state["rag_messages"] = []
        st.session_state.pop("copilot_session_rag", None)
        st.rerun()


# ── Copilot Session with LangChain Tool ───────────────────────────────
def _get_copilot_rag_session():
    if "copilot_session_rag" not in st.session_state:
        if copilot_client is None:
            raise RuntimeError("GitHub Copilot Client is not connected. Check GITHUB_TOKEN.")

        tool = build_copilot_rag_tool(
            store_dir=store_dir,
            active_doc_ids_fn=lambda: st.session_state.get("rag_doc_ids", []),
            get_google_api_key_fn=lambda: settings.resolved_google_api_key,
        )
        system_msg = (
            "You are a helpful document assistant. "
            "When the user asks about uploaded PDFs, ALWAYS invoke the `retrieve_from_documents` tool. "
            "Base your answers strictly on the retrieved passages and cite document names and page numbers."
        )
        session = run_sync(
            create_session(
                client=copilot_client,
                settings=settings,
                tools=[tool],
                system_message=system_msg,
            )
        )
        st.session_state["copilot_session_rag"] = session
    return st.session_state["copilot_session_rag"]


# ── Render Message History ─────────────────────────────────────────────
for msg in messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sources" in msg and msg["sources"]:
            with st.expander(f"🔍 View {len(msg['sources'])} retrieved source passages"):
                for idx, src in enumerate(msg["sources"], start=1):
                    st.markdown(f"**Passage {idx}** — *{src.get('source')}* (Page {src.get('page')})")
                    st.code(src.get("content", ""), language="text")

if not doc_ids:
    st.info("👆 Upload one or more PDFs in the sidebar to start asking questions about them.")

# ── Chat Input & Answer Generation ────────────────────────────────────
if prompt := st.chat_input("Ask a question about your uploaded documents…"):
    if not doc_ids:
        st.warning("Please upload at least one PDF before asking questions.")
        st.stop()

    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        sources = []
        with st.spinner("Searching document vectors & generating grounded answer…"):
            try:
                _ensure_event_loop()
                if "Gemini" in rag_engine:
                    if not google_api_key:
                        reply = (
                            "⚠️ **Google Gemini API Key is required for this engine.** "
                            "Please add `GOOGLE_API_KEY` to your `.env` file."
                        )
                    else:
                        result = answer_with_gemini(
                            query=prompt,
                            doc_ids=doc_ids,
                            store_dir=store_dir,
                            google_api_key=google_api_key,
                            model_name=settings.gemini_model,
                        )
                        reply = result["answer"]
                        sources = result.get("sources", [])
                else:
                    session = _get_copilot_rag_session()
                    reply = run_sync(send_message(session, prompt, timeout=180.0))
            except Exception as e:
                reply = f"⚠️ Error processing query: {e}"

        st.markdown(reply)
        if sources:
            with st.expander(f"🔍 View {len(sources)} retrieved source passages"):
                for idx, src in enumerate(sources, start=1):
                    st.markdown(f"**Passage {idx}** — *{src.get('source')}* (Page {src.get('page')})")
                    st.code(src.get("content", ""), language="text")

    messages.append({"role": "assistant", "content": reply, "sources": sources})
    st.session_state["rag_messages"] = messages
    st.rerun()
