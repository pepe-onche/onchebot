import onchebot
from onchebot.bot import Bot
from onchebot.models import Message, User


def create(id: str, user: User, topic_id: int) -> Bot:
    pingpong = onchebot.add_bot(id, user, topic_id)

    @pingpong.command("ping")
    async def send_pong(msg: Message, _):  # pyright: ignore[reportUnusedFunction]
        await pingpong.post_message("PONG :Singe:", answer_to=msg)

    @pingpong.command("pong")
    async def send_ping(msg: Message, _):  # pyright: ignore[reportUnusedFunction]
        await pingpong.post_message("PING :Singe:", answer_to=msg)

    return pingpong
