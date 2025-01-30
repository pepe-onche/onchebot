from onchebot import test
from onchebot.consumer import consume_once
from onchebot.examples import create_counter
from onchebot.test import onchebot_setup  # pyright: ignore[reportUnusedImport]


async def test_counter(onchebot_setup: None):  # pyright: ignore[reportUnusedParameter]
    bot = create_counter("counter", test.user, test.topic_id)

    await test.add_msg("/+1")
    await consume_once()
    assert "1" in test.posted_msgs[-1].content

    await test.add_msg("/+1")
    await consume_once()
    assert "2" in test.posted_msgs[-1].content

    await test.add_msg("/+1")
    await consume_once()
    assert "3" in test.posted_msgs[-1].content

    assert bot.state["count"] == 3
