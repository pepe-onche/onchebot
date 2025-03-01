import asyncio
import logging
import re
import threading
from asyncio.tasks import Task
from collections.abc import Coroutine
from typing import Any

from tortoise import Tortoise
from tortoise.expressions import F

import onchebot.globals as g
import onchebot.metrics as metrics
from onchebot.models import Message, Metric
from onchebot.onche import Onche
from onchebot.scraper import TopicScraper

logger = logging.getLogger("producer")

tasks: dict[
    str,
    tuple[
        Coroutine[Any, Any, None],
        Task[None],
        int,
    ],
] = {}

mins_regex = re.compile(r"(\d+)m")

onche = Onche()


async def produce(stop_event: threading.Event | None = None):
    global tasks

    if not stop_event:
        stop_event = threading.Event()

    msg_total, _ = await Metric.get_or_create(
        id="messages_total", defaults={"value": 0}
    )

    metrics.msg_counter.set(msg_total.value)

    posted_total, _ = await Metric.get_or_create(
        id="posted_total", defaults={"value": 0}
    )
    metrics.posted_msg_counter.set(posted_total.value)

    topics_total, _ = await Metric.get_or_create(
        id="topics_total", defaults={"value": 0}
    )
    metrics.topic_counter.set(topics_total.value)

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

        metrics.watched_topic_counter.set(len(tasks))

        await asyncio.sleep(10)

    await asyncio.gather(*[t[0] for t in tasks.values()], return_exceptions=True)
    await Tortoise.close_connections()


# Start scraper on a topic
async def produce_topic(
    topic_id: int, stop_event: threading.Event | None = None
) -> None:
    if not stop_event:
        stop_event = threading.Event()

    last_msg_in_topic: Message | None = (
        await Message.filter(topic_id=topic_id).order_by("-id").first()
    )
    scraper = TopicScraper(
        topic_id,
        last_msg_in_topic.id if last_msg_in_topic else -1,
        last_msg_in_topic.timestamp if last_msg_in_topic else -1,
    )
    msg_list: list[Message] = []

    async for messages in scraper.run(
        onche,
        stop_event=stop_event,
    ):
        for msg in messages:
            logger.debug("New message: %s", msg)
            msg_list.append(msg)
            await msg.save()
            await Metric.filter(id="messages_total").update(value=F("value") + 1)
            msg_total = await Metric.get_or_none(id="messages_total")
            if msg_total:
                metrics.msg_counter.set(msg_total.value)
