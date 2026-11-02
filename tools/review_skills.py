"""
Skill-based file review tools.

Each "skill" is a system prompt + a structured review request that the
Copilot agent executes against a file's content.
"""
import sys

sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")

from pydantic import BaseModel, Field
from copilot import Tool, ToolInvocation, define_tool

# -----------------------------------------------------------------------
# Skill definitions
# -----------------------------------------------------------------------

SKILLS: dict[str, dict] = {
    "Quality Reviewer": {
        "label": "Quality Reviewer",
        "system_prompt": (
            "You are a thorough software quality reviewer. Your job is to review the "
            "provided file and produce:\n"
            "1. A **summary** of what the file does.\n"
            "2. A **list of issues** (bugs, anti-patterns, missing error handling, style violations).\n"
            "3. An **improved version** of the file that fixes all identified issues.\n"
            "Always wrap the improved file content in ```improved\\n<content>\\n``` fences."
        ),
    },
    "Python Code Reviewer": {
        "label": "Python Code Reviewer",
        "system_prompt": (
            "You are a senior Python engineer performing a code review. Your job is to:\n"
            "1. Identify bugs, type-safety issues, PEP-8 violations, and missing docstrings.\n"
            "2. Suggest modern Python idioms and performance improvements.\n"
            "3. Produce an **improved version** of the file.\n"
            "Always wrap the improved file content in ```improved\\n<content>\\n``` fences."
        ),
    },
    "Documentation Reviewer": {
        "label": "Documentation Reviewer",
        "system_prompt": (
            "You are a technical writer reviewing code documentation. Your job is to:\n"
            "1. Check that all public functions, classes, and modules have accurate docstrings.\n"
            "2. Improve clarity, completeness, and format.\n"
            "3. Produce an **improved version** of the file with enhanced docs.\n"
            "Always wrap the improved file content in ```improved\\n<content>\\n``` fences."
        ),
    },
}

SKILL_NAMES = list(SKILLS.keys())


def get_skill_system_prompt(skill_name: str) -> str:
    return SKILLS.get(skill_name, SKILLS["Quality Reviewer"])["system_prompt"]


# -----------------------------------------------------------------------
# Helper: parse improved content from agent reply
# -----------------------------------------------------------------------

def extract_improved_content(reply: str) -> str | None:
    """
    Parse the ```improved ... ``` block from the agent's reply.
    Returns the content string, or None if not found.
    """
    import re
    pattern = r"```improved\s*\n(.*?)```"
    match = re.search(pattern, reply, re.DOTALL)
    if match:
        return match.group(1)
    # Fallback: any code fence
    pattern2 = r"```(?:\w+)?\s*\n(.*?)```"
    match2 = re.search(pattern2, reply, re.DOTALL)
    if match2:
        return match2.group(1)
    return None

