"""Local WEB (World English Bible) sample — FR-023 (a): a public-domain
translation held locally. This is a small seeded set of commonly-cited
verses, not the full Bible — see docs/plan.md Week 2 notes. Expanding
coverage is a matter of adding entries to data/web_sample.json; the lookup
and licensing model are already in place.
"""

import json
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).parent / "data" / "web_sample.json"


@lru_cache
def _load() -> dict[str, str]:
    with _DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["verses"]


def get_web_verse(reference: str) -> str | None:
    """Returns WEB text for an exact reference string (e.g. 'John 3:16'), or None."""
    return _load().get(reference)


def all_web_verse_texts() -> list[str]:
    """Used by the verse-text validator to catch AI output that quotes a
    seeded verse verbatim instead of using a {{Book Ch:V}} placeholder."""
    return list(_load().values())
