from typing import Any, Callable

from onchebot.command import Command
from onchebot.task import Task


class BotModule:
    def __init__(self):
        from onchebot.bot import Bot
        from onchebot.models import Message

        self.commands: list[Command] = []
        self.tasks: list[Task] = []
        self.default_state: dict[str, Any] = {}
        self.on_message_fn: Callable[[Message], Any] | None = None
        self.bot: Bot | None = None

    def init(self, bot):
        self.commands = (
            self.commands if hasattr(self, "commands") and self.commands else []
        )
        self.tasks = self.tasks if hasattr(self, "tasks") and self.tasks else []
        self.default_state = (
            self.default_state
            if hasattr(self, "default_state") and self.default_state
            else {}
        )
        self.on_message_fn = (
            self.on_message_fn
            if hasattr(self, "on_message_fn") and self.on_message_fn
            else None
        )
        self.bot = bot
