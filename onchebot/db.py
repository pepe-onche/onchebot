from tortoise import Tortoise

import onchebot.globals as g


async def init():
    await Tortoise.init(db_url=g.config.db_url, modules={"models": ["onchebot.models"]})
    await Tortoise.generate_schemas(safe=True)
