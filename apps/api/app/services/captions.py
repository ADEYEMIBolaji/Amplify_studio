"""Burn-in caption layout — FR-009 (v1.1 additions), AT-03.

Turns reviewed transcript segments into an ASS (Advanced SubStation Alpha)
subtitle file that FFmpeg's `ass` filter (libass) burns into a 1080x1920
render. ASS rather than SRT + `force_style` because it lets us pin the exact
geometry FR-009 asks for:

- Style (font, size, colour, background box) comes from the brand profile's
  `subtitle_style_json`, validated by `SubtitleStyle`.
- Line breaking is done here, not by libass: at most `max_chars_per_line`
  characters per line (default 32) and `max_lines` lines per caption
  (default 2). A segment too long for one caption is split into several,
  with its time shared out in proportion to each caption's text length.
- Safe zone: captions are bottom-anchored (ASS alignment 2) with a vertical
  margin that keeps the whole box, padding included, clear of the bottom
  `safe_zone_bottom_pct` of the frame (default 20%), and a right margin
  clear of the right `safe_zone_right_pct` (default 12%). Text grows upwards
  from that line, so containment doesn't depend on how many lines a caption
  has. `caption_bounds` computes the box for tests and for the render result.

All of this is pure (no FFmpeg needed), so it's fully unit-tested even on
machines where only `FakeVideoProcessor` runs.
"""

import math
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field, model_validator

FRAME_WIDTH = 1080
FRAME_HEIGHT = 1920

# Rough average glyph width as a fraction of font size for a sans-serif face
# like DejaVu Sans — used only to reject styles whose longest allowed line
# couldn't fit between the margins. libass also wraps at the margins as a
# backstop (WrapStyle 0), so an underestimate can't push text out of the zone.
_AVG_CHAR_WIDTH_RATIO = 0.55
_LINE_HEIGHT_RATIO = 1.2

_HEX_COLOUR = r"^#[0-9A-Fa-f]{6}$"


class SubtitleStyle(BaseModel):
    """FR-009 subtitle style. Defaults are the FRD's (32 chars x 2 lines,
    safe zone clear of the bottom 20% / right 12%); every field is
    configurable from Settings."""

    # DejaVu Sans ships in the worker image (fonts-dejavu-core); libass falls
    # back via fontconfig if the Owner names a font that isn't installed.
    font_family: str = Field(default="DejaVu Sans", min_length=1, max_length=100)
    font_size: int = Field(default=48, ge=24, le=120)
    bold: bool = True
    text_colour: str = Field(default="#FFFFFF", pattern=_HEX_COLOUR)
    background_box: bool = True
    background_colour: str = Field(default="#000000", pattern=_HEX_COLOUR)
    background_opacity: float = Field(default=0.6, ge=0, le=1)
    max_chars_per_line: int = Field(default=32, ge=10, le=60)
    max_lines: int = Field(default=2, ge=1, le=3)
    safe_zone_bottom_pct: float = Field(default=20, ge=0, le=50)
    safe_zone_right_pct: float = Field(default=12, ge=0, le=40)
    safe_zone_left_pct: float = Field(default=6, ge=0, le=40)

    @model_validator(mode="after")
    def _longest_line_fits(self) -> "SubtitleStyle":
        available = safe_width_px(self)
        needed = self.max_chars_per_line * self.font_size * _AVG_CHAR_WIDTH_RATIO
        if needed > available:
            largest = math.floor(available / (self.max_chars_per_line * _AVG_CHAR_WIDTH_RATIO))
            raise ValueError(
                f"A {self.max_chars_per_line}-character line at font size {self.font_size} won't fit "
                f"inside the caption safe zone — use font size {largest} or smaller, or fewer "
                "characters per line."
            )
        return self


def safe_width_px(style: SubtitleStyle) -> float:
    return FRAME_WIDTH * (1 - (style.safe_zone_left_pct + style.safe_zone_right_pct) / 100)


def style_from_profile(raw: dict | None) -> SubtitleStyle:
    """Brand profiles created before FR-009 shipped have `{}` — defaults apply."""
    return SubtitleStyle.model_validate(raw or {})


