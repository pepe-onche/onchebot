import asyncio
import json
import logging
import threading
import time
import traceback

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dacite import from_dict

import onchebot.globals as g
from onchebot.models import Message
from onchebot.redis_client import redis

logger = logging.getLogger("consumer")


async def consume_once():
    await consume(once=True)


async def consume(once: bool = False, stop_event: threading.Event | None = None):
    if not stop_event:
        stop_event = threading.Event()

    scheduler = AsyncIOScheduler()
    scheduler.start()

    while not stop_event.is_set():
        if len(g.bots) == 0:
            logger.error("No bots, please add one")
            await asyncio.sleep(2)
            continue

        watched_topics = await redis().r.smembers("onchebot:watched-topics")

        topic_ids = set(int(bot.topic_id) for bot in g.bots)
        for topic in watched_topics:
            try:
                topic_ids.add(int(topic))
            except:
                pass

        for topic_id in topic_ids:
            await redis().ensure_group(
                f"onchebot:topics:{topic_id}:messages", "onchebot"
            )

        for bot in g.bots:
            if not once and not bot.tasks_created:
                await bot.create_tasks(scheduler)

        result = await redis().r.xreadgroup(
            groupname="onchebot",
            consumername="onchebot-consumer",
            streams={
                f"onchebot:topics:{topic_id}:messages": ">" for topic_id in topic_ids
            },
            block=3000,
            count=100,
        )

        for stream, messages in result:
            topic_id = int(stream.split(":")[2])
            topic = await redis().get_topic(topic_id)
            for key, raw_msg in messages:
                try:
                    await redis().r.xack(stream, "onchebot", key)
                    msg = from_dict(Message, json.loads(raw_msg["msg"]))

                    bots = filter(lambda b: b.topic_id == topic_id, g.bots)

                    for bot in bots:
                        if bot.user and msg.username == bot.user.username:
                            continue

                        if int(time.time()) - bot.msg_time_threshold > msg.timestamp:
                            continue
                        await bot.consume_msg(msg)
                except Exception:
                    logger.error(traceback.format_exc())

        if once:
            break

    scheduler.shutdown()


def start(stop_event: threading.Event | None = None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(consume(stop_event=stop_event))
    loop.close()
