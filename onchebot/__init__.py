import logging
import os
import signal
import sys
import threading
from queue import Queue

import logging_loki
from prometheus_client import start_http_server

from onchebot import consumer, examples
from onchebot import globals as g
from onchebot import onche, producer
from onchebot.api import add_bot, add_user, setup

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


def start():
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

    thread_producer = threading.Thread(target=producer.start, args=(stop_event,))
    thread_consumer = threading.Thread(target=consumer.start, args=(stop_event,))

    thread_producer.start()
    thread_consumer.start()

    thread_producer.join()
    thread_consumer.join()

    sys.exit(0)
