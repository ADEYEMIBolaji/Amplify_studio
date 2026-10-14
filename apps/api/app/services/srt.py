"""SRT export — FR-009 (ships before burn-in per docs/plan.md)."""


def _timestamp(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_srt(segments: list[dict]) -> str:
    lines = []
    for i, segment in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{_timestamp(segment['start'])} --> {_timestamp(segment['end'])}")
        lines.append(segment["text"])
        lines.append("")
    return "\n".join(lines)
