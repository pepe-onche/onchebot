import onchebot
from onchebot.bot import Bot
from onchebot.models import Message, User


def create(id: str, user: User, topic_id: int) -> Bot:
    counter = onchebot.add_bot(id, user, topic_id, default_state={"count": 0})

    @counter.command("+1")
    async def add_one(msg: Message, _):  # pyright: ignore[reportUnusedFunction]
        counter.state["count"] += 1
        await counter.post_message(f"{counter.state['count']}", answer_to=msg)

    return counter
