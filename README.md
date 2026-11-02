# Agentic Workbench

A complete, working application demonstrating AI-powered capabilities using Python, Streamlit, and the **GitHub Copilot SDK for Python**.

## Features

| Feature | Description |
|---|---|
| 💬 **Conversational Chat** | Continuous multi-turn chat with context using Copilot SDK sessions; local JSON conversation persistence |
| 📄 **PDF Chat (LangChain + Gemini RAG)** | Upload PDFs, extract text with page metadata, semantic chunking via LangChain, store in FAISS vector DB, and generate grounded answers with Google Gemini 2.5 (with expandable source passages) |
| 🐙 **GitHub Repository Assistant** | Read-only repository inspection using the GitHub MCP server integration via Copilot SDK |
| 🔍 **Skill-Based File Reviewer** | Configurable review skills (Quality, Python Code, Documentation), unified diff viewer, side-by-side comparison, and **strict human approval gate** before saving |

## Quick Start (Windows PowerShell)

### 1. Configure credentials

```powershell
cd agentic_workbench
Copy-Item .env.example .env
notepad .env   # Fill in your GITHUB_TOKEN
```

### 2. Run the application

You can launch using the one-click script:
```powershell
.\start.ps1
```
Or manually with:
```powershell
python -m streamlit run app.py
```

Open your browser at `http://localhost:8501`.

## Project Structure

```
agentic_workbench/
├── app.py                    # Main entry point & native st.navigation router
├── start.ps1                 # Windows PowerShell launch script
├── start.bat                 # Windows CMD launch batch file
├── .env.example              # Environment configuration template
├── requirements.txt          # Project dependencies
├── README.md                 # Full documentation
├── test_imports.py           # Verification smoke test
│
├── core/
│   ├── config.py             # Settings via pydantic-settings
│   ├── agent.py              # GitHub Copilot SDK client & session bridge
│   └── conversation_store.py # Local JSON persistence for chat histories
│
├── tools/
│   ├── langchain_rag.py      # LangChain RAG pipeline (FAISS + Gemini 2.5 + @define_tool)
│   ├── rag_tool.py           # Standard FAISS RAG tool registered with @define_tool
│   └── review_skills.py      # Review skill definitions & prompt engineering
│
├── pages/
│   ├── chat.py               # 💬 Continuous Conversational Chat
│   ├── pdf_chat.py           # 📄 PDF Chat with FAISS RAG
│   ├── github_assistant.py   # 🐙 GitHub Repo Assistant via MCP
│   └── file_reviewer.py      # 🔍 Skill-based Reviewer with Diff & Approval
│
├── utils/
│   └── helpers.py            # Unified diff generator & workspace file helpers
│
└── data/                     # Local storage (auto-created)
    ├── conversations/        # Saved chat histories (.json)
    ├── uploads/              # Uploaded PDF files
    └── vector_stores/        # FAISS indexes (.index + .meta)
```

## Environment Configuration (`.env`)

| Variable | Description | Default |
|---|---|---|
| `GITHUB_TOKEN` | GitHub Personal Access Token with Copilot access | *(required)* |
| `GOOGLE_API_KEY` | Google Gemini API Key for LangChain RAG | *(optional/UI input)* |
| `GEMINI_MODEL` | Gemini Model (e.g. `gemini-2.5-flash`) | `gemini-2.5-flash` |
| `GITHUB_MCP_TOKEN` | GitHub token for MCP server (defaults to GITHUB_TOKEN) | *(optional)* |
| `COPILOT_MODEL` | Copilot model name | `gpt-4o` |
| `EMBEDDING_MODEL` | Hugging Face embedding model id | `sentence-transformers/all-MiniLM-L6-v2` |
| `DATA_DIR` | Local storage directory path | `data` |

## Technical Implementation Details

- **Agent Runtime**: Official `github-copilot-sdk` v1.0.28+ with `copilot-runtime.exe` pre-staged.
- **Async Backend**: Python `asyncio` integrated into Streamlit's event loop via synchronous wrappers.
- **Custom Tool Registration**: Built using `@define_tool` with Pydantic parameter schemas (`RAGQueryParams`).
- **MCP Integration**: `MCPHTTPServerConfig` pointing to `https://api.githubcopilot.com/mcp/` with read-only repository inspection.
- **FAISS Vector Store**: Flat L2 indexing, overlapping text chunking, local pickle chunk metadata, and zero external vector service dependency.
- **Human-in-the-Loop Safety**: The File Reviewer computes unified diffs with Python's `difflib` and strictly gates disk writes behind an explicit user approval button.
