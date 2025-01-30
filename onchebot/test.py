import json
from dataclasses import asdict, dataclass
from time import time

import fakeredis
import pytest
from pytest_mock import MockerFixture

import onchebot
import onchebot.globals as g
from onchebot.models import Message, Topic, User
from onchebot.redis_client import redis

topic_id = -1
topic_title = "Titre"
user = None


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
    await redis().set_topic(
        Topic(id=topic_id, name="hey", title=topic_title, forum_id=1)
    )
    msg = Message(
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
    await redis().r.xadd(
        name="onchebot:topics:" + str(topic_id) + ":messages",
        fields={"msg": json.dumps(asdict(msg))},
    )
    await redis().r.sadd("onchebot:watched-topics", str(msg.topic_id))
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
    msg = Message(
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
    await redis().r.xadd(
        name="onchebot:topics:" + str(topic_id) + ":messages",
        fields={"msg": json.dumps(asdict(msg))},
    )
    posted_msgs.append(msg)


async def login():
    return ""


def start():
    pass


@pytest.fixture
async def onchebot_setup(mocker: MockerFixture):
    global posted_msgs, bots, bot_types, user
    posted_msgs = []
    g.bots = []
    mocker.patch("redis.asyncio.Redis", fakeredis.aioredis.FakeRedis)
    mocker.patch("onchebot.redis_client.aioredis.Redis", fakeredis.aioredis.FakeRedis)
    mocker.patch("onchebot.bot.Bot.post_message", side_effect=post_msg)
    mocker.patch("onchebot.onche.Onche.get_user", side_effect=get_user)
    mocker.patch("onchebot.onche.Onche.login", side_effect=login)
    mocker.patch("onchebot.start", side_effect=start)
    onchebot.setup()
    user = onchebot.add_user(username="Bot", password="caca")
