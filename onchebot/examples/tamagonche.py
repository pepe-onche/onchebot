import onchebot
from onchebot.bot import Bot
from onchebot.models import Message, User

from supabase import create_client, Client


def create(id: str, user: User, topic_id: int, supabase_url: str, supabase_key: str) -> Bot:
    supabase: Client = create_client(supabase_url, supabase_key)

    tamagonche = onchebot.add_bot(id, user, topic_id, default_state={"count": 0})

    @tamagonche.command("nourrir")
    async def feed(msg: Message, _):  # pyright: ignore[reportUnusedFunction]
        response = (
            supabase.table("pets")
            .select("*")
            .eq("id", 1)
            .execute()
        )
        if len(response.data) <= 0:
            return

        status = str(response.data[0]["status"])
        food_level = int(response.data[0]["food"])
        max_food = int(response.data[0]["max_food"])

        # If dead
        if food_level <= 0 or status == "dead":
            return

        # If food level is full
        if food_level >= max_food:
            return

        # Add action
        response = (
            supabase.table("actions")
            .insert({"type": "feed", "username": msg.username, "pet_id": 1})
            .execute()
        )

    return tamagonche
