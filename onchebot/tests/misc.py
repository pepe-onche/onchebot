import onchebot
from onchebot import test
from onchebot.consumer import consume_once
from onchebot.modules.misc import Misc
from onchebot.test import onchebot_setup  # pyright: ignore[reportUnusedImport]


async def test_misc(onchebot_setup: None):  # pyright: ignore[reportUnusedParameter]
    onchebot.add_bot(
        "misc",
        test.user,
        test.topic_id,
        modules=[Misc(admin="admin")],
    )

    await test.add_msg("/insulte trapvador")
    await consume_once()
    assert "la part de" in test.posted_msgs[-1].content

    await test.add_msg("/love trapvador")
    await consume_once()
    assert "la part de" in test.posted_msgs[-1].content

    await test.add_msg("/ping")
    await consume_once()
    assert "PONG" in test.posted_msgs[-1].content

    await test.add_msg("/caca")
    await consume_once()
    assert "caca_autiste" in test.posted_msgs[-1].content
