import random

from onchebot.bot_module import BotModule
from onchebot.command import Command
from onchebot.dictionnaries import get_random_insult, get_random_loves
from onchebot.models import Message, User


class Misc(BotModule):
    """Adds useless commands like `insulte`, `ping`, `caca`"""

    def __init__(self, admin: str):
        super().__init__()
        self.admin: str = admin
        self.commands: list[Command] = [
            Command("insulte", self.insult),
            Command("love", self.love),
            Command("ping", self.ping),
            Command("caca", self.caca),
        ]

    async def insult(self, msg: Message, args: list[str]):
        if not self.bot or len(args) <= 0:
            return

        sender = msg.username
        insult = get_random_insult()
        target = args[0]
        if len(target) > 0 and target[0] == "@":
            target = target[1:]

        if (
            target.lower() == self.bot.user.username.lower()
            or target.lower() == self.admin.lower()
        ):
            sender_user = (
                (await self.bot.onche.get_user(target))
                if self.bot.onche
                else User(username=target)
            )
            if sender_user == None:
                return
            sender = sender_user.username
            target = msg.username
            insult = "Ta gueule"

        user = (
            (await self.bot.onche.get_user(target))
            if self.bot.onche
            else User(username=target)
        )
        if user == None:
            return

        await self.bot.post_message(
            f"@{user.username} {insult}\n[i]De la part de @{sender}[/i]",
            answer_to=msg,
        )

    async def love(self, msg: Message, args: list[str]):
        if not self.bot or len(args) <= 0:
            return

        sender = msg.username
        target = args[0]
        if len(target) > 0 and target[0] == "@":
            target = target[1:]

        user = (
            (await self.bot.onche.get_user(target))
            if self.bot.onche
            else User(username=target)
        )
        if user == None:
            return

        suffixes = [":hap_love:", ":ok:", ":risibo:", ":okok:", ":risipouce:"]
        suffix = random.choice(suffixes)

        loves = [love.lower() for love in get_random_loves(3)]
        sentence = f"Tu es {loves[0]}, {loves[1]}, et {loves[2]}!"
        await self.bot.post_message(
            f"@{user.username} {sentence} {suffix} \n[i]De la part de @{sender}[/i]",
            answer_to=msg,
        )

    async def ping(self, msg: Message, _: list[str]):
        if not self.bot:
            return
        await self.bot.post_message("PONG :singe_eussou: ", answer_to=msg)

    async def caca(self, msg: Message, _: list[str]):
        if not self.bot:
            return
        await self.bot.post_message(":caca_autiste:", answer_to=msg)
