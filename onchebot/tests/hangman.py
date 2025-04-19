from onchebot import test
from onchebot.consumer import consume_once
from onchebot.examples import create_hangman
from onchebot.examples.hangman import HANGMAN_START_POINTS
from onchebot.test import onchebot_setup  # pyright: ignore[reportUnusedImport]


async def test_hangman(onchebot_setup: None):  # pyright: ignore[reportUnusedParameter]
    bot = create_hangman("hangman", test.user, test.topic_id, "Admin")
    bot.state["word"] = "merde"
    khey = "Connard"
    khey2 = "Pute"

    await test.add_msg("/ping", khey)
    await consume_once()
    assert "PONG" in test.posted_msgs[-1].content

    await test.add_msg("/status", khey)
    await consume_once()
    assert "_ _ _ _ _" in test.posted_msgs[-1].content

    await test.add_msg("/lettre a", khey)
    await test.add_msg("/lettre a", khey2)
    await consume_once()
    assert "_ _ _ _ _" in test.posted_msgs[-2].content
    assert bot.state["guesses"]["a"] == khey
    assert bot.state["points"][khey] == HANGMAN_START_POINTS - 1
    assert bot.state["points"][khey2] == HANGMAN_START_POINTS - 1

    await test.add_msg("/lettre b", khey)
    await consume_once()
    assert "_ _ _ _ _" in test.posted_msgs[-1].content
    assert bot.state["guesses"]["b"] == khey
    assert bot.state["points"][khey] == HANGMAN_START_POINTS - 2

    await test.add_msg("/lettre A", khey)
    await consume_once()
    assert bot.state["guesses"]["a"] == khey
    assert bot.state["points"][khey] == HANGMAN_START_POINTS - 3

    await test.add_msg("/lettre m", khey)
    await consume_once()
    assert "M _ _ _ _" in test.posted_msgs[-1].content
    assert bot.state["guesses"]["m"] == khey
    assert bot.state["points"][khey] == HANGMAN_START_POINTS - 3

    await test.add_msg("/lettre e", khey)
    await consume_once()
    assert "M E _ _ E" in test.posted_msgs[-1].content
    assert bot.state["guesses"]["e"] == khey
    assert bot.state["points"][khey] == HANGMAN_START_POINTS - 3

    await test.add_msg("/lettre r", khey)
    await consume_once()
    assert "M E R _ E" in test.posted_msgs[-1].content
    assert bot.state["guesses"]["r"] == khey
    assert bot.state["points"][khey] == HANGMAN_START_POINTS - 3

    await test.add_msg("/lettre d", khey)
    await consume_once()
    assert "MERDE" in test.posted_msgs[-1].content
    assert "Nouveau mot" in test.posted_msgs[-1].content
    assert "a" not in bot.state["guesses"]
    assert khey not in bot.state["points"]
    assert bot.state["word"] != "merde"

    await bot.set_state("word", "caca")

    await test.add_msg("/lettre c", khey)
    await consume_once()
    assert "C _ C _" in test.posted_msgs[-1].content
    assert bot.state["guesses"]["c"] == khey
    assert bot.state["points"][khey] == HANGMAN_START_POINTS - 0

    await test.add_msg("/mot cucu", khey)
    await consume_once()
    assert "C _ C _" in test.posted_msgs[-1].content
    assert bot.state["points"][khey] == HANGMAN_START_POINTS - 1

    await test.add_msg("/mot caca", khey)
    await consume_once()
    assert "CACA" in test.posted_msgs[-1].content
    assert "Nouveau mot" in test.posted_msgs[-1].content
    assert khey not in bot.state["points"]

    await bot.set_state("word", "arc-en-ciél")

    await test.add_msg("/lettre é", khey)
    await consume_once()
    assert "_ _ _ - E _ - _ _ E _" in test.posted_msgs[-1].content
    assert bot.state["guesses"]["e"] == khey
    assert bot.state["points"][khey] == HANGMAN_START_POINTS - 0
