"""Deterministic fake LLM for local dev and tests (D-04 is still open —
no real provider chosen). Never emits quoted verse text, only {{Book Ch:V}}
placeholders, so it exercises the same validation path a real provider
output would have to pass (app/services/scripture.py).
"""

import hashlib

from app.db.models import BrandProfile
from app.providers.llm import CaptionDraft, HookDraft, HooksDraft, LLMProvider, ScriptDraft, SectionDraft

MODEL_ID = "fake-llm-v1"
PROMPT_VERSION = "2026-10-script-v1"

_REFERENCE_POOL = [
    "John 3:16",
    "Romans 8:28",
    "Philippians 4:13",
    "Psalm 23:1",
    "Jeremiah 29:11",
    "Matthew 6:33",
    "Isaiah 41:10",
    "Proverbs 3:5",
    "Joshua 1:9",
    "1 Corinthians 13:4",
]

_HOOK_TEMPLATES = [
    ("question", "Have you ever wondered what {topic} really means when life gets hard?"),
    ("bold_claim", "{topic} is not optional for the Christian life — here's why."),
    ("story", "Let me tell you about the day I almost gave up on {topic}."),
]


def _pick_reference(seed: str) -> str:
    index = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(_REFERENCE_POOL)
    return _REFERENCE_POOL[index]


class FakeLLMProvider(LLMProvider):
    async def generate_script(
        self,
        *,
        topic: str,
        audience: str | None,
        target_duration_seconds: int | None,
        brand_profile: BrandProfile,
        hook_text: str | None,
    ) -> ScriptDraft:
        reference = _pick_reference(topic)
        tone = brand_profile.tone or "warm and direct"
        audience_phrase = f" for {audience}" if audience else ""

        sections = {
            "hook": hook_text or f"Have you ever wondered what {topic} really means?",
            "biblical_context": (
                f"Scripture speaks directly to {topic}. As it says in {{{{{reference}}}}}, "
                "God has not left us without guidance here."
            ),
            "main_teaching": (
                f"In a {tone} way, here's the heart of it{audience_phrase}: {topic} is something "
                "God invites us into, not something we achieve alone."
            ),
            "practical_application": (
                f"This week, take one honest step toward {topic} — write it down, pray about it, "
                "or tell someone you trust."
            ),
            "closing_cta": (
                "If this spoke to you, follow for more and share it with someone who needs it today."
            ),
        }

        return ScriptDraft(sections=sections, model_id=MODEL_ID, prompt_version=PROMPT_VERSION)

    async def generate_hooks(
        self,
        *,
        topic: str,
        brand_profile: BrandProfile,
        count: int = 3,
    ) -> HooksDraft:
        hooks = [
            HookDraft(text=template.format(topic=topic), hook_type=hook_type)
            for hook_type, template in _HOOK_TEMPLATES[:count]
        ]
        return HooksDraft(hooks=hooks, model_id=MODEL_ID, prompt_version=PROMPT_VERSION)

    async def regenerate_section(
        self,
        *,
        section: str,
        topic: str,
        brand_profile: BrandProfile,
        other_sections: dict[str, str],
    ) -> SectionDraft:
        reference = _pick_reference(topic + section)
        text = {
            "hook": f"Here's something about {topic} that might surprise you.",
            "biblical_context": (
                f"As {{{{{reference}}}}} reminds us, this isn't a new struggle for God's people."
            ),
            "main_teaching": (
                f"Let's go deeper on {topic}: it starts with being honest about where you are."
            ),
            "practical_application": (
                f"Try this: spend five minutes today reflecting on {topic} before you pick up your phone."
            ),
            "closing_cta": "Save this post and come back to it when you need the reminder.",
        }.get(section, f"Here's more on {topic}.")

        return SectionDraft(text=text, model_id=MODEL_ID, prompt_version=PROMPT_VERSION)

    async def generate_caption(
        self,
        *,
        platform: str,
        topic: str,
        script_sections: dict[str, str],
        brand_profile: BrandProfile,
    ) -> CaptionDraft:
        hook_text = script_sections.get("hook", f"Let's talk about {topic}.")
        cta_text = script_sections.get("closing_cta", "Follow for more.")

        platform_captions = {
            "instagram": f"{hook_text}\n\n{topic} isn't always easy — but we don't walk through it alone.",
            "tiktok": f"{hook_text} 👀 Here's what I mean about {topic}.",
            "facebook": f"{hook_text}\n\nA short word on {topic} for anyone who needs it today.",
            "x": f"{hook_text[:200]} On {topic}:",
        }
        caption = platform_captions.get(platform, hook_text)

        base_tags = ["faith", "christian", topic.lower().replace(" ", "")]
        hashtags = [f"#{tag}" for tag in base_tags if tag]

        return CaptionDraft(
            caption=caption, hashtags=hashtags, cta=cta_text, model_id=MODEL_ID, prompt_version=PROMPT_VERSION
        )
