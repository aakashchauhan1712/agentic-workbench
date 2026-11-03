"""
Page: 🔍 Skill-Based File Reviewer
------------------------------------
1. User selects a skill (Quality Reviewer / Python Code Reviewer / Documentation Reviewer)
2. User uploads a file OR selects one from the workspace
3. Agent reads the file and produces a review + improved version
4. A unified diff is displayed
5. User must explicitly approve before the file is overwritten

IMPORTANT: Files are NEVER modified without explicit user approval.
"""
import sys
sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")

from pathlib import Path

import streamlit as st

from core.agent import create_session_and_client, chat_with_session
from core.config import Settings
from tools.review_skills import SKILL_NAMES, get_skill_system_prompt, extract_improved_content
from utils.helpers import compute_diff, read_file_safe, workspace_files

# ── Shared state ───────────────────────────────────────────────────────
settings: Settings = st.session_state["settings"]

# ── Page header ────────────────────────────────────────────────────────
st.title("🔍 Skill-Based File Reviewer")
st.caption("Select a review skill, pick a file, and let the AI suggest improvements.")

if not settings.resolved_github_token:
    st.error("No GITHUB_TOKEN found. Add it to your `.env` file and restart.")
    st.stop()

# ── Session state ─────────────────────────────────────────────────────
if "review_result" not in st.session_state:
    st.session_state["review_result"] = None  # {reply, improved, original, filepath}


# ── Step 1: Skill & file selection ────────────────────────────────────
col1, col2 = st.columns([1, 2])

with col1:
    selected_skill = st.selectbox("🎯 Review Skill", SKILL_NAMES)

with col2:
    file_source = st.radio(
        "File Source",
        ["Upload a file", "Select from workspace"],
        horizontal=True,
    )

# ── File picker ───────────────────────────────────────────────────────
original_content: str | None = None
file_name: str = ""
file_path: Path | None = None

if file_source == "Upload a file":
    uploaded = st.file_uploader(
        "Upload a file to review",
        type=["py", "md", "txt", "js", "ts", "json", "yaml", "yml", "html", "css"],
        key="review_uploader",
    )
    if uploaded:
        try:
            original_content = uploaded.read().decode("utf-8", errors="replace")
            file_name = uploaded.name
        except Exception as e:
            st.error(f"Could not read file: {e}")
else:
    workspace_root = Path.cwd()
    all_files = workspace_files(workspace_root)
    file_options = [str(f.relative_to(workspace_root)) for f in all_files]

    if not file_options:
        st.info("No supported files found in the current workspace.")
    else:
        selected_rel = st.selectbox("Select a workspace file", file_options)
        if selected_rel:
            file_path = workspace_root / selected_rel
            file_name = file_path.name
            original_content = read_file_safe(file_path)
            if original_content is None:
                st.error(f"Could not read {selected_rel}")

# ── Preview the selected file ─────────────────────────────────────────
if original_content is not None:
    with st.expander(f"📄 {file_name} (original)", expanded=False):
        lang = file_name.rsplit(".", 1)[-1] if "." in file_name else "text"
        st.code(original_content[:8000], language=lang)
        if len(original_content) > 8000:
            st.caption(f"… (showing first 8 000 chars of {len(original_content)} total)")

# ── Review button ─────────────────────────────────────────────────────
st.divider()

run_review = st.button(
    f"🚀 Run {selected_skill}",
    type="primary",
    disabled=original_content is None,
    use_container_width=True,
)

if run_review and original_content:
    system_prompt = get_skill_system_prompt(selected_skill)

    # For file review, we create a fresh session each time (no ongoing conversation needed)
    with st.spinner(f"Running {selected_skill}…"):
        try:
            # Create a brand-new session with the skill's system prompt
            client, session = create_session_and_client(
                settings=settings,
                system_message=system_prompt,
            )
            user_prompt = (
                f"Please review the following file named `{file_name}`:\n\n"
                f"```\n{original_content[:12000]}\n```\n\n"
                f"Provide your review and the improved version."
            )
            reply = chat_with_session(settings, session, user_prompt, timeout=300.0)
        except Exception as e:
            reply = f"⚠️ Error during review: {e}"

    improved = extract_improved_content(reply)

    st.session_state["review_result"] = {
        "reply": reply,
        "improved": improved,
        "original": original_content,
        "file_name": file_name,
        "file_path": str(file_path) if file_path else None,
    }
    st.rerun()


# ── Display review results ────────────────────────────────────────────
result = st.session_state.get("review_result")

if result:
    st.subheader("📋 Review")
    st.markdown(result["reply"])

    improved = result.get("improved")
    if improved:
        st.subheader("📝 Proposed Changes (Diff)")
        diff_text = compute_diff(
            result["original"],
            improved,
            filename=result["file_name"],
        )

        if diff_text:
            st.code(diff_text, language="diff")
        else:
            st.success("No changes proposed – the file looks good already!")

        # ── Tab: side-by-side comparison ───────────────────────────────
        with st.expander("👁️ Side-by-side comparison"):
            c_orig, c_new = st.columns(2)
            lang = result["file_name"].rsplit(".", 1)[-1] if "." in result["file_name"] else "text"
            with c_orig:
                st.caption("Original")
                st.code(result["original"][:4000], language=lang)
            with c_new:
                st.caption("Improved")
                st.code(improved[:4000], language=lang)

        # ── Approval gate ─────────────────────────────────────────────
        st.divider()
        st.warning(
            "⚠️ **Review the diff carefully before approving.** "
            "The file will only be saved after you click the button below."
        )

        save_path = result.get("file_path")
        if save_path:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✅ Approve & Save Changes", type="primary", use_container_width=True):
                    try:
                        Path(save_path).write_text(improved, encoding="utf-8")
                        st.success(f"✅ File saved: `{save_path}`")
                        st.session_state["review_result"] = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving file: {e}")
            with col_b:
                if st.button("❌ Discard Changes", use_container_width=True):
                    st.session_state["review_result"] = None
                    st.rerun()
        else:
            # File was uploaded (not from workspace) — offer download instead
            st.download_button(
                label="⬇️ Download Improved Version",
                data=improved.encode("utf-8"),
                file_name=f"improved_{result['file_name']}",
                mime="text/plain",
                use_container_width=True,
            )
            if st.button("🗑️ Clear Results", use_container_width=True):
                st.session_state["review_result"] = None
                st.rerun()
    else:
        st.info("The agent did not produce a structured improved version. See the review above.")
        if st.button("🔄 Clear", use_container_width=True):
            st.session_state["review_result"] = None
            st.rerun()
