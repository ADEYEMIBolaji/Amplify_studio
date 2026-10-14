"""Scripture placeholder handling — FR-003, FR-004 (verse-text rule), FR-023.

Non-negotiable: AI output may cite scripture only as {{Book Ch:V}}
placeholders. This module (a) rejects AI output that quotes verse text
directly, (b) turns placeholders into scripture_references rows so they can
be verified, and (c) expands placeholders to real text only from the
allowlisted translations table — never from an assumed-public-domain source.
"""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ScriptureReference
from app.errors import BadRequestError
from app.providers.verse_data import all_web_verse_texts, get_web_verse

PLACEHOLDER_PATTERN = re.compile(r"\{\{([^{}]+)\}\}")
REFERENCE_PATTERN = re.compile(r"^(.+?)\s+(\d+):(\d+)(?:-(\d+))?$")


def find_placeholders(text: str) -> list[str]:
    return PLACEHOLDER_PATTERN.findall(text)


def parse_reference(reference: str) -> tuple[str, int, int, int | None]:
    match = REFERENCE_PATTERN.match(reference.strip())
    if not match:
        raise BadRequestError(f"'{reference}' is not a recognised 'Book Chapter:Verse' reference.")
    book, chapter, verse_start, verse_end = match.groups()
    return book.strip(), int(chapter), int(verse_start), int(verse_end) if verse_end else None


def validate_no_quoted_verse_text(text: str) -> None:
    """Rejects AI output that quotes a known verse verbatim instead of citing
    it as a {{Book Ch:V}} placeholder (FR-004 verse-text rule)."""
    lowered = text.lower()
    for verse_text in all_web_verse_texts():
        needle = verse_text.strip().lower()
        if len(needle) > 15 and needle in lowered:
            raise BadRequestError(
                "Generated text quotes scripture directly — only {{Book Ch:V}} placeholders are allowed.",
                code="verse_text_not_allowed",
            )


def validate_sections(sections: dict[str, str]) -> None:
    for text in sections.values():
        validate_no_quoted_verse_text(text)


async def sync_references_from_sections(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    sections: dict[str, str],
    default_translation: str,
) -> list[ScriptureReference]:
    """Ensures every {{Book Ch:V}} placeholder in the given sections has a
    scripture_references row (source=ai), so it can be reviewed and verified."""
    references_found = {ref for text in sections.values() for ref in find_placeholders(text)}
    synced: list[ScriptureReference] = []

    for reference in references_found:
        result = await db.execute(
            select(ScriptureReference).where(
                ScriptureReference.project_id == project_id,
                ScriptureReference.reference == reference,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            synced.append(existing)
            continue

        book, chapter, verse_start, verse_end = parse_reference(reference)
        row = ScriptureReference(
            project_id=project_id,
            book=book,
            chapter=chapter,
            verse_start=verse_start,
            verse_end=verse_end,
            reference=reference,
            translation=default_translation,
            source="ai",
        )
        db.add(row)
        synced.append(row)

    await db.flush()
    return synced


def expand_reference(ref: ScriptureReference) -> dict:
    """Returns the expanded-text payload for one reference, from the
    allowlisted translation source only (FR-023)."""
    if ref.pasted_text:
        return {"reference": ref.reference, "text": ref.pasted_text, "translation": "Owner-supplied"}

    if ref.translation == "WEB":
        text = get_web_verse(ref.reference)
        if text:
            return {"reference": ref.reference, "text": text, "translation": "WEB"}

    return {"reference": ref.reference, "text": None, "translation": ref.translation, "unavailable": True}


def expand_placeholders_in_text(text: str, references: dict[str, ScriptureReference]) -> str:
    def _replace(match: re.Match) -> str:
        reference = match.group(1)
        ref = references.get(reference)
        if ref is None:
            return "[Unavailable]"
        expanded = expand_reference(ref)
        if expanded.get("unavailable"):
            return "[Unavailable — add Owner-pasted text in Settings]"
        return f"{expanded['text']} ({expanded['translation']})"

    return PLACEHOLDER_PATTERN.sub(_replace, text)
