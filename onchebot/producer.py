import asyncio
import json
import logging
import re
import threading
from asyncio.tasks import Task
from collections.abc import Coroutine
from dataclasses import asdict
from typing import Any

import onchebot.globals as g
import onchebot.metrics as metrics
from onchebot.models import Message
from onchebot.onche import Onche
from onchebot.redis_client import redis
from onchebot.scraper import TopicScraper

logger = logging.getLogger("producer")

tasks: dict[
    str,
    tuple[
        Coroutine[Any, Any, tuple[Message | None, list[Message]]],
        Task[tuple[Message | None, list[Message]]],
        int,
    ],
] = {}

mins_regex = re.compile(r"(\d+)m")

onche = Onche()


async def produce(stop_event: threading.Event | None = None):
    global tasks

    if not stop_event:
        stop_event = threading.Event()

    await redis().r.delete("onchebot:watched-topics")

    msg_total = await redis().r.get(name="onchebot:metadata:messages:total")
    if msg_total != None:
        metrics.msg_counter.set(int(msg_total))

    posted_total = await redis().r.get(name="onchebot:metadata:messages:posted_total")
    if posted_total != None:
        metrics.posted_msg_counter.set(int(posted_total))

    topics_total = await redis().r.get(name="onchebot:metadata:topics:total")
    if topics_total != None:
        metrics.topic_counter.set(int(topics_total))

    while not stop_event.is_set():
        topic_ids = set(bot.topic_id for bot in g.bots)

        # Produce topics
        for topic_id in topic_ids:
            if str(topic_id) not in tasks:
                co = produce_topic(topic_id, stop_event=stop_event)
                tasks[str(topic_id)] = (co, asyncio.create_task(co), topic_id)

        # Remove all completed tasks
        for i in range(len(tasks.keys()) - 1, -1, -1):
            key = list(tasks.keys())[i]
            if tasks[key][1].done():
                del tasks[str(key)]
                await redis().r.srem("onchebot:watched-topics", str(key))

        metrics.watched_topic_counter.set(
            await redis().r.scard("onchebot:watched-topics")
        )

        await asyncio.sleep(12)

    await asyncio.gather(*[t[0] for t in tasks.values()], return_exceptions=True)


# Start scraper on a topic
async def produce_topic(
    topic_id: int, stop_event: threading.Event | None = None
) -> tuple[Message | None, list[Message]]:
    if not stop_event:
        stop_event = threading.Event()
    msg: Message | None = await redis().get_topic_last_msg(topic_id)
    scraper = TopicScraper(
        topic_id, msg.id if msg else -1, msg.timestamp if msg else -1
    )
    msg_list: list[Message] = []

    await redis().r.sadd("onchebot:watched-topics", str(topic_id))

    will_incr_topics_total = (
        await redis().r.exists(f"onchebot:topics:{topic_id}:messages") == 0
    )

    async for messages in scraper.run(
        onche,
        stop_event=stop_event,
    ):
        for msg in messages:
            logger.debug("New message: %s", msg)
            msg_list.append(msg)
            await redis().r.xadd(
                name=f"onchebot:topics:{topic_id}:messages",
                fields={"msg": json.dumps(asdict(msg))},
                maxlen=200,
            )
            metrics.msg_counter.set(
                await redis().r.incrby(
                    name="onchebot:metadata:messages:total", amount=1
                )
            )

    # Increment metadata:topics:total
    if len(msg_list) > 0 and will_incr_topics_total:
        metrics.topic_counter.set(
            await redis().r.incrby(name="onchebot:metadata:topics:total", amount=1)
        )

    return (msg, msg_list)


def start(stop_event: threading.Event | None = None):
    if not stop_event:
        stop_event = threading.Event()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(produce(stop_event))
    loop.close()
