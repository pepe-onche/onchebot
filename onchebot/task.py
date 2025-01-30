from dataclasses import dataclass
from typing import Any, Callable

from apscheduler.triggers.base import BaseTrigger


@dataclass
class Task:
    trigger: BaseTrigger
    func: Callable[[], Any]
