import json
import logging
import traceback
from copy import deepcopy
from typing import IO, Any, Callable, Type, TypeVar

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger

import onchebot.metrics as metrics
from onchebot.bot_module import BotModule
from onchebot.command import Command, CommandFunction
from onchebot.models import Message, User
from onchebot.onche import NotLoggedInError, Onche
from onchebot.redis_client import RedisLock, redis
from onchebot.task import Task

logger = logging.getLogger("bot")

OnMessageFunction = Callable[[Message], Any]


T = TypeVar("T", bound=BotModule)


class Bot:
    def __init__(
        self,
        id: str,
        user: User,
        topic_id: int,
        modules: list[T] | None = None,
        default_state: dict[str, Any] | None = None,
        msg_time_threshold: int = 30 * 60,
        prefix: str | None = None,
    ) -> None:
        self.id: str = id
        self.topic_id: int = topic_id
        self.on_message_fn: OnMessageFunction | None = None
        self.commands: list[Command] = []
        self.task_fns: list[Task] = []
        self.default_config: dict[str, Any] = {}
        self.default_state: dict[str, Any] = default_state if default_state else {}
        self.config: dict[str, Any] = {}
        self.state: dict[str, Any] = deepcopy(default_state) if default_state else {}
        self.enabled: bool = True
        self.tasks: list[Job] = []
        self.tasks_created: bool = False
        self.modules = modules if modules else []
        self.user: User = user
        self.onche = Onche(user.username, user.password)
        self.msg_time_threshold = msg_time_threshold
        self.prefix = prefix
        for module in self.modules:
            module.init(bot=self)
        self._set_state(self.state)

    def get_module(self, module_type: type[T]) -> T:
        return next(
            module for module in self.modules if isinstance(module, module_type)
        )

    def on_message(self):
        def decorator(func: OnMessageFunction):
            self.on_message_fn = func
            return func

        return decorator

    def add_command(self, command_name: str, func: CommandFunction):
        self.commands.append(Command(cmd=command_name, func=func))

    def command(self, command_name: str):
        def decorator(func: CommandFunction):
            self.commands.append(Command(cmd=command_name, func=func))
            return func

        return decorator

    def task(self, trigger: BaseTrigger):
        def decorator(func: Callable[[], Any]):
            async def wrapper():
                await func()
                await self._save()

            self.task_fns.append(Task(func=wrapper, trigger=trigger))
            return func

        return decorator

    def _set_state(self, state: dict[str, Any] = {}):
        modules_default_state = {}
        for d in [m.default_state for m in self.modules]:
            modules_default_state.update(d)

        self.state = {**modules_default_state, **self.default_state, **state}

    def set_state(self, key: str, value: Any):
        self.state[key] = value

    def get_state(self, key: str | None = None) -> Any:
        if key:
            return self.state.get(key, None)
        return self.state

    async def _save(self) -> None:
        await redis().r.hset(
            f"onchebot:bots:{self.id}",
            mapping={
                "state": json.dumps(self.state),
            },
        )

    def get_task_fns(self):
        task_fns = [*self.task_fns.copy()]
        for mod in self.modules:
            for t in mod.tasks:
                task_fns.append(t)
        return task_fns

    async def create_tasks(self, scheduler: AsyncIOScheduler) -> None:
        self.tasks_created = True
        for task in self.get_task_fns():
            self.tasks.append(scheduler.add_job(task.func, task.trigger))

    async def run_task_once(self, task_func_name: str) -> None:
        task_func = next(
            l.func for l in self.get_task_fns() if l.func.__name__ == task_func_name
        )
        await task_func()
        await self._save()

    def _cancel_tasks(self) -> None:
        for task in self.tasks:
            task.remove()
        self.tasks = []
        self.tasks_created = False

    async def consume_msg(self, msg: Message) -> bool:
        if self.on_message_fn:
            await self.on_message_fn(msg)

        for module in self.modules:
            if module.on_message_fn:
                await module.on_message_fn(msg)

        content = msg.content.split()
        unavailable_commands: list[str] = []
        modules_commands = [m.commands for m in self.modules]
        m_commands = [item for sublist in modules_commands for item in sublist]
        command_list = [*self.commands, *m_commands]

        def cmd_to_str(cmd: str):
            return "/" + ((self.prefix + "/") if self.prefix else "") + cmd

        for word in content:
            for command in command_list:
                if (
                    cmd_to_str(command.cmd) == word.strip()
                    and command.cmd not in unavailable_commands
                ):
                    unavailable_commands.append(command.cmd)
                    args = []
                    try:
                        lines = msg.content.splitlines()
                        line = next(
                            l
                            for l in lines
                            if cmd_to_str(command.cmd).lower() in l.lower()
                        )
                        words_lower = line.lower().split()
                        words = line.split()
                        cmd_i = words_lower.index(cmd_to_str(command.cmd).lower())
                        args = words[cmd_i + 1 :]
                    except Exception:
                        traceback.format_exc()
                        pass
                    logger.info(f"COMMAND FOUND: {cmd_to_str(command.cmd)} from {msg}")
                    await command.func(msg, args)
                    await self._save()
                    return True
        await self._save()
        return False

    async def post_message(
        self,
        content: str,
        topic_id: int | None = None,
        answer_to: Message | None = None,
        _retry: int = 0,
    ) -> int:
        try:
            t = (
                topic_id
                if topic_id
                else (answer_to.topic_id if answer_to else self.topic_id)
            )
            if not t:
                raise Exception("Undefined topic in post_message")
            res = await self.onche.post_message(t, content, answer_to)
            metrics.posted_msg_counter.set(
                await redis().r.incrby(
                    name="onchebot:metadata:messages:posted_total", amount=1
                )
            )
            return res
        except NotLoggedInError:
            max_retry = 5
            if _retry >= max_retry:
                raise Exception(
                    f"Could not logged after {_retry} retries, aborting post_message"
                )

            logger.info("Not logged in, will retry post_message after log in")
            await self.login()
            return await self.post_message(content, topic_id, answer_to, _retry + 1)

    async def login(self):
        lock = RedisLock(f"onchebot:users:{self.user.username}:logging_in")
        await lock.acquire_lock()

        # Check if another bot logged in while we acquired the lock
        cookie2 = await redis().get_user_cookie(self.user.username)
        if cookie2 and self.user.cookie != cookie2:
            self.user.cookie = cookie2
            self.onche.cookie = cookie2
            return

        # If not, log in
        cookie = await self.onche.login()
        if not cookie:
            return
        self.user.cookie = cookie
        await redis().set_user_cookie(self.user.username, cookie)

        await lock.release_lock()

    async def upload_image(
        self,
        data: IO[Any] | bytes | str,
        filename: str,
        content_type: str,
        _retry: int = 0,
    ) -> str | None:
        try:
            return await self.onche.upload_image(data, filename, content_type)
        except NotLoggedInError:
            max_retry = 3
            if _retry >= max_retry:
                raise Exception(
                    f"Could not logged after {_retry} retries, aborting post_message"
                )

            logger.info(
                "Not logged in (400 http code from image upload), will retry upload_image after log in"
            )
            await self.login()

            return await self.upload_image(data, filename, content_type, _retry + 1)
