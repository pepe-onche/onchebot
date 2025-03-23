import asyncio
import logging
import re
import traceback
from datetime import datetime
from typing import IO, Any
from zoneinfo import ZoneInfo

import aiohttp
from aiolimiter import AsyncLimiter
from bs4 import BeautifulSoup
from bs4.element import Tag

from onchebot.models import Message, Topic, User

logger = logging.getLogger("onche")

upload_rate_limit = AsyncLimiter(1, 22)
rate_limit = AsyncLimiter(1, 8)

TOPICS_CACHE_SIZE = 100


class OncheTopic:
    def __init__(self, id: int, name: str, soup: Tag):
        self.id: int = id
        self.name: str = name
        self.soup: Tag = soup
        self.last_page: int = self.get_last_page()
        self.token: str = self.get_token()
        self.title: str = self.get_title()
        self.forum_id: int = -1

    def to_model(self) -> Topic:
        return Topic(
            id=self.id, name=self.name, title=self.title, forum_id=self.forum_id
        )

    def get_last_page(self) -> int:
        items = self.soup.find("div", class_="pagination")

        if not isinstance(items, Tag):
            try:
                logger.error(
                    f"Could not find pagination on topic {self.name} ({self.id})"
                )
            except:
                pass
            return 1

        items = items.find_all("a")
        return int(
            [e.get_text() for e in items if isinstance(e, Tag) and e.get_text()][-1]
        )

    def get_title(self) -> str:
        h1 = self.soup.select_one("div#topic>.title>a>h1")
        if not h1:
            return ""
        return h1.get_text()

    def get_forum_id(self) -> int:
        try:
            reg = r"https://onche.org/forum/([0-9]+)"
            a = self.soup.select_one("div#topic>.title>a")
            if not a:
                return 1
            href = a["href"]
            if not isinstance(href, str):
                return 1
            match = re.match(reg, href)
            if match:
                return int(match.group(1))
        except:
            pass
        return 1

    def get_token(self) -> str:
        item = self.soup.find("input", attrs={"name": "token", "type": "hidden"})
        if not isinstance(item, Tag):
            return ""

        value = item.get("value", "")
        if not isinstance(value, str):
            return ""

        return value

    def soup_to_msg(self, soup: Tag) -> Message | None:
        raw_id = soup["data-id"]
        if not isinstance(raw_id, str):
            return None

        id = int(raw_id)
        content_soup = soup.select_one(
            f'div.message[data-id="{id}"] > div.message-content'
        )
        if not content_soup:
            return None
        signature = content_soup.select_one(".signature")
        if signature:
            signature.extract()
        answer = soup.select_one(f'div.message[data-id="{id}"] > div.message.answer')
        answer_id: int | None = None
        if answer:
            raw_answer_id = answer["data-id"]
            if isinstance(raw_answer_id, str):
                answer_id = int(raw_answer_id)

        def parse_datetime(soup: Tag):
            date: Tag | None = soup.select_one(
                f'div.message[data-id="{id}"] > div.message-bottom > div.message-date'
            )
            if not date:
                return None
            date_text = date["title"]
            if not isinstance(date_text, str):
                return None
            r = re.compile(
                r".*(?P<day>\d\d)\/(?P<month>\d\d)\/(?P<year>\d\d\d\d).*(?P<hour>\d\d)\:(?P<minute>\d\d)\:(?P<second>\d\d).*"
            )
            match = r.match(date_text)
            if match:
                d = match.groupdict()
                return datetime(
                    int(d["year"]),
                    int(d["month"]),
                    int(d["day"]),
                    int(d["hour"]),
                    int(d["minute"]),
                    int(d["second"]),
                    tzinfo=ZoneInfo("Europe/Paris"),
                )
            return None

        def soup_parse_special(soup: Tag):
            s = BeautifulSoup("", "html.parser")
            for img in soup.select("div.sticker"):
                name = img["data-name"]
                if not isinstance(name, str):
                    continue
                newspan = s.new_tag("span")
                newspan.string = ":" + name + ":"
                img.replace_with(newspan)
            return soup

        dt = parse_datetime(soup)
        if not dt:
            return None

        stickers: list[str] = []
        for sticker in content_soup.select("div.sticker"):
            name = sticker["data-name"]
            if isinstance(name, str):
                stickers.append(name)

        raw_username = soup.find("a", class_="message-username")
        if not isinstance(raw_username, Tag):
            return None

        return Message(
            id=id,
            answer_to=answer_id,
            stickers=stickers,
            mentions=[
                mention.get_text()[1:].lower()
                for mention in content_soup.select("a._format._mention")
            ],
            content_html=content_soup.decode_contents(),
            content_without_stickers=content_soup.get_text().strip(),
            content=soup_parse_special(content_soup).get_text().strip(),
            username=raw_username.get_text(),
            topic_id=int(self.id),
            timestamp=int(dt.timestamp()),
        )

    def is_logged(self, soup: Tag) -> bool:
        return soup.find(id="account-button") != None


