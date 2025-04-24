from dataclasses import dataclass
from typing import Any

from tortoise.fields import (BigIntField, CharField, Field, ForeignKeyField,
                             ForeignKeyNullableRelation, IntField, JSONField,
                             TextField)
from tortoise.models import Model


@dataclass
class Config:
    db_url: str = f"sqlite://db.sqlite3"
    prometheus_host: str = "localhost"
    prometheus_port: int = 9464
    loki_url: str | None = None
    cf_clearance: str | None = None


class Metric(Model):
    id: Field[str] = TextField(pk=True)
    value: Field[int] = IntField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table: str = "onchebot_metrics"


class Topic(Model):
    id: Field[int] = IntField(pk=True)
    name: Field[str] = CharField(max_length=255)
    title: Field[str] = CharField(max_length=255)
    forum_id: Field[int] = IntField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table: str = "onchebot_topics"


class Message(Model):
    id: Field[int] = IntField(pk=True)
    stickers: Field[dict[str, Any]] = JSONField()
    mentions: Field[dict[str, Any]] = JSONField()
    content_html: Field[str] = TextField()
    content_without_stickers: Field[str] = TextField()
    content: Field[str] = TextField()
    username: Field[str] = CharField(max_length=255)
    timestamp: Field[int] = BigIntField()
    topic: ForeignKeyNullableRelation[Topic] = ForeignKeyField(
        "models.Topic", related_name="messages", null=True, default=-1
    )
    answer_to: Field[int] = IntField(null=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table: str = "onchebot_messages"
        indexes: list[tuple[str, str]] = [("topic_id", "id")]


class User(Model):
    username: Field[str] = CharField(max_length=255, unique=True)
    password: Field[str] = CharField(max_length=255, null=True)
    cookie: Field[str] = CharField(max_length=666, null=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table: str = "onchebot_users"


class BotParams(Model):
    id: Field[str] = TextField(pk=True)
    state: Field[dict[str, Any]] = JSONField()
    last_consumed_id: Field[int] = BigIntField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table: str = "onchebot_bots"