def wrap_text(text: str, max_chars: int) -> list[str]:
    """Greedy word wrap to at most `max_chars` per line; a single word longer
    than the limit is hard-split rather than allowed to overflow."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        while len(word) > max_chars:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:max_chars])
            word = word[max_chars:]
        if not word:
            continue
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


@dataclass
class CaptionEvent:
    start: float
    end: float
    lines: list[str]


def build_caption_events(segments: list[dict], style: SubtitleStyle) -> list[CaptionEvent]:
    events: list[CaptionEvent] = []
    for segment in segments:
        start, end = float(segment["start"]), float(segment["end"])
        if end <= start:
            continue
        lines = wrap_text(str(segment.get("text", "")), style.max_chars_per_line)
        if not lines:
            continue

        chunks = [lines[i : i + style.max_lines] for i in range(0, len(lines), style.max_lines)]
        weights = [sum(len(line) for line in chunk) for chunk in chunks]
        total = sum(weights)
        cursor = start
        for i, (chunk, weight) in enumerate(zip(chunks, weights, strict=True)):
            # Last chunk ends exactly on the segment end, so rounding never
            # leaves a gap or overlaps the next segment.
            chunk_end = end if i == len(chunks) - 1 else cursor + (end - start) * weight / total
            events.append(CaptionEvent(start=cursor, end=chunk_end, lines=chunk))
            cursor = chunk_end
    return events


def _box_padding_px(style: SubtitleStyle) -> int:
    # With BorderStyle 3 libass draws the opaque box `Outline` pixels beyond
    # the text on every side.
    return max(round(style.font_size * 0.25), 4)


def _margins_px(style: SubtitleStyle) -> tuple[int, int, int]:
    padding = _box_padding_px(style)
    left = math.ceil(FRAME_WIDTH * style.safe_zone_left_pct / 100) + padding
    right = math.ceil(FRAME_WIDTH * style.safe_zone_right_pct / 100) + padding
    bottom = math.ceil(FRAME_HEIGHT * style.safe_zone_bottom_pct / 100) + padding
    return left, right, bottom


@dataclass
class CaptionBounds:
    left: float
    right: float
    top: float
    bottom: float


def caption_bounds(style: SubtitleStyle, line_count: int) -> CaptionBounds:
    """The outer box (background padding included) of a bottom-anchored
    caption with `line_count` lines, assuming the widest permitted line."""
    left_margin, right_margin, bottom_margin = _margins_px(style)
    padding = _box_padding_px(style)
    text_width = min(
        style.max_chars_per_line * style.font_size * _AVG_CHAR_WIDTH_RATIO,
        FRAME_WIDTH - left_margin - right_margin,
    )
    centre = left_margin + (FRAME_WIDTH - left_margin - right_margin) / 2
    text_height = line_count * style.font_size * _LINE_HEIGHT_RATIO
    bottom = FRAME_HEIGHT - bottom_margin + padding
    return CaptionBounds(
        left=centre - text_width / 2 - padding,
        right=centre + text_width / 2 + padding,
        top=bottom - text_height - 2 * padding,
        bottom=bottom,
    )


def safe_zone_px(style: SubtitleStyle) -> CaptionBounds:
    return CaptionBounds(
        left=FRAME_WIDTH * style.safe_zone_left_pct / 100,
        right=FRAME_WIDTH * (1 - style.safe_zone_right_pct / 100),
        top=0,
        bottom=FRAME_HEIGHT * (1 - style.safe_zone_bottom_pct / 100),
    )


def _ass_colour(hex_colour: str, opacity: float = 1.0) -> str:
    """#RRGGBB -> ASS &HAABBGGRR, where AA is transparency (00 = opaque)."""
    r, g, b = hex_colour[1:3], hex_colour[3:5], hex_colour[5:7]
    alpha = round((1 - opacity) * 255)
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ass_time(seconds: float) -> str:
    centis = round(seconds * 100)
    hours, rem = divmod(centis, 360_000)
    minutes, rem = divmod(rem, 6000)
    secs, cs = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _escape_ass_text(text: str) -> str:
    # `{...}` is an ASS override block and `\` starts an override tag; neither
    # should ever be interpreted from transcript text.
    text = text.replace("\\", "/")
    return re.sub(r"[{}]", lambda m: "(" if m.group() == "{" else ")", text)


def build_ass(segments: list[dict], style: SubtitleStyle) -> str:
    left, right, bottom = _margins_px(style)
    padding = _box_padding_px(style)
    if style.background_box:
        back = _ass_colour(style.background_colour, style.background_opacity)
        border_style, outline = 3, padding
        outline_colour = back  # BorderStyle 3 paints the box in OutlineColour
    else:
        border_style, outline, back = 1, 3, "&H80000000"
        outline_colour = "&H00000000"

    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {FRAME_WIDTH}",
            f"PlayResY: {FRAME_HEIGHT}",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
            "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,"
            f"{style.font_family},{style.font_size},{_ass_colour(style.text_colour)},&H000000FF,"
            f"{outline_colour},{back},{-1 if style.bold else 0},0,0,0,100,100,0,0,"
            f"{border_style},{outline},0,2,{left},{right},{bottom},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )
    dialogue = [
        f"Dialogue: 0,{_ass_time(e.start)},{_ass_time(e.end)},Default,,0,0,0,,"
        + r"\N".join(_escape_ass_text(line) for line in e.lines)
        for e in build_caption_events(segments, style)
    ]
    return header + "\n" + "\n".join(dialogue) + "\n"
