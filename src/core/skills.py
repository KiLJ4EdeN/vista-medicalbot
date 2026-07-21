from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import frontmatter

ROOT = Path(__file__).resolve().parent.parent.parent
PROMPTS_DIR = ROOT / "src" / "prompts"
SKILLS_DIR = ROOT / "src" / "skills"


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    description: str
    content: str


@lru_cache
def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if path.parent != PROMPTS_DIR or not path.is_file():
        raise ValueError(f"Unknown prompt: {name}")
    return path.read_text(encoding="utf-8").strip()


@lru_cache
def load_skills() -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        document = frontmatter.loads(path.read_text(encoding="utf-8"))
        name = str(document.metadata.get("name", path.stem)).strip()
        description = str(document.metadata.get("description", "")).strip()
        if not name or not description:
            raise ValueError(f"Skill {path.name} requires name and description")
        skills[name] = Skill(name=name, description=description, content=document.content.strip())
    return skills


def skill_catalog() -> str:
    return "\n".join(f"- {skill.name}: {skill.description}" for skill in load_skills().values())
