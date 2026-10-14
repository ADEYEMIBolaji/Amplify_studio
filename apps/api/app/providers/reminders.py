"""ReminderProvider — FR-027 (decision D-06: email first, console-logged in dev)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ReminderContent:
    to_email: str
    platform: str
    caption: str
    download_url: str | None
    mark_published_url: str


class ReminderProvider(ABC):
    @abstractmethod
    async def send(self, content: ReminderContent) -> None: ...


class ConsoleReminderProvider(ReminderProvider):
    """D-06 default for development: logs to the console instead of sending email."""

    async def send(self, content: ReminderContent) -> None:
        print(
            "\n--- Publishing reminder ---\n"
            f"To: {content.to_email}\n"
            f"Platform: {content.platform}\n"
            f"Caption: {content.caption}\n"
            f"Download: {content.download_url or '(no export attached yet)'}\n"
            f"Mark published: {content.mark_published_url}\n"
            "---------------------------\n"
        )


def get_reminder_provider() -> ReminderProvider:
    from app.config import get_settings

    settings = get_settings()
    if settings.reminder_provider == "console":
        return ConsoleReminderProvider()
    raise NotImplementedError(
        f"Reminder provider '{settings.reminder_provider}' is not configured yet (D-06)."
    )
