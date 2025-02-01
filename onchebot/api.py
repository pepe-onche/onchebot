from dataclasses import fields
from typing import Any

from dacite import from_dict

import onchebot.globals as g
import onchebot.metrics as metrics
from onchebot.bot import Bot
from onchebot.bot_module import BotModule
from onchebot.models import Config, User


def setup(**kwargs: dict[str, Any]):
    global g
    valid_fields = {f.name for f in fields(Config)}
    for key in kwargs:
        if key not in valid_fields:
            raise ValueError(f"Invalid argument: {key}")

    g.config = from_dict(Config, kwargs)


def add_user(username: str, password: str) -> User:
    user = User(username=username, password=password)
    g.users.append(user)
    return user


def add_bot(
    id: str,
    user: User,
    topic_id: int,
    default_state: dict[str, Any] | None = None,
    modules: list[BotModule] | None = None,
    prefix: str | None = None,
    msg_time_threshold: int = 10 * 60,
):
    if any(b.id == id for b in g.bots):
        raise Exception(f"Bot {id} already exists")

    try:
        _user = next(u for u in g.users if user.username.lower() == u.username.lower())
    except:
        raise Exception(
            f"User {user.username} not found, you need to call onchebot.add_user()"
        )

    if not default_state:
        default_state = {}
    if not modules:
        modules = []

    bot = Bot(
        id=id,
        user=_user,
        topic_id=topic_id,
        modules=modules,
        default_state=default_state,
        prefix=prefix,
        msg_time_threshold=msg_time_threshold,
    )
    g.bots.append(bot)
    metrics.bot_counter.set(len(g.bots))
    return bot
