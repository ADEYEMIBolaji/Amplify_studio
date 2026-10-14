from functools import lru_cache

from app.config import get_settings
from app.providers.fake_llm import FakeLLMProvider
from app.providers.llm import LLMProvider

settings = get_settings()


@lru_cache
def get_llm_provider() -> LLMProvider:
    # D-04 is still open — no real provider chosen yet. Every call site
    # depends on LLMProvider, so wiring a real one later is a one-line change
    # here, not a refactor of callers.
    if settings.llm_provider == "fake":
        return FakeLLMProvider()
    raise NotImplementedError(f"LLM provider '{settings.llm_provider}' is not configured yet (D-04).")
