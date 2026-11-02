# Agentic Workbench

A streamlined, robust application demonstrating AI-powered capabilities using Python, Streamlit, and the **GitHub Copilot SDK for Python**.

## Features

| Feature | Description |
|---|---|
| 💬 **Conversational Chat** | Continuous multi-turn chat maintaining context using Copilot SDK sessions; local JSON conversation persistence |
| 🐙 **GitHub Repository Assistant** | Read-only repository inspection using the official GitHub MCP server integration via Copilot SDK |
| 🔍 **Skill-Based File Reviewer** | Configurable review skills (Quality, Python Code, Documentation), unified diff viewer, side-by-side comparison, and **strict human approval gate** before saving |

## Quick Start (Local)

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

## Deploy to Streamlit Community Cloud

1. Push your repository to GitHub:
   ```powershell
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/agentic-workbench.git
   git push -u origin main
   ```
2. Log in to [share.streamlit.io](https://share.streamlit.io/).
3. Click **"Create app"** and select your repository (`app.py` as main file).
4. Under **Advanced settings -> Secrets**, add:
   ```toml
   GITHUB_TOKEN = "your_github_pat_token"
   COPILOT_MODEL = "gpt-4o"
   ```
5. Click **Deploy!**

## Project Structure

```
agentic_workbench/
├── app.py                    # Main entry point & native st.navigation router
├── start.ps1                 # Windows PowerShell launch script
├── start.bat                 # Windows CMD launch batch file
├── .env.example              # Environment configuration template
├── requirements.txt          # Lightweight project dependencies
├── README.md                 # Full documentation
├── test_imports.py           # Verification smoke test
│
├── core/
│   ├── config.py             # Settings via pydantic-settings & st.secrets
│   ├── agent.py              # GitHub Copilot SDK client & session bridge
│   └── conversation_store.py # Local JSON persistence for chat histories
│
├── tools/
│   └── review_skills.py      # Review skill definitions & prompt engineering
│
├── pages/
│   ├── chat.py               # 💬 Continuous Conversational Chat
│   ├── github_assistant.py   # 🐙 GitHub Repo Assistant via MCP
│   └── file_reviewer.py      # 🔍 Skill-based Reviewer with Diff & Approval
│
├── utils/
│   └── helpers.py            # Unified diff generator & workspace file helpers
│
└── data/                     # Local storage (auto-created)
    └── conversations/        # Saved chat histories (.json)
```

## Environment Configuration (`.env` or Streamlit Secrets)

| Variable | Description | Default |
|---|---|---|
| `GITHUB_TOKEN` | GitHub Personal Access Token with Copilot access | *(required)* |
| `GITHUB_MCP_TOKEN` | GitHub token for MCP server (defaults to GITHUB_TOKEN) | *(optional)* |
| `COPILOT_MODEL` | Copilot model name | `gpt-4o` |
| `DATA_DIR` | Local storage directory path | `data` |

## Technical Implementation Details

- **Agent Runtime**: Official `github-copilot-sdk` v1.0.28+ with `copilot-runtime.exe` pre-staged.
- **Async Backend**: Python `asyncio` integrated into Streamlit's event loop via thread-safe `AsyncBridge`.
- **MCP Integration**: `MCPHTTPServerConfig` pointing to `https://api.githubcopilot.com/mcp/` for read-only repository inspection.
- **Human-in-the-Loop Safety**: The File Reviewer computes unified diffs with Python's `difflib` and strictly gates disk writes behind an explicit user approval button.
