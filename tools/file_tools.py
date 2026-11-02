"""
Custom tools defined for the Copilot SDK agent using @define_tool and Pydantic.
Demonstrates:
- Pydantic BaseModel input validation schema.
- @define_tool decorator registration.
- Safe programmatic execution inside Copilot SDK sessions.
"""
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")

from pydantic import BaseModel, Field
from copilot import Tool, ToolInvocation, define_tool


class InspectFileParams(BaseModel):
    file_path: str = Field(
        description="Relative path to the workspace file to inspect (e.g. 'app.py' or 'core/config.py')"
    )
    include_metrics: bool = Field(
        default=True,
        description="Whether to include line counts, imports, and AST structure analysis",
    )


@define_tool(
    name="inspect_workspace_file",
    description=(
        "Reads a file from the workspace, verifies its syntax, and computes code metrics "
        "(lines of code, function count, import list). Always use this tool when asked to "
        "inspect, read, or analyze files in the current repository."
    ),
    skip_permission=True,
)
async def inspect_workspace_file(
    params: InspectFileParams, invocation: ToolInvocation = None
) -> str:
    """Read a local workspace file safely and return content + analysis metrics."""
    workspace_root = Path.cwd()
    target_path = (workspace_root / params.file_path).resolve()

    # Security check: Ensure file is within workspace root
    try:
        target_path.relative_to(workspace_root)
    except ValueError:
        return json.dumps({"error": f"Access denied: '{params.file_path}' is outside the workspace."})

    if not target_path.exists():
        return json.dumps({"error": f"File not found: '{params.file_path}'"})

    if not target_path.is_file():
        return json.dumps({"error": f"Path '{params.file_path}' is a directory, not a file."})

    try:
        content = target_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return json.dumps({"error": f"Failed to read file: {e}"})

    metrics = {
        "file_name": target_path.name,
        "size_bytes": len(content.encode("utf-8")),
        "line_count": len(content.splitlines()),
    }

    # Python-specific AST metrics
    if params.include_metrics and target_path.suffix == ".py":
        try:
            tree = ast.parse(content)
            functions = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            imports = []
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    imports.extend(alias.name for alias in n.names)
                elif isinstance(n, ast.ImportFrom) and n.module:
                    imports.append(n.module)

            metrics["python_analysis"] = {
                "functions": functions,
                "classes": classes,
                "imported_modules": list(set(imports)),
                "syntax_valid": True,
            }
        except SyntaxError as se:
            metrics["python_analysis"] = {
                "syntax_valid": False,
                "syntax_error": f"Line {se.lineno}: {se.msg}",
            }

    # Cap content snippet if too large to prevent token explosion
    preview_limit = 10000
    snippet = content[:preview_limit]
    if len(content) > preview_limit:
        snippet += f"\n... [Truncated {len(content) - preview_limit} additional characters]"

    return json.dumps({
        "metrics": metrics,
        "content": snippet,
    }, ensure_ascii=False, indent=2)

