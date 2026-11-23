"""Load file-review skills from GitHub Copilot SKILL.md files."""

import re
from dataclasses import dataclass
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[1] / ".github" / "skills"
_FRONTMATTER_PATTERN = re.compile(
    r"\A---\r?\n(?P<metadata>.*?)\r?\n---\r?\n(?P<body>.*)\Z",
    re.DOTALL,
)
_SKILL_NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


@dataclass(frozen=True)
class ReviewSkill:
    name: str
    title: str
    system_prompt: str


def _read_skill(skill_file: Path) -> ReviewSkill:
    content = skill_file.read_text(encoding="utf-8")
    match = _FRONTMATTER_PATTERN.match(content)
    if not match:
        raise ValueError(f"Skill file must start with YAML frontmatter: {skill_file}")

    metadata: dict[str, str] = {}
    for line in match.group("metadata").splitlines():
        key, separator, value = line.partition(":")
        if not separator or not key.strip() or not value.strip():
            raise ValueError(f"Invalid skill metadata in {skill_file}: {line}")
        metadata[key.strip()] = value.strip()

    name = metadata.get("name", "")
    if not _SKILL_NAME_PATTERN.fullmatch(name):
        raise ValueError(f"Skill name must be lowercase kebab-case in {skill_file}")
    if skill_file.parent.name != name:
        raise ValueError(f"Skill folder must match its metadata name in {skill_file}")

    body = match.group("body").strip()
    heading, separator, instructions = body.partition("\n")
    if not heading.startswith("# ") or not separator:
        raise ValueError(f"Skill file must have a level-one title heading: {skill_file}")
    if not metadata.get("description"):
        raise ValueError(f"Skill description is required in {skill_file}")
    if not instructions.strip():
        raise ValueError(f"Skill instructions are required in {skill_file}")

    return ReviewSkill(
        name=name,
        title=heading[2:].strip(),
        system_prompt=instructions.strip(),
    )


def _load_skills() -> dict[str, ReviewSkill]:
    skills: dict[str, ReviewSkill] = {}
    for skill_file in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        skill = _read_skill(skill_file)
        if skill.title in skills:
            raise ValueError(f"Duplicate review skill title: {skill.title}")
        skills[skill.title] = skill
    if not skills:
        raise FileNotFoundError(f"No review skills found in {SKILLS_DIR}")
    return skills


SKILLS = _load_skills()
SKILL_NAMES = list(SKILLS)


def get_skill_system_prompt(skill_name: str) -> str:
    try:
        return SKILLS[skill_name].system_prompt
    except KeyError as error:
        raise ValueError(f"Unknown review skill: {skill_name}") from error


def extract_improved_content(reply: str) -> str | None:
    """
    Parse the ```improved ... ``` block from the agent's reply.
    Returns the content string, or None if not found.
    """
    pattern = r"```improved\s*\n(.*?)```"
    match = re.search(pattern, reply, re.DOTALL)
    if match:
        return match.group(1)
    fallback_pattern = r"```(?:\w+)?\s*\n(.*?)```"
    fallback_match = re.search(fallback_pattern, reply, re.DOTALL)
    if fallback_match:
        return fallback_match.group(1)
    return None
