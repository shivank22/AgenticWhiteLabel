"""Utilities for embedding resolved skill metadata into agent system prompts.

We intentionally embed only a compact summary (id/name/version/description/path/tags)
so prompts remain stable and token-efficient.

Skill bodies (SKILL.md) are *not* embedded here by default.
"""

from __future__ import annotations

from typing import Iterable

from src.services.skill_resolver import SkillCard, get_resolver


async def build_skill_cards_section(
    *,
    tags: list[str],
    env: str | None = None,
    limit: int = 8,
) -> str:
    """Return a markdown section listing relevant skills for an agent."""
    resolver = get_resolver()
    cards = await resolver.search(tags=tags, env=env, limit=limit)
    return _format_cards(cards)


async def build_minimal_skill_cards_section(
    *,
    tags: list[str],
    env: str | None = None,
    limit: int = 8,
) -> str:
    """Return a compact skill section with name, description, and path only."""
    resolver = get_resolver()
    cards = await resolver.search(tags=tags, env=env, limit=limit)
    return _format_minimal_cards(cards)


def _format_cards(cards: Iterable[SkillCard]) -> str:
    lines: list[str] = []
    for c in cards:
        tags = ", ".join(str(t) for t in (c.tags or []) if str(t).strip())
        envs = ", ".join(str(e) for e in (c.env_list or []) if str(e).strip())

        line = f"- {c.name} ({c.skill_id})"
        if c.version:
            line += f" v{c.version}"
        if c.description:
            line += f": {c.description}"
        if tags:
            line += f" [tags: {tags}]"
        if envs:
            line += f" [env: {envs}]"
        if c.skill_path:
            line += f" [path: {c.skill_path}]"
        elif c.locator_path:
            line += f" [path: {c.locator_path}]"

        lines.append(line)

    if not lines:
        return ""

    return "\n\n## Skills\n\n" + "\n".join(lines) + "\n"


def _format_minimal_cards(cards: Iterable[SkillCard]) -> str:
    blocks: list[str] = []
    for c in cards:
        base_name = ""
        raw_path = str(c.skill_path or c.locator_path or "").strip().rstrip("/")
        if raw_path:
            base_name = raw_path.split("/")[-1]
        if not base_name:
            base_name = str(c.skill_id or c.name or "skill").strip()

        # Point to sandbox-local skills mount exposed by shared backend.
        md_path = f"/skills/{base_name}/SKILL.md"
        description = (
            c.description or "Use this skill when relevant to the task."
        ).strip()

        block = (
            f"### {c.name}\n"
            f"**When to use**: {description}\n"
            f"**Skill path**: `{md_path}`"
        )
        blocks.append(block)

    if not blocks:
        return ""

    return "\n\n## Skills\n\n" + "\n\n".join(blocks) + "\n"
