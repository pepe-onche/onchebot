from dataclasses import dataclass
from time import time

import pytest
from pytest_mock import MockerFixture
from tortoise import Tortoise

import onchebot
import onchebot.globals as g
from onchebot.models import Message, Topic, User

topic_id = -1
topic_title = "Titre"
user = None


async def init_db():
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["onchebot.models"]},
    )
    await Tortoise.generate_schemas()


@dataclass
class PostedMessage:
    content: str
    answer_to: Message | None


posted_msgs: list[Message] = []

msg_counter = 0


async def add_msg(
    content: str, username: str = "Connard", answer_to: Message | None = None
) -> Message:
    global msg_counter
    await Topic.update_or_create(id=topic_id, name="hey", title=topic_title, forum_id=1)
    msg = await Message.create(
        id=msg_counter,
        answer_to=answer_to.id if answer_to else None,
        stickers=[],
        mentions=[],
        content_html=content,
        content_without_stickers=content,
        content=content,
        username=username,
        timestamp=int(time()),
        topic_id=topic_id,
    )
    msg_counter += 1
    return msg


async def get_user(username: str) -> User:
    return User(username=username)


async def post_msg(
    content: str,
    _: int | None = None,
    answer_to: Message | None = None,
    _retry: int = 0,
):
    global msg_counter
    msg = await Message.create(
        id=msg_counter,
        answer_to=answer_to.id if answer_to else None,
        stickers=[],
        mentions=[],
        content_html=content,
        content_without_stickers=content,
        content=content,
        username="__bot__",
        timestamp=int(time()),
        topic_id=topic_id,
    )
    msg_counter += 1
    posted_msgs.append(msg)


async def login():
    return ""


def start():
    pass


@pytest.fixture
async def onchebot_setup(mocker: MockerFixture):
    global posted_msgs, bots, bot_types, user
    await init_db()
    posted_msgs = []
    g.bots = []
    mocker.patch("onchebot.bot.Bot.post_message", side_effect=post_msg)
    mocker.patch("onchebot.onche.Onche.get_user", side_effect=get_user)
    mocker.patch("onchebot.onche.Onche.login", side_effect=login)
    mocker.patch("onchebot.start", side_effect=start)
    onchebot.setup()
    user = onchebot.add_user(username="Bot", password="caca")
    yield None
    await Tortoise.close_connections()
