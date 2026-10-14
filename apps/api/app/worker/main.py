"""Background worker entry point.

Stub for Week 1 — the queue consumer (transcription, FFmpeg rendering, AI
jobs) is built starting Week 3 per docs/plan.md. Running this now just
confirms the container wiring works end to end.
"""

import time


def main() -> None:
    print("Amplify Studio worker: no jobs to process yet (ships Week 3). Idling.")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
