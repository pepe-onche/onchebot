from collections import Counter
from typing import Any

from onchebot.bot_module import BotModule
from onchebot.models import Message


class Vote(BotModule):
    """Adds a voting system"""

    def __init__(self):
        super().__init__()
        self.default_state: dict[str, Any] = {"votes": {}}

    def reset_votes(self):
        if not self.bot:
            return
        self.bot.state["votes"] = {}

    def vote(self, msg: Message, choice: str):
        if not self.bot:
            return
        self.bot.state["votes"][msg.username] = choice

    # Returns the list of choices that had the highest number of votes
    # If more than one, result is ambiguous
    # If None, there were no votes
    def get_final_vote(self) -> list[str] | None:
        if not self.bot:
            return
        if not self.bot.state["votes"]:
            return None  # No votes

        votes: dict[str, int] = dict(Counter(self.bot.state["votes"].values()))
        max_vote = max(votes.values())
        final_vote = [key for key, value in votes.items() if value == max_vote]
        return final_vote

    async def final_vote(self):
        if not self.bot:
            return
        final_vote = self.get_final_vote()
        if final_vote is None:
            return False
        if len(final_vote) <= 0:
            return False
        if len(final_vote) > 1:
            votes_str = ", ".join([f"[b]{v}[/b]" for v in final_vote])
            await self.bot.post_message(
                f"Les choix: {votes_str}\nOnt le même nombre de votes. Décidez-vous bande de glandus."
            )
            self.reset_votes()
            return False

        return final_vote[0]
