from datetime import date
from ..plugin import Plugin


class CalendarPlugin(Plugin):
    name = "calendar"
    description = "Reports the local date without accessing a remote calendar account."
    version = "1.0.0"
    capabilities = ["Calendar"]

    def can_handle(self, command: str) -> bool:
        return command.strip().casefold() in {"calendar today", "today's calendar", "today calendar"}

    def execute(self, command: str) -> str:
        return f"Today is {date.today().isoformat()}. No external calendar account is connected."
