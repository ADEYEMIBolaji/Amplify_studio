"""Reminder scheduling and delivery — FR-027.

Reminders are created when a post gets a scheduled_at; one at the scheduled
time and one `reminder_lead_minutes` before (both, since FR-027 says the
lead-time one is optional — we just always do both locally). Publishing a
post deletes its still-pending reminders outright, which is what "reminders
stop once the post is marked published" means in practice — there is
nothing left to fire.
"""

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import MediaAsset, Reminder, SocialPost, User, Workspace
from app.providers.reminders import ReminderContent, get_reminder_provider
from app.providers.storage import get_storage_provider


async def schedule_reminders(db: AsyncSession, post: SocialPost) -> None:
    await db.execute(delete(Reminder).where(Reminder.social_post_id == post.id))
    if post.scheduled_at is None:
        return

    settings = get_settings()
    send_times = {post.scheduled_at}
    lead_time = post.scheduled_at - timedelta(minutes=settings.reminder_lead_minutes)
    send_times.add(lead_time)

    for send_at in sorted(send_times):
        db.add(Reminder(social_post_id=post.id, channel="email", send_at=send_at))
    await db.flush()


async def cancel_reminders(db: AsyncSession, post_id) -> None:
    await db.execute(delete(Reminder).where(Reminder.social_post_id == post_id))


async def send_due_reminders(db: AsyncSession, now: datetime) -> int:
    settings = get_settings()
    storage = get_storage_provider()
    provider = get_reminder_provider()

    result = await db.execute(select(Reminder).where(Reminder.sent_at.is_(None), Reminder.send_at <= now))
    due = list(result.scalars().all())

    sent = 0
    for reminder in due:
        post = await db.get(SocialPost, reminder.social_post_id)
        if post is None or post.status == "published":
            reminder.sent_at = now
            continue

        workspace = await db.get(Workspace, post.workspace_id)
        owner = await db.get(User, workspace.owner_id) if workspace else None

        download_url = None
        if post.media_asset_id:
            asset = await db.get(MediaAsset, post.media_asset_id)
            if asset and asset.status == "ready":
                download_url = storage.signed_url(asset.object_key, settings.signed_url_expiry_seconds)

        await provider.send(
            ReminderContent(
                to_email=owner.email if owner else "unknown@example.com",
                platform=post.platform,
                caption=post.caption or "",
                download_url=download_url,
                mark_published_url=f"{settings.frontend_base_url}/calendar?postId={post.id}",
            )
        )
        reminder.sent_at = now
        sent += 1

    return sent
