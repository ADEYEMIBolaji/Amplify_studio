"""Background worker — polls for `media_jobs` left `pending`.

The API processes a job inline right after enqueueing it (so the fake
providers feel instant for the single-user pilot); this loop exists to pick
up anything left pending after a crash or a real (slow) provider timing out
mid-request — that's the actual point of tracking status/retry_count in the
DB rather than only awaiting the call directly. AI jobs (ai_jobs) don't need
this: FR-004/022 calls are synchronous request/response today.
"""

import asyncio

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models import MediaJob
from app.services.media_jobs import process_job

POLL_INTERVAL_SECONDS = 5


async def run_once() -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(MediaJob).where(MediaJob.status == "pending"))
        jobs = list(result.scalars().all())
        for job in jobs:
            await process_job(db, job)
        await db.commit()
        return len(jobs)


async def main() -> None:
    print("Amplify Studio worker: polling media_jobs every "
          f"{POLL_INTERVAL_SECONDS}s for pending transcription/render/normalize jobs.")
    while True:
        processed = await run_once()
        if processed:
            print(f"Worker: processed {processed} job(s).")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
