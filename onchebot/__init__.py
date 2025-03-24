import asyncio
import logging
import os
import signal
import sys
import threading
from queue import Queue
from typing import Awaitable, Callable

import logging_loki
from prometheus_client import start_http_server
from tortoise import Tortoise

from onchebot import consumer, examples
from onchebot import globals as g
from onchebot import onche, producer
from onchebot.api import add_bot, add_user, setup
from onchebot.db import init as init_db

__all__ = ["add_bot", "add_user", "setup", "start", "examples", "onche"]

logging.basicConfig(
    level=logging.getLevelNamesMapping()[os.environ.get("LOG_LEVEL", "INFO")]
)
logger = logging.getLogger("main")

stop_event = threading.Event()

logging.getLogger("apscheduler.scheduler").disabled = True
logging.getLogger("apscheduler.scheduler").propagate = False
logging.getLogger("apscheduler.executors.default").disabled = True
logging.getLogger("apscheduler.executors.default").propagate = False


async def run(start_fn: Callable[[], Awaitable[None]] | None = None, stop_fn: Callable[[], Awaitable[None]] | None = None):
    if len(g.bots) == 0:
        logger.error("No bots, please add one")
        return

    await init_db()

    for i, user in enumerate(g.users):
        g.users[i], _ = await user.update_or_create(
            defaults={"username": user.username, "password": user.password}
        )

    for bot in g.bots:
        bot.user = next(user for user in g.users if user.username == bot.user.username)
        await bot.fetch_params()

    if start_fn:
        await start_fn()

    try:
        await asyncio.gather(
            producer.produce(stop_event), consumer.consume(False, stop_event)
        )
    except Exception as e:
        stop_event.set()
        if stop_fn:
            await stop_fn()
        raise e

    if stop_fn:
        await stop_fn()

    await Tortoise.close_connections()


def start(start_fn: Callable[[], Awaitable[None]] | None = None, stop_fn: Callable[[], Awaitable[None]] | None = None):
    global g

    if g.config.loki_url:
        handler = logging_loki.LokiQueueHandler(
            Queue(-1),
            url=g.config.loki_url,
            tags={"application": "onchebot"},
            version="1",
        )
        handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)

    # Start prometheus client
    start_http_server(port=g.config.prometheus_port, addr=g.config.prometheus_host)
    logger.info(
        f"Prometheus endpoint at {g.config.prometheus_host}:{g.config.prometheus_port}/metrics"
    )

    def signal_handler(*_):
        logger.error("Received signal to terminate, shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run(start_fn, stop_fn))
    loop.close()

    sys.exit(0)
