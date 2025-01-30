import onchebot
from onchebot.bot import Bot
from onchebot.models import Message, User


def create(id: str, user: User, topic_id: int) -> Bot:
    repeater = onchebot.add_bot(id, user, topic_id)

    @repeater.on_message()
    async def repeat(msg: Message):  # pyright: ignore[reportUnusedFunction]
        await repeater.post_message(msg.content, answer_to=msg)

    return repeater
