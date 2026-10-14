"""AT-12 (Reminders): a reminder is scheduled alongside a planned post and
sends at (or after) its scheduled time with a download link; marking the
post published stops any further reminders from firing (FR-027).
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import Reminder
from app.services.reminders import send_due_reminders
from tests.conftest import TestSessionLocal, make_user


async def _scheduled_post(client: AsyncClient) -> dict:
    project = (await client.post("/api/projects", json={"title": "Weekly word", "topic": "Joy"})).json()
    await client.post(f"/api/projects/{project['id']}/outline")
    posts = (
        await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": ["instagram"]})
    ).json()
    post = posts[0]
    await client.patch(
        f"/api/posts/{post['id']}",
        json={"scheduled_at_local": "2026-06-15T09:00:00", "timezone": "Europe/London"},
    )
    return {"project": project, "post": post}


async def test_scheduling_a_post_creates_reminders(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _scheduled_post(client)

    async with TestSessionLocal() as db:
        result = await db.execute(select(Reminder).where(Reminder.social_post_id == ctx["post"]["id"]))
        reminders = list(result.scalars().all())

    assert len(reminders) == 2  # on-time + the 30-minute lead reminder
    assert all(r.sent_at is None for r in reminders)


async def test_due_reminder_sends_and_marks_sent(client: AsyncClient, as_user, capsys):
    as_user(make_user())
    await _scheduled_post(client)

    # 09:00 Europe/London on 2026-06-15 (BST) is 08:00 UTC; well after that.
    now = datetime(2026, 6, 15, 9, 0, tzinfo=UTC)
    async with TestSessionLocal() as db:
        sent = await send_due_reminders(db, now)
        await db.commit()

    assert sent == 2
    captured = capsys.readouterr()
    assert "Publishing reminder" in captured.out

    async with TestSessionLocal() as db:
        result = await db.execute(select(Reminder))
        assert all(r.sent_at is not None for r in result.scalars().all())


async def test_reminder_not_due_yet_is_not_sent(client: AsyncClient, as_user):
    as_user(make_user())
    await _scheduled_post(client)

    now = datetime(2026, 6, 1, tzinfo=UTC)  # well before the scheduled time
    async with TestSessionLocal() as db:
        sent = await send_due_reminders(db, now)
        await db.commit()

    assert sent == 0


async def test_publishing_cancels_pending_reminders(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _scheduled_post(client)

    await client.post(
        f"/api/posts/{ctx['post']['id']}/publish",
        json={"external_url": "https://www.instagram.com/p/ABC123/"},
    )

    async with TestSessionLocal() as db:
        result = await db.execute(select(Reminder).where(Reminder.social_post_id == ctx["post"]["id"]))
        assert list(result.scalars().all()) == []

    # Even if the worker ran after publishing, there's nothing left to send.
    async with TestSessionLocal() as db:
        sent = await send_due_reminders(db, datetime.now(UTC) + timedelta(days=1))
    assert sent == 0
