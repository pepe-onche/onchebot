from dataclasses import dataclass
from typing import Any

from tortoise import fields
from tortoise.models import Model


@dataclass
class Config:
    db_url: str = f"sqlite://db.sqlite3"
    prometheus_host: str = "localhost"
    prometheus_port: int = 9464
    loki_url: str | None = None


class Metric(Model):
    id = fields.TextField(pk=True)
    value = fields.IntField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table = "onchebot_metrics"


class Message(Model):
    id = fields.IntField(pk=True)
    stickers: fields.Field[dict[str, Any]] = fields.JSONField()
    mentions: fields.Field[dict[str, Any]] = fields.JSONField()
    content_html = fields.TextField()
    content_without_stickers = fields.TextField()
    content = fields.TextField()
    username = fields.CharField(max_length=255)
    timestamp = fields.BigIntField()
    topic = fields.ForeignKeyField(
        "models.Topic", related_name="messages", null=True, default=-1
    )
    answer_to = fields.IntField(null=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table = "onchebot_messages"
        indexes = [("topic_id", "id")]


class Topic(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    title = fields.CharField(max_length=255)
    forum_id = fields.IntField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table = "onchebot_topics"


class User(Model):
    username = fields.CharField(max_length=255, unique=True)
    password = fields.CharField(max_length=255, null=True)
    cookie = fields.CharField(max_length=255, null=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table = "onchebot_users"


class BotParams(Model):
    id = fields.TextField(pk=True)
    state: fields.Field[dict[str, Any]] = fields.JSONField()
    last_consumed_id = fields.BigIntField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table = "onchebot_bots"
