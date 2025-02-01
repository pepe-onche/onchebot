import asyncio
import logging
import threading
import time
import traceback

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tortoise.expressions import Q

import onchebot.globals as g
from onchebot.models import Message

logger = logging.getLogger("consumer")


async def consume_once():
    for bot in g.bots:
        await bot.fetch_params()

    await consume(once=True)


async def consume(once: bool = False, stop_event: threading.Event | None = None):
    if not stop_event:
        stop_event = threading.Event()

    scheduler = AsyncIOScheduler()
    scheduler.start()

    while not stop_event.is_set():
        # topic_id -> oldest last consumed msg id for any bot
        topic_thresholds: dict[str, int] = {}
        for bot in g.bots:
            if not bot.params:
                continue

            if not once and not bot.tasks_created:
                await bot.create_tasks(scheduler)

            if (
                str(bot.topic_id) not in topic_thresholds
                or topic_thresholds[str(bot.topic_id)] > bot.params.last_consumed_id
            ):
                topic_thresholds[str(bot.topic_id)] = bot.params.last_consumed_id

        queries = [
            Q(topic_id=int(topic), id__gt=threshold)
            for topic, threshold in topic_thresholds.items()
        ]
        query = queries[0]
        for q in queries[1:]:
            query |= q

        latest_messages = await Message.filter(query).order_by("topic_id", "-id")
        if len(latest_messages) > 0:
            logger.debug(f"{len(latest_messages)} new messages")

        for msg in latest_messages:
            topic_id: int = msg.topic_id
            try:
                bots = filter(lambda b: b.topic_id == topic_id, g.bots)

                for bot in bots:
                    if not bot.params:
                        continue

                    # Skip if the message was already consumed by the bot
                    if bot.params.last_consumed_id >= msg.id:
                        continue

                    # Skip if it's a message from the bot
                    if bot.user and msg.username == bot.user.username:
                        continue

                    # Skip if the message is too old
                    if int(time.time()) - bot.msg_time_threshold > msg.timestamp:
                        continue

                    # Finally consume the message
                    await bot.consume_msg(msg)
            except Exception:
                logger.error(traceback.format_exc())

        if once:
            break

        await asyncio.sleep(5)

    scheduler.shutdown()
