"""LLMProvider interface — FR-004, FR-020, FR-022.

Real provider choice is an open decision (D-04); every call site depends on
this interface, not a concrete SDK, so swapping providers later touches only
`app/providers/*_llm.py` and the DI wiring in the routers.

Non-negotiable: generated text may cite scripture only as {{Book Ch:V}}
placeholders, never quoted verse text (FR-004 verse-text rule, FR-023).
Providers must honour this in what they generate; `app/services/scripture.py`
is the server-side backstop that validates it regardless.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.db.models import BrandProfile

SCRIPT_SECTIONS = ("hook", "biblical_context", "main_teaching", "practical_application", "closing_cta")


@dataclass
class ScriptDraft:
    sections: dict[str, str]  # keys are SCRIPT_SECTIONS
    model_id: str
    prompt_version: str


@dataclass
class HookDraft:
    text: str
    hook_type: str  # question | bold_claim | story | scripture_first | other


@dataclass
class HooksDraft:
    hooks: list[HookDraft]
    model_id: str
    prompt_version: str


@dataclass
class SectionDraft:
    text: str
    model_id: str
    prompt_version: str


@dataclass
class CaptionDraft:
    caption: str
    hashtags: list[str]
    cta: str
    model_id: str
    prompt_version: str


class LLMProvider(ABC):
    @abstractmethod
    async def generate_script(
        self,
        *,
        topic: str,
        audience: str | None,
        target_duration_seconds: int | None,
        brand_profile: BrandProfile,
        hook_text: str | None,
    ) -> ScriptDraft: ...

    @abstractmethod
    async def generate_hooks(
        self,
        *,
        topic: str,
        brand_profile: BrandProfile,
        count: int = 3,
    ) -> HooksDraft: ...

    @abstractmethod
    async def regenerate_section(
        self,
        *,
        section: str,
        topic: str,
        brand_profile: BrandProfile,
        other_sections: dict[str, str],
    ) -> SectionDraft: ...

    @abstractmethod
    async def generate_caption(
        self,
        *,
        platform: str,
        topic: str,
        script_sections: dict[str, str],
        brand_profile: BrandProfile,
    ) -> CaptionDraft: ...
