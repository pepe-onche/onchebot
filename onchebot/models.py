from dataclasses import dataclass


@dataclass
class Config:
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_username: str | None = None
    redis_password: str | None = None
    prometheus_host: str = "localhost"
    prometheus_port: int = 9464
    loki_url: str | None = None


@dataclass
class Message:
    id: int
    stickers: list[str]
    mentions: list[str]
    content_html: str
    content_without_stickers: str
    content: str
    username: str
    timestamp: int
    topic_id: int = -1
    answer_to: int | None = None


@dataclass
class Topic:
    id: int
    name: str
    title: str
    forum_id: int


@dataclass
class User:
    username: str
    password: str | None = None
    cookie: str | None = None
