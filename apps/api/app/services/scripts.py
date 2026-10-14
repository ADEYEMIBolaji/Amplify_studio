"""Script version helpers — FR-004, FR-005.

sections_json on a script_versions row looks like:
    {"hook": {"text": "...", "source": "ai"}, "biblical_context": {...}, ...}

Per-section provenance (not just a version-level source) is what lets
"never overwrite manual edits without confirmation" be enforced section by
section, and lets a version's rollup `source` (ai|manual|mixed) be derived
rather than tracked separately.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ScriptVersion
from app.providers.llm import SCRIPT_SECTIONS


def rollup_source(sections: dict[str, dict]) -> str:
    sources = {section["source"] for section in sections.values()}
    if sources == {"ai"}:
        return "ai"
    if sources == {"manual"}:
        return "manual"
    return "mixed"


def word_count(sections: dict[str, dict]) -> int:
    return sum(len(section["text"].split()) for section in sections.values())


def estimate_duration_seconds(sections: dict[str, dict], wpm: int) -> float:
    if wpm <= 0:
        return 0.0
    return round(word_count(sections) / wpm * 60, 1)


async def next_version_no(db: AsyncSession, project_id: uuid.UUID) -> int:
    result = await db.execute(
        select(ScriptVersion.version_no)
        .where(ScriptVersion.project_id == project_id)
        .order_by(ScriptVersion.version_no.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    return (latest or 0) + 1


async def get_latest_version(db: AsyncSession, project_id: uuid.UUID) -> ScriptVersion | None:
    result = await db.execute(
        select(ScriptVersion)
        .where(ScriptVersion.project_id == project_id)
        .order_by(ScriptVersion.version_no.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def empty_sections() -> dict[str, dict]:
    return {section: {"text": "", "source": "ai"} for section in SCRIPT_SECTIONS}
