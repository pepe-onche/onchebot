# pyright: reportUnknownArgumentType=none

import asyncio
import json
import logging
import threading
import uuid
from dataclasses import asdict
from typing import Any, cast

from dacite import from_dict
from redis import asyncio as aioredis

import onchebot.globals as g
from onchebot.models import Message, Topic, User

logger = logging.getLogger("redis")


class OncheRedis:
    def __init__(self):
        self.r = aioredis.Redis(
            host=g.config.redis_host,
            port=g.config.redis_port,
            username=g.config.redis_username,
            password=g.config.redis_password,
            decode_responses=True,
        )

    async def get_bot_ids(self) -> list[str]:
        return [
            k.split(":")[1] async for k in self.r.scan_iter(match="onchebot:bots:*")
        ]

    async def get_topic_last_msg(self, topic_id: int) -> Message | None:
        res = await self.r.xrevrange(f"onchebot:topics:{topic_id}:messages", count=1)
        if len(res) <= 0:
            return None
        return from_dict(Message, json.loads(res[0][1]["msg"]))

    async def ensure_group(self, stream_name: str, group_name: str) -> None:
        from redis.exceptions import ResponseError

        try:
            await self.r.xgroup_create(
                name=stream_name, groupname=group_name, id="0", mkstream=True
            )
        except ResponseError as e:
            # Ignore the error if the group already exists
            if "BUSYGROUP Consumer Group name already exists" in str(e):
                return
            else:
                raise

    async def set_topic(self, topic: Topic) -> None:
        try:
            await self.r.hset(f"onchebot:topics:{topic.id}", mapping=asdict(topic))
        except Exception as e:
            logger.error(topic, asdict(topic))
            raise e

    async def get_topic(self, topic_id: int) -> Topic | None:
        res = cast(
            dict[str, str | int], await self.r.hgetall(f"onchebot:topics:{topic_id}")
        )
        if not res:
            return None
        res["id"] = int(res["id"])
        res["forum_id"] = int(res["forum_id"])
        return from_dict(Topic, res)

    async def get_topic_messages(
        self, topic_id: int, count: Any | None
    ) -> list[Message]:
        raw_messages: list[dict[str, Any]] = await self.r.xrevrange(
            f"onchebot:topics:{topic_id}:messages", max="+", min="-", count=count
        )
        messages: list[Message] = [
            from_dict(Message, json.loads(raw_msg[1]["msg"]))
            for raw_msg in raw_messages
        ]
        return list(reversed(messages))

    async def set_user_cookie(self, username: str, cookie: str) -> None:
        await self.r.hset(f"onchebot:users:{username}", mapping={"cookie": cookie})

    async def get_usernames(self) -> list[str]:
        return [
            k.split(":")[1] async for k in self.r.scan_iter(match="onchebot:users:*")
        ]

    async def get_user_cookie(self, username: str) -> str | None:
        res = await self.r.hgetall(f"onchebot:users:{username}")
        if not res:
            return None
        try:
            return res.get("cookie", None)
        except:
            return None

    async def get_users(self) -> list[User]:
        usernames = await self.get_usernames()
        pipe = self.r.pipeline()
        for username in usernames:
            pipe.hgetall(f"onchebot:users:{username}")
        raw_users = cast(list[dict[str, str]], await pipe.execute())
        return [from_dict(User, ru) for ru in raw_users]

    async def get_topics(self, topic_ids: list[int]) -> list[Topic]:
        pipe = self.r.pipeline()
        for id in topic_ids:
            pipe.hgetall(f"onchebot:topics:{id}")
        raw_topics = cast(list[dict[str, str]], await pipe.execute())
        return [from_dict(Topic, ru) for ru in raw_topics]


class RedisLock:
    def __init__(self, lock_key: str, ttl: int = 40):
        self.lock_key: str = lock_key
        self.ttl: int = ttl
        self.lock_value: str = str(  # Unique value to identify the lock holder
            uuid.uuid4()
        )

    async def acquire_lock(self):
        """Acquire the lock with a unique value."""
        while True:
            # Try to set the lock key with the unique value if it doesn't already exist
            result = await redis().r.setnx(self.lock_key, self.lock_value)
            if result:
                # If lock is acquired, set expiration time for the lock
                await redis().r.expire(self.lock_key, self.ttl)
                return self.lock_value
            else:
                # If the lock exists, wait and retry
                await asyncio.sleep(1)

    async def release_lock(self):
        """Release the lock if the value matches."""
        current_value = await redis().r.get(self.lock_key)
        if current_value == self.lock_value:
            await redis().r.delete(self.lock_key)
        else:
            logger.error("Failed to release lock: Not the lock holder")

    async def is_locked(self):
        """Check if the lock is acquired."""
        return await redis().r.exists(self.lock_key)


_thread_local = threading.local()


def redis() -> OncheRedis:
    if not hasattr(_thread_local, "redis_client"):
        _thread_local.redis_client = OncheRedis()

    return _thread_local.redis_client
