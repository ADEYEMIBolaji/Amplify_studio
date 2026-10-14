"""Platform constraint checks — FR-026. Seed values mirror
supabase/migrations/0004_platform_limits.sql exactly (that migration is the
source of truth for a real Supabase DB; SQLite test/dev DBs don't run SQL
migrations, so `ensure_seeded` inserts the same rows the first time).
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BrandProfile, MediaAsset, PlatformLimit
from app.errors import BadRequestError, ConflictError

SEED_ROWS = [
    dict(
        platform="instagram", caption_max_chars=2200, caption_max_chars_premium=None,
        duration_max_seconds=180, duration_max_seconds_premium=None, hashtag_max_count=30,
        notes="Reels. Seeded from FRD FR-026 table; verify before launch.",
    ),
    dict(
        platform="tiktok", caption_max_chars=4000, caption_max_chars_premium=None,
        duration_max_seconds=600, duration_max_seconds_premium=None, hashtag_max_count=30,
        notes="Seeded from FRD FR-026 table; verify before launch.",
    ),
    dict(
        platform="facebook", caption_max_chars=2200, caption_max_chars_premium=None,
        duration_max_seconds=90, duration_max_seconds_premium=None, hashtag_max_count=30,
        notes='Reels limit changes frequently — FRD marks this "configurable; verify". Placeholder.',
    ),
    dict(
        platform="x", caption_max_chars=280, caption_max_chars_premium=25000,
        duration_max_seconds=140, duration_max_seconds_premium=10800, hashtag_max_count=None,
        notes="2:20 (140s) non-Premium per FRD; Premium figures are placeholders pending verification.",
    ),
]


async def ensure_seeded(db: AsyncSession) -> None:
    count = (await db.execute(select(func.count()).select_from(PlatformLimit))).scalar_one()
    if count > 0:
        return
    for row in SEED_ROWS:
        db.add(PlatformLimit(**row))
    await db.flush()


@dataclass
class EffectiveLimits:
    platform: str
    caption_max_chars: int
    duration_max_seconds: int
    hashtag_max_count: int | None
    aspect_ratio: str
    is_premium: bool


async def get_effective_limits(
    db: AsyncSession, platform: str, brand_profile: BrandProfile
) -> EffectiveLimits:
    await ensure_seeded(db)
    result = await db.execute(select(PlatformLimit).where(PlatformLimit.platform == platform))
    row = result.scalar_one_or_none()
    if row is None:
        raise ConflictError(f"No platform configuration found for '{platform}'.")

    is_premium = bool(brand_profile.platform_flags_json.get(f"{platform}_premium", False))
    caption_max = (
        row.caption_max_chars_premium
        if is_premium and row.caption_max_chars_premium
        else row.caption_max_chars
    )
    duration_max = (
        row.duration_max_seconds_premium
        if is_premium and row.duration_max_seconds_premium
        else row.duration_max_seconds
    )

    return EffectiveLimits(
        platform=platform,
        caption_max_chars=caption_max,
        duration_max_seconds=duration_max,
        hashtag_max_count=row.hashtag_max_count,
        aspect_ratio=row.aspect_ratio,
        is_premium=is_premium,
    )


def check_caption_against_limits(caption: str | None, hashtags: list[str], limits: EffectiveLimits) -> None:
    """FR-010: enforce configured character and hashtag limits per platform."""
    caption_len = len(caption or "")
    if caption_len > limits.caption_max_chars:
        premium_hint = (
            " (enable the Premium flag in Settings for a higher limit)"
            if limits.platform == "x" and not limits.is_premium
            else ""
        )
        raise BadRequestError(
            f"{limits.platform.title()} captions are limited to {limits.caption_max_chars} characters"
            f"{premium_hint}; this one is {caption_len}.",
            code="caption_too_long",
        )

    if limits.hashtag_max_count is not None and len(hashtags) > limits.hashtag_max_count:
        raise BadRequestError(
            f"{limits.platform.title()} allows at most {limits.hashtag_max_count} hashtags; "
            f"this post has {len(hashtags)}.",
            code="too_many_hashtags",
        )


def _format_duration(seconds: float) -> str:
    minutes, secs = divmod(round(seconds), 60)
    return f"{minutes}:{secs:02d}"


def check_media_against_limits(asset: MediaAsset, limits: EffectiveLimits) -> None:
    """FR-026: block attaching an export that fails duration/aspect checks,
    with a message naming the specific limit and the actual value."""
    if asset.duration_seconds and asset.duration_seconds > limits.duration_max_seconds:
        premium_note = " without the Premium flag" if limits.platform == "x" and not limits.is_premium else ""
        raise ConflictError(
            f"{limits.platform.title()} allows {_format_duration(limits.duration_max_seconds)}"
            f"{premium_note}; this video is {_format_duration(float(asset.duration_seconds))}.",
            code="platform_duration_exceeded",
        )

    if asset.width and asset.height:
        actual_ratio = asset.width / asset.height
        expected_w, expected_h = (int(x) for x in limits.aspect_ratio.split(":"))
        expected_ratio = expected_w / expected_h
        if abs(actual_ratio - expected_ratio) > 0.05:
            raise ConflictError(
                f"{limits.platform.title()} expects {limits.aspect_ratio} video; "
                f"this export is {asset.width}x{asset.height}.",
                code="platform_aspect_mismatch",
            )