class NotLoggedInError(Exception):
    pass


class NotFoundError(Exception):
    pass


class NotPostedError(Exception):
    pass


class Onche:
    def __init__(self, username: str | None = None, password: str | None = None):
        self.username: str | None = username
        self.password: str | None = password
        self.topics: list[OncheTopic] = []
        self._cookie: str = ""

    @property
    def cookie(self):
        return self._cookie

    @cookie.setter
    def cookie(self, new_cookie: str):
        self._cookie = new_cookie
        self.topics = []  # Clear the topics cache whevener the cookie changes

    def get_headers(self):
        return {
            "Cookie": self.cookie,
        }

    async def init_topic(self, topic_id: int) -> OncheTopic:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://onche.org/topic/{topic_id}", headers=self.get_headers()
            ) as resp:
                res = await resp.text()
                soup = BeautifulSoup(res, "html.parser")
                suffix = resp.url.path[len(f"/topic/{topic_id}/") :]
                end = suffix.find("/")
                topic = OncheTopic(topic_id, suffix[:end] if end > 0 else suffix, soup)
                await self._update_topic(topic)
                self.topics = list(filter(lambda t: t.id != topic_id, self.topics))
                self.topics.append(topic)
                if len(self.topics) > TOPICS_CACHE_SIZE:
                    self.topics.pop(0)
                logger.info(f"Found topic {topic.name} ({topic.id})")
                return topic

    async def lazy_get_topic(self, topic_id: int) -> OncheTopic:
        try:
            cached_topic = next(topic for topic in self.topics if topic.id == topic_id)
        except:
            cached_topic = None

        return (
            cached_topic
            if cached_topic is not None
            else await self.init_topic(topic_id)
        )

    async def get_user(self, username: str) -> User | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://onche.org/profil/{username.lower()}",
                    headers=self.get_headers(),
                ) as resp:
                    res = await resp.text()
                    soup = BeautifulSoup(res, "html.parser")
                    div = soup.find("div", class_="profile-cover-username")
                    if not div:
                        return None

                    return User(username=div.text.strip())
        except:
            return None

    async def _update_topic(self, topic: OncheTopic):
        topic.soup = await self._fetch_messages(topic, topic.last_page)
        topic.last_page = topic.get_last_page()
        topic.token = topic.get_token()
        topic.title = topic.get_title()
        topic.forum_id = topic.get_forum_id()

    def _free_topic(self, topic_id: int):
        try:
            topic_index = next(
                i for (i, topic) in enumerate(self.topics) if topic.id == topic_id
            )
            self.topics.pop(topic_index)
        except:
            pass

    async def _fetch_messages(self, topic: OncheTopic, page: int) -> BeautifulSoup:
        url = f"https://onche.org/topic/{topic.id}/{topic.name}/{page}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.get_headers()) as resp:
                if resp.status != 200 and resp.status != 404:
                    logger.error(
                        f"Error while fetching topic {topic.name} page {page} (status {resp.status}), will retry in 20 secs"
                    )
                    await asyncio.sleep(20)
                    return await self._fetch_messages(topic, page)

                if resp.status == 404:
                    logger.error(f"404 - {topic.id} - {topic.name}")
                    logger.error(await resp.text())
                    raise NotFoundError()

                logger.debug(f"Fetched topic {topic.name} page {page}")
                res = await resp.text()
                soup = BeautifulSoup(res, "html.parser")
                return soup

    async def fetch_messages(self, topic_id: int, page: int) -> list[Message]:
        topic = await self.lazy_get_topic(topic_id)
        soup = await self._fetch_messages(topic, page)
        if not soup:
            return []
        topic.soup = soup
        topic.last_page = topic.get_last_page()
        topic.token = topic.get_token()
        messages = [
            topic.soup_to_msg(s)
            for s in topic.soup.select("div.messages > div.message")
        ]
        filtered_messages = [m for m in messages if isinstance(m, Message)]

        return filtered_messages

    async def post_message(
        self, topic_id: int, content: str, answer_to: Message | None = None
    ) -> int:
        logger.info("Posting message...")
        topic = await self.lazy_get_topic(topic_id)

        async with rate_limit:
            data = {"message": content, "token": topic.get_token()}
            if answer_to is not None:
                data["answer"] = str(answer_to.id)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://onche.org/topic/{topic.id}/{topic.name}/{topic.last_page}",
                    data=data,
                    headers=self.get_headers(),
                ) as resp:
                    res = await resp.text()
                    soup = BeautifulSoup(res, "html.parser")
                    if not self.is_logged(soup):
                        raise NotLoggedInError()

                    reply = f" (reply to {answer_to.id})" if answer_to else ""
                    logger.info(f"Message posted{reply}:\n{content}")
                    return resp.status

    async def get_upload_token(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://onche.org/forum/1/blabla-general", headers=self.get_headers()
            ) as response:
                res = await response.text()
                soup = BeautifulSoup(res, "html.parser")
                item = soup.find("input", id="insert-image-input")
                if item == None:
                    return ""
                if not isinstance(item, Tag):
                    return ""

                raw = item.get("data-token", "")
                if not isinstance(raw, str):
                    return ""

                return raw

    async def upload_image(
        self,
        data: IO[Any] | bytes | str,
        filename: str,
        content_type: str,
    ) -> str | None:
        async with upload_rate_limit:
            token = await self.get_upload_token()

            formdata = aiohttp.FormData()
            formdata.add_field(
                "file", value=data, filename=filename, content_type=content_type
            )
            formdata.add_field("token", value=token)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://onche.org/upload",
                    data=formdata,
                    headers=self.get_headers(),
                ) as response:
                    if response.status == 200:
                        return str((await response.json())["image"])
                    if response.status == 400:
                        raise NotLoggedInError()

                    logger.error(f"{response.status}: {await response.text()}")

    def is_logged(self, soup: Tag) -> bool:
        return soup.find(id="account-button") != None

    async def login(self) -> str | None:
        if not self.username or not self.password:
            raise Exception("Trying to log in without a username or password")

        logger.info(f"Logging in to {self.username}...")
        await asyncio.sleep(3)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://onche.org/account/login",
                ) as resp:
                    res = await resp.text()
                    soup = BeautifulSoup(res, "html.parser")
                    captcha = soup.select_one("div.h-captcha")
                    if captcha:
                        raise Exception("Aborted log in because of captcha")
                    input = soup.select_one('input[name="token"]')
                    token = str(input["value"]) if input else None
                    if not token:
                        return ""

                data = {
                    "login": self.username,
                    "password": self.password,
                    "token": token,
                }
                async with session.post(
                    f"https://onche.org/account/login",
                    data=data,
                ) as resp:
                    auth = None
                    sess = None
                    for cookie in session.cookie_jar:
                        if cookie.key == "auth":
                            auth = cookie.value
                        if cookie.key == "sess":
                            sess = cookie.value

                    cookie = "auth=" + str(auth) + "; sess=" + str(sess)
                    self.cookie = cookie
                    logger.info(f"Logged in as {self.username}")
                    logger.info(f"Cookie: {self.cookie}")
                    return cookie
        except Exception:
            logger.error("error while login:")
            logger.error(traceback.format_exc())

        return None
