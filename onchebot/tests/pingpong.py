from onchebot import test
from onchebot.consumer import consume_once
from onchebot.examples import create_pingpong
from onchebot.test import onchebot_setup  # pyright: ignore[reportUnusedImport]


async def test_pingpong(onchebot_setup: None):  # pyright: ignore[reportUnusedParameter]
    bot = create_pingpong("pingpong", test.user, test.topic_id)

    await test.add_msg("/ping")
    await consume_once()
    assert "PONG" in test.posted_msgs[-1].content

    await test.add_msg("/pong")
    await consume_once()
    assert "PING" in test.posted_msgs[-1].content

    # command is ignored if the message is from the bot
    prev_len = len(test.posted_msgs)
    await test.add_msg("/ping", bot.user.username)
    await consume_once()
    assert prev_len == len(test.posted_msgs)
