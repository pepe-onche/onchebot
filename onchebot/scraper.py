import asyncio
import logging
import threading
import time
import traceback

import aiohttp

import onchebot.globals as g
from onchebot.models import Message
from onchebot.onche import NotFoundError, Onche, OncheTopic
from onchebot.redis_client import redis

logger = logging.getLogger("scraper")

tick = 15  # seconds


class TopicScraper:
    def __init__(
        self,
        topic_id: int,
        last_msg_id: int,
        last_msg_timestamp: int,
    ):
        self.topic_id: int = topic_id
        self.last_msg_id: int = last_msg_id
        self.last_msg_timestamp: int = last_msg_timestamp
        self.start_timestamp: int | None = None
        self.topic: OncheTopic | None = None

    async def run(
        self,
        onche: Onche,
        stop_event: threading.Event | None = None,
    ):
        if not self.topic_id:
            return

        if not stop_event:
            stop_event = threading.Event()

        self.topic = await onche.init_topic(self.topic_id)
        await redis().set_topic(self.topic.to_model())
        self.start_timestamp = int(time.time())

        while not stop_event.is_set():
            try:
                messages = await self.read_until_msg_id(onche, self.last_msg_id, -1, [])

                if len(messages) > 0:
                    logger.debug(f"{len(messages)} new messages")

                yield list(reversed(messages))

                if len(messages) > 0:
                    self.last_msg_id = messages[0].id
                    self.last_msg_timestamp = messages[0].timestamp

            except aiohttp.ClientConnectorError as e:
                logger.error("connection error")
                logger.error(traceback.format_exc())
            except Exception as e:
                logger.error(traceback.format_exc())

            await asyncio.sleep(tick)

    async def read_until_msg_id(
        self,
        onche: Onche,
        msg_id: int,
        page: int = -1,
        msg_buffer: list[Message] | None = None,
    ) -> list[Message]:
        if not self.topic:
            return []

        if page == -1:
            page = self.topic.last_page

        if not msg_buffer:
            msg_buffer = []

        max_msg_time_limit = max(
            [bot.msg_time_threshold for bot in g.bots if bot.topic_id == self.topic_id],
            default=None,
        )
        if not max_msg_time_limit:
            return msg_buffer

        try:
            msgs = list(reversed(await onche.fetch_messages(self.topic.id, page)))
        except NotFoundError:  # Stop with a sleep if we get a 404
            await asyncio.sleep(10)
            self.topic = await onche.init_topic(self.topic_id)  # Re-init the topic
            await asyncio.sleep(3)
            return msg_buffer

        for msg in msgs:
            if int(time.time()) - max_msg_time_limit > msg.timestamp:
                return msg_buffer
            if msg.id <= msg_id:
                return msg_buffer
            msg_buffer.append(msg)

        if page == 1:
            return msg_buffer

        return await self.read_until_msg_id(onche, msg_id, page - 1, msg_buffer)
