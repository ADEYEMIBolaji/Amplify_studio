"""Calendar/publishing helpers — FR-011, FR-012, FR-021 (posting_slot tag).

Scheduling takes the Owner's wall-clock local time + IANA timezone and
converts to UTC via `zoneinfo`, which is what makes the BST/GMT clock
change (AT-11) come out correctly — the same local wall-clock time maps to
a different UTC instant on either side of the transition, and zoneinfo
handles that without any special-casing here.
"""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.errors import BadRequestError

_EXTERNAL_ID_PATTERNS = {
    "instagram": re.compile(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)"),
    "tiktok": re.compile(r"tiktok\.com/@[\w.]+/video/(\d+)"),
    "facebook": re.compile(r"facebook\.com/[^/]+/(?:videos|reel)/(\d+)"),
    "x": re.compile(r"(?:twitter|x)\.com/\w+/status/(\d+)"),
}


def parse_external_post_id(platform: str, url: str) -> str | None:
    pattern = _EXTERNAL_ID_PATTERNS.get(platform)
    if pattern is None:
        return None
    match = pattern.search(url)
    return match.group(1) if match else None


def local_to_utc(local_naive_iso: str, timezone: str) -> datetime:
    try:
        naive = datetime.fromisoformat(local_naive_iso)
    except ValueError as exc:
        raise BadRequestError(f"'{local_naive_iso}' is not a valid ISO datetime.") from exc
    if naive.tzinfo is not None:
        raise BadRequestError(
            "scheduled_at_local must not include a timezone offset — pass 'timezone' separately."
        )

    try:
        zone = ZoneInfo(timezone)
    except Exception as exc:  # noqa: BLE001
        raise BadRequestError(f"'{timezone}' is not a recognised IANA timezone.") from exc

    localized = naive.replace(tzinfo=zone)
    return localized.astimezone(UTC)


def compute_posting_slot(utc_time: datetime, timezone: str) -> str:
    local_hour = utc_time.astimezone(ZoneInfo(timezone)).hour
    if local_hour < 12:
        return "morning"
    if local_hour < 17:
        return "midday"
    return "evening"
