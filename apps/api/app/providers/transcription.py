"""TranscriptionProvider — FR-008. Real provider choice is open (D-03);
every call site depends on this interface, not a concrete SDK.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptDraft:
    segments: list[TranscriptSegment]
    language: str


class TranscriptionProvider(ABC):
    @abstractmethod
    async def transcribe(
        self, *, media_path: Path, duration_seconds: float, vocabulary: list[str]
    ) -> TranscriptDraft: ...


class FakeTranscriptionProvider(TranscriptionProvider):
    """Deterministic fake for local dev/test — no real provider chosen yet (D-03)."""

    async def transcribe(
        self, *, media_path: Path, duration_seconds: float, vocabulary: list[str]
    ) -> TranscriptDraft:
        lines = [
            "Welcome back — today we're talking about something that matters.",
            "Let's look at what this means for us right now.",
            "Here's the one thing I want you to take away from this.",
        ]
        segment_length = max(duration_seconds / len(lines), 1.0)
        segments = [
            TranscriptSegment(
                start=round(i * segment_length, 1),
                end=round((i + 1) * segment_length, 1),
                text=line,
            )
            for i, line in enumerate(lines)
        ]
        return TranscriptDraft(segments=segments, language="en-GB")


def get_transcription_provider() -> TranscriptionProvider:
    from app.config import get_settings

    settings = get_settings()
    if settings.transcription_provider == "fake":
        return FakeTranscriptionProvider()
    raise NotImplementedError(
        f"Transcription provider '{settings.transcription_provider}' is not configured yet (D-03)."
    )
