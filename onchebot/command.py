from dataclasses import dataclass
from typing import Any, Callable

from onchebot.models import Message

CommandFunction = Callable[[Message, list[str]], Any]


@dataclass
class Command:
    cmd: str
    func: CommandFunction
