import asyncio
import logging
import traceback
from copy import deepcopy
from typing import IO, Any, Callable, TypeVar

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger
from tortoise.expressions import F

import onchebot.metrics as metrics
from onchebot.bot_module import BotModule
from onchebot.command import Command, CommandFunction
from onchebot.models import BotParams, Message, Metric, User
from onchebot.onche import NotLoggedInError, NotPostedError, Onche
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
        default_state: dict[str, Any],
        modules: list[BotModule],
        prefix: str | None,
        msg_time_threshold: int,
    ) -> None:
        self.id: str = id
        self.topic_id: int = topic_id
        self.user: User = user
        self.state: dict[str, Any] = deepcopy(default_state) if default_state else {}
        self.on_message_fn: OnMessageFunction | None = None
        self.commands: list[Command] = []
        self.task_fns: list[Task] = []
        self.default_config: dict[str, Any] = {}
        self.default_state: dict[str, Any] = default_state if default_state else {}
        self.tasks: list[Job] = []
        self.tasks_created: bool = False
        self.onche: Onche = Onche(user.username, user.password)
        self.msg_time_threshold: int = msg_time_threshold
        self.prefix: str | None = prefix
        self.modules: list[BotModule] = modules
        for module in self.modules:
            module.init(bot=self)
        self.refresh_state(self.state)
        self.params: BotParams | None = None

    async def fetch_params(self):
        self.params, _ = await BotParams.get_or_create(
            id=self.id, defaults={"state": self.state, "last_consumed_id": -1}
        )
        self.refresh_state(self.params.state)

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
                if self.params:
                    logger.info("saving params C")
                    self.params.state = self.state
                    await self.params.save()

            self.task_fns.append(Task(func=wrapper, trigger=trigger))
            return func

        return decorator

    def refresh_state(self, state: dict[str, Any] = {}):
        modules_default_state = {}
        for d in [m.default_state for m in self.modules]:
            modules_default_state.update(d)

        self.state = {**modules_default_state, **self.default_state, **state}

    def set_state(self, key: str, value: Any):
        self.state[key] = value

    def get_state(self, key: str | None = None) -> Any:  # pyright: ignore[reportAny]
        if key:
            return self.state.get(key, None)  # pyright: ignore[reportAny]
        return self.state

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
        if self.params:
            logger.info("saving params D")
            self.params.state = self.state
            await self.params.save()

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

        if self.params:
            self.params.last_consumed_id = msg.id

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

                    if self.params:
                        logger.info("saving params A")
                        self.refresh_state(self.state)
                        self.params.state = self.state
                        await self.params.save()

                    return True

        if self.params:
            logger.info("saving params B")
            self.refresh_state(self.state)
            self.params.state = self.state
            await self.params.save()

        return False

    async def verify_posted(
        self,
        topic_id: int,
        author: str,
        min_id: int,
        timeout: int,
        interval: int,
    ):
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            result = await Message.filter(
                topic_id=topic_id, username=author, id__gt=min_id
            ).exists()
            logger.info(f"verify_posted: {result}, {topic_id}, {author}, {min_id}")
            if result:
                return True
            await asyncio.sleep(interval)
        raise NotPostedError()

    async def post_message(
        self,
        content: str,
        topic_id: int | None = None,
        answer_to: Message | None = None,
        _retry: int = 0,
        _last_post_id: int = 0,
    ) -> int:
        last_post_id = _last_post_id
        try:
            t = (  # pyright: ignore[reportUnknownVariableType]
                topic_id
                if topic_id
                else (
                    answer_to.topic_id  # pyright: ignore[reportAttributeAccessIssue]
                    if answer_to
                    else self.topic_id
                )
            )
            if not isinstance(t, int):
                raise Exception("Undefined topic in post_message")

            if last_post_id == 0:
                last_post = await Message.filter(topic_id=t).order_by("-id").first()
                last_post_id = last_post.id if last_post else 0

            res = await self.onche.post_message(t, content, answer_to)

            # Watch the database until posted, raise NotPostedError if it times out
            if self.onche.username:
                await self.verify_posted(
                    t,
                    self.onche.username,
                    min_id=last_post_id,
                    timeout=32,
                    interval=3,
                )

            await Metric.filter(id="posted_total").update(value=F("value") + 1)
            posted_total = await Metric.get_or_none(id="posted_total")
            if posted_total:
                metrics.posted_msg_counter.set(posted_total.value)

            return res
        except NotLoggedInError:
            max_retry = 5
            if _retry >= max_retry:
                raise Exception(
                    f"Could not log in after {_retry} retries, aborting post_message"
                )

            logger.info("Not logged in, will retry post_message after log in")
            await self.login()
            return await self.post_message(content, topic_id, answer_to, _retry + 1, last_post_id)
        except NotPostedError:
            max_retry = 4
            if _retry >= max_retry:
                raise Exception(
                    f"Could not post after {_retry} retries, aborting post_message"
                )

            wait = 10
            logger.info(f"Not posted, retrying post_message after login + {wait} secs")
            await self.login()
            await asyncio.sleep(wait)
            return await self.post_message(content, topic_id, answer_to, _retry + 1, last_post_id)

    async def login(self):
        old_cookie = self.user.cookie
        await self.user.refresh_from_db()
        if self.user.cookie != old_cookie:
            self.onche.cookie = self.user.cookie
            return

        cookie = await self.onche.login()
        if not cookie:
            return
        self.user.cookie = cookie
        await self.user.save()

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
