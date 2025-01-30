import logging
import re

import aiohttp
from apscheduler.triggers.cron import CronTrigger
from googletrans import Translator

import onchebot
from onchebot.bot import Bot
from onchebot.models import Message, User

logger = logging.getLogger("apod")


def create(id: str, user: User, topic_id: int, admin: str, api_key: str) -> Bot:
    apod = onchebot.add_bot(id, user, topic_id, default_state={"last_date": None})

    yt_embed_regex = r"https://www\.youtube\.com/embed/([a-zA-Z0-9_-]+)"

    def is_youtube_embed(string: str):
        return re.match(yt_embed_regex, string)

    def youtube_embed_to_watch_url(embed_url: str):
        match = re.match(yt_embed_regex, embed_url)

        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"
        else:
            return embed_url

    async def on_apod():
        # Fetch today's picture metadata
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.nasa.gov/planetary/apod?api_key={api_key}"
            ) as resp:
                if resp.status != 200:
                    logger.error(resp)
                    return
                r: dict[str, str] = await resp.json()
                logger.info(r)

        # Extract metadata from response
        date = r.get("date", "")
        if date == apod.get_state("last_date"):
            return

        title = r.get("title", None)
        url = r.get("url", None)
        hdurl = r.get("hdurl", None)
        explanation = r.get("explanation", None)

        if url == None:
            return

        # Translate title and explanation to french
        async with Translator() as translator:
            title_fr: str | None = (
                (await translator.translate(title, src="en", dest="fr")).text
                if title
                else None
            )
            explanation_fr = (
                (await translator.translate(explanation, src="en", dest="fr")).text
                if explanation
                else None
            )

        image_msg = ""

        if is_youtube_embed(url):  # When `url` is not an image but a youtube link
            logger.info("Picture of the day is a youtube embed")
            image_msg = youtube_embed_to_watch_url(url)
        else:
            # Download today's picture into `image_data`
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.error(resp)
                        return
                    image_data = await resp.read()

            # Upload today's picture to onche
            image_id = await apod.upload_image(image_data, "image.jpg", "image/jpeg")
            if not image_id:
                return

            image_msg = f"[img:{image_id}]"

        # Update the bot state
        apod.set_state("last_date", date)
        logger.info(f"APOD DATE: {date}")

        # Assemble the message
        title_msg = f"[b]{title_fr}[/b]" if title_fr else None
        explanation_msg = f"{explanation_fr}" if explanation_fr else None
        hdurl_msg = f"[i]L'image en HD: {hdurl}[/i]" if hdurl else None

        msg = "\n\n".join(
            [x for x in [image_msg, title_msg, explanation_msg, hdurl_msg] if x != None]
        )

        await apod.post_message(f"[center]{msg}[/center]")

    @apod.command("apod")
    async def manual(msg: Message, _):  # pyright: ignore[reportUnusedFunction]
        if msg.username == admin:
            await on_apod()

    @apod.task(CronTrigger(hour=7))
    async def cron():  # pyright: ignore[reportUnusedFunction]
        await on_apod()

    return apod
