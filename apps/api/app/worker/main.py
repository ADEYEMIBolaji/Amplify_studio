"""Background worker — polls for `media_jobs` left `pending` and sends any
due publishing reminders (FR-027).

The API processes a media_jobs row inline right after enqueueing it (so the
fake providers feel instant for the single-user pilot); this loop exists to
pick up anything left pending after a crash or a real (slow) provider
timing out mid-request — that's the actual point of tracking
status/retry_count in the DB rather than only awaiting the call directly.
AI jobs (ai_jobs) don't need this: FR-004/022 calls are synchronous
request/response today. Reminders, by contrast, have no synchronous
trigger at all — this loop is their only delivery path.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models import MediaJob
from app.services.media_jobs import process_job
from app.services.reminders import send_due_reminders

POLL_INTERVAL_SECONDS = 5


async def run_once() -> tuple[int, int]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(MediaJob).where(MediaJob.status == "pending"))
        jobs = list(result.scalars().all())
        for job in jobs:
            await process_job(db, job)

        reminders_sent = await send_due_reminders(db, datetime.now(UTC))
        await db.commit()
        return len(jobs), reminders_sent


async def main() -> None:
    print(
        "Amplify Studio worker: polling media_jobs and due reminders every "
        f"{POLL_INTERVAL_SECONDS}s."
    )
    while True:
        jobs_processed, reminders_sent = await run_once()
        if jobs_processed:
            print(f"Worker: processed {jobs_processed} media job(s).")
        if reminders_sent:
            print(f"Worker: sent {reminders_sent} reminder(s).")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
