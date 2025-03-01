import logging
import os
import random
import unicodedata
from ast import FormattedValue

import onchebot
from onchebot.bot import Bot
from onchebot.dictionnaries import get_random_hangman_word, letters_lower
from onchebot.models import Message, User
from onchebot.modules import Misc

logger = logging.getLogger("hangman")

HANGMAN_START_POINTS = 7


def create(id: str, user: User, topic_id: int, admin: str) -> Bot:
    hangman = onchebot.add_bot(
        id,
        user,
        topic_id,
        modules=[Misc(admin=admin)],
        default_state={"word": get_random_hangman_word(), "guesses": {}, "points": {}},
    )

    def remove_accents(text: str) -> str:
        return "".join(
            c
            for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )

    def format_word(word: str) -> str:
        return remove_accents(word)

    def hangman_format_word() -> str:
        return format_word(hangman.state["word"].lower())

    def state_text() -> str:
        word = list(hangman_format_word())
        word = [
            (
                l.upper()
                if l in hangman.state["guesses"]
                else (l if l not in letters_lower else "_")
            )
            for l in word
        ]
        word = " ".join(word)
        return f"[center][b]{word}[/b][/center]"

    def remove_point(khey: str):
        if khey not in hangman.state["points"]:
            hangman.state["points"][khey] = HANGMAN_START_POINTS
        hangman.state["points"][khey] -= 1

    def is_win() -> bool:
        letters_in_word = list(hangman_format_word())
        return all(l in hangman.state["guesses"] for l in letters_in_word)

    async def on_win(msg: Message):
        remove_point(msg.username)
        score = hangman.state["points"][msg.username]
        word = hangman.state["word"].upper()
        hangman.state["guesses"] = {}
        hangman.state["points"] = {}
        hangman.state["word"] = get_random_hangman_word()
        state = state_text()
        return await hangman.post_message(
            f"Bravo champion, le mot était [b]{word}[/b] :Fritechat:\nNouveau mot:\n\n{state}",
            answer_to=msg,
        )

    async def on_bad(msg: Message):
        remove_point(msg.username)
        score = hangman.state["points"][msg.username]
        sticker = random.choice(
            [
                ":Risitas_wtf:",
                ":Dubitatif2:",
                ":Autistin:",
                ":Tarax_2:",
            ]
        )
        state = state_text()
        return await hangman.post_message(
            f"Non, il te reste {score}/{HANGMAN_START_POINTS} points {sticker}\n\n{state}",
            answer_to=msg,
        )

    async def on_good(msg: Message):
        remove_point(msg.username)
        score = hangman.state["points"][msg.username]
        sticker = random.choice(
            [
                ":chatpointilleux:",
                ":Cohen_ahi:",
                ":Chat_marrant_:",
                ":notready2:",
            ]
        )
        state = state_text()
        return await hangman.post_message(
            f"Bravo, il te reste {score}/{HANGMAN_START_POINTS} points {sticker}\n\n{state}",
            answer_to=msg,
        )

    @hangman.command("lettre")
    async def lettre(  # pyright: ignore[reportUnusedFunction]
        msg: Message, args: list[str]
    ):
        if len(args) <= 0:
            return

        # No more guesses
        if (
            msg.username in hangman.state["points"]
            and hangman.state["points"][msg.username] <= 0
        ):
            return

        l = remove_accents(args[0].lower())

        # Invalid letter
        if l not in letters_lower:
            return

        # Letter already guessed
        if l in hangman.state["guesses"]:
            remove_point(msg.username)
            score = hangman.state["points"][msg.username]
            state = state_text()
            t = random.choice(
                [
                    "Il faut suivre enculin",
                    "Déjà dit",
                ]
            )
            return await hangman.post_message(
                t + f", il te reste {score}/{HANGMAN_START_POINTS} points\n\n{state}",
                answer_to=msg,
            )

        hangman.state["guesses"][l] = msg.username

        # Win
        if is_win():
            return await on_win(msg)

        # Bad guess
        formatted_word = hangman_format_word()
        if l not in formatted_word:
            return await on_bad(msg)

        # Good guess
        await on_good(msg)

    @hangman.command("mot")
    async def mot(  # pyright: ignore[reportUnusedFunction]
        msg: Message, args: list[str]
    ):
        if len(args) <= 0:
            return

        guess = args[0]

        if hangman_format_word() == format_word(guess.lower()):
            return await on_win(msg)

        await on_bad(msg)

    @hangman.command("status")
    async def status(msg: Message, _):  # pyright: ignore[reportUnusedFunction]
        return await hangman.post_message(
            state_text(),
            answer_to=msg,
        )

    return hangman
