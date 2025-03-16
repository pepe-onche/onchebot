import onchebot
from onchebot.bot import Bot
from onchebot.models import Message, User

from supabase import create_client, Client


def create(id: str, user: User, topic_id: int, supabase_url: str, supabase_key: str) -> Bot:
    supabase: Client = create_client(supabase_url, supabase_key)

    tamagonche = onchebot.add_bot(id, user, topic_id)

    @tamagonche.command("nourrir")
    async def feed(msg: Message, _):  # pyright: ignore[reportUnusedFunction]
        try:
            supabase.table("actions").insert({"type": "feed", "username": msg.username, "pet_id": 1}).execute()
        except:
            pass

    @tamagonche.command("nettoyer")
    async def clean_trash(msg: Message, _):  # pyright: ignore[reportUnusedFunction]
        try:
            supabase.table("actions").insert({"type": "clean_trash", "username": msg.username, "pet_id": 1}).execute()
        except:
            pass

    @tamagonche.command("doliprane")
    async def give_medicine(msg: Message, _):  # pyright: ignore[reportUnusedFunction]
        try:
            supabase.table("actions").insert({"type": "give_medicine", "username": msg.username, "pet_id": 1}).execute()
        except:
            pass

    return tamagonche
