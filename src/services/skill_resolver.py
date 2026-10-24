"""Skill card resolver — scans the skills directory for progressive disclosure."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config.settings import get_settings

_resolver: "SkillResolver | None" = None


@dataclass
class SkillCard:
    skill_id: str
    name: str
    description: str = ""
    version: str | None = None
    tags: list[str] = field(default_factory=list)
    env_list: list[str] = field(default_factory=list)
    skill_path: str | None = None
    locator_path: str | None = None


class SkillResolver:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path

    def _load_cards(self) -> list[SkillCard]:
        cards: list[SkillCard] = []
        if not self.base_path.exists():
            return cards

        for skill_dir in sorted(p for p in self.base_path.iterdir() if p.is_dir()):
            skill_md = skill_dir / "SKILL.md"
            meta: dict[str, Any] = {}
            description = ""
            if skill_md.exists():
                text = skill_md.read_text(encoding="utf-8")
                description = _first_paragraph(text)
                meta = _parse_frontmatter(text)

            cards.append(
                SkillCard(
                    skill_id=str(meta.get("id") or skill_dir.name),
                    name=str(meta.get("name") or skill_dir.name),
                    description=str(meta.get("description") or description),
                    version=meta.get("version"),
                    tags=list(meta.get("tags") or [skill_dir.name]),
                    env_list=list(meta.get("env") or ["dev"]),
                    skill_path=str(skill_dir),
                    locator_path=str(skill_dir),
                )
            )
        return cards

    async def search(
        self,
        *,
        tags: list[str] | None = None,
        env: str | None = None,
        limit: int = 8,
    ) -> list[SkillCard]:
        cards = self._load_cards()
        wanted = {t.lower() for t in (tags or [])}
        results: list[SkillCard] = []
        for card in cards:
            card_tags = {t.lower() for t in card.tags}
            if wanted and not (wanted & card_tags) and card.skill_id not in wanted:
                # Also match agent role tags loosely against skill folder names.
                if not any(tag in card.skill_id.lower() or tag in card.name.lower() for tag in wanted):
                    # Keep all cards when tags are role names that skills declare.
                    role_aliases = {
                        "supervisor_agent": "supervisor",
                        "discovery_agent": "discovery",
                        "design_agent": "migration",
                    }
                    aliases = {role_aliases.get(t, t) for t in wanted}
                    if not any(a in card.skill_id.lower() or a in card.name.lower() for a in aliases):
                        if not (wanted & card_tags):
                            continue
            if env and card.env_list and env not in card.env_list and "all" not in card.env_list:
                continue
            results.append(card)
            if len(results) >= limit:
                break
        return results


def _first_paragraph(text: str) -> str:
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        body = parts[2] if len(parts) >= 3 else text
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def _parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    meta: dict[str, Any] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key] = [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
        else:
            meta[key] = value
    return meta


def get_resolver() -> SkillResolver:
    global _resolver
    if _resolver is None:
        settings = get_settings()
        raw = Path(settings.skills_base_path)
        base = raw if raw.is_absolute() else Path.cwd() / raw
        _resolver = SkillResolver(base)
    return _resolver
