"""
Utility helpers shared across pages.
"""
import difflib
from pathlib import Path


def compute_diff(original: str, improved: str, filename: str = "file") -> str:
    """Return a unified diff string between original and improved content."""
    orig_lines = original.splitlines(keepends=True)
    new_lines = improved.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        new_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm="",
    )
    return "".join(diff)


def read_file_safe(path: Path) -> str | None:
    """Read a text file, returning None on error."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def workspace_files(root: Path, extensions: tuple = (".py", ".md", ".txt", ".js", ".ts", ".json", ".yaml", ".yml")) -> list[Path]:
    """Return a list of text files in the workspace directory."""
    files = []
    for ext in extensions:
        files.extend(root.rglob(f"*{ext}"))
    return sorted(files)

