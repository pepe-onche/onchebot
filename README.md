# Onchebot

Librairie python pour la création de bots pour onche dot org ![](https://risibank.fr/cache/medias/0/29/2940/294046/thumb.png)

## Avertissement

Ne soit pas un enculin, n'utilise pas cette librairie pour spam (sinon cancer) ![](https://risibank.fr/cache/medias/0/18/1851/185193/thumb.png)

## Avant de commencer

Il te faut:

- Au moins 80 de QI
- Python >= 3.11
- [Redis](https://redis.io/downloads/)
- Un pseudo onche assez haut niveau pour ne pas avoir de captcha

## Installation

```shell
pip install onchebot
```

## Guide

> Je suis con, je fais quoi ? ![](https://risibank.fr/cache/medias/0/28/2844/284448/thumb.png)

Ne t'inquiètes pas c'est très simple ![](https://risibank.fr/cache/medias/0/25/2556/255695/thumb.png)

Voici le code pour un bot qui va lire un topic et poster "PONG" en réponse à un message qui contient "/ping":

```python
import onchebot

risitas = onchebot.add_user(username="Risitas", password="ElMuchacho") # 1

bot = onchebot.add_bot( # 2
    id="pingpong",
    user=risitas,
    topic_id=759451
)

@bot.command("ping") # 3
async def send_pong(msg, args):
    await bot.post_message("PONG", answer_to=msg)

onchebot.start() # 4
```

En résumé:

1. On ajoute le pseudo et le mot de passe du compte onche qui va poster (je conseille de ne pas mettre ton pseudo principal, ça risque de te déconnecter quand tu onches normalement)
2. On crée le bot, il nous faut:

   - l'identifiant du bot: tu mets ce que tu veux, mais ne le change pas une fois que le bot est créé, et il doit être UNIQUE à chaque bot
   - le compte qui va poster
   - l'identifiant du topic: le lien d'un topic ressemble à https://onche.org/topic/12345/coucou, c'est le nombre après /topic/

3. On définit le comportement du bot:

   - Quand il reçoit la commande "ping", la fonction `send_pong` va se lancer
   - `bot.post_message` va poster un message sur le topic, l'argument `answer_to` fait que le message posté est une réponse à un autre message, ici le message qui contient la commande ping

4. On lance onchebot

On a un bot fonctionnel en seulement quelques lignes de python, c'est pas beau la vie ? ![](https://risibank.fr/cache/medias/0/7/705/70589/thumb.png)

Tu peux faire plusieurs bots dans le même programme.

L'argument `args` contient la liste de "mots" après "/ping" dans le message, par exemple si le message est "/ping mange mon cul" alors `args` est `["mange", "mon", "cul"]`.

### Réagir aux messages sans commandes

Tu peux réagir à n'importe quel nouveau message du topic avec le décorateur `@bot.on_message()`:

```python
import onchebot

risitas = onchebot.add_user(username="Risitas", password="ElMuchacho")

bot = onchebot.add_bot(
    id="prout",
    user=risitas,
    topic_id=759451
)

@bot.on_message()
async def caca(msg):
    print(f"Nouveau message de {msg.username}: {msg.content}")

onchebot.start()
```

Ici la fonction `caca` est appelée pour chaque message sur le topic #759451, peu importe si il contient une commande ou non.

### L'état

Les bots ont un état (un `state`) qui est sauvegardé, même après que le programme redémarre. Utilise le pour toutes les variables qui ne sont pas temporaire.

Un exemple d'un bot qui ajoute 1 à chaque commande "/+1":

```python
import onchebot

risitas = onchebot.add_user(username="Risitas", password="ElMuchacho")

bot = onchebot.add_bot(
    id="counter",
    user=risitas,
    topic_id=759451,
    default_state={"count": 0}
)

@bot.command("+1")
async def add_one(msg, args):
    bot.state["count"] += 1
    await bot.post_message(f"Le compteur est maintenant à: {bot.get_state('count')}", answer_to=msg)

onchebot.start()
```

Notre compteur ne retourne pas à zéro quand le programme est redémarré ![](https://risibank.fr/cache/medias/0/0/21/2158/thumb.png)

Tu peux utiliser `bot.state` (un dict sérialisable en json), ou les fonctions `bot.get_state` et `bot.set_state`

### Les tâches

Si tu veux poster un message sans réagir à un message mais en fonction du temps (comme [ce topax](https://onche.org/topic/772195/l-image-d-astronomie-du-jour) par exemple), tu peux utiliser le décorateur `bot.task()`.

Onchebot intègre les [triggers de apscheduler](https://apscheduler.readthedocs.io/en/3.x/), par exemple:

```python
import onchebot
from apscheduler.triggers.cron import CronTrigger

risitas = onchebot.add_user(username="Risitas", password="ElMuchacho")

bot = onchebot.add_bot(
    id="elcon",
    user=risitas,
    topic_id=759451
)

@bot.task(CronTrigger(hour=12))
async def post():
    await bot.post_message("C'EST MIDI")

onchebot.start()
```

Ce bot va poster "C'EST MIDI" sur le topic #759451 tous les jours à midi ![](https://risibank.fr/cache/medias/0/18/1853/185320/thumb.png)

### Les modules

Un module est un groupe de commandes, état, et tâches, que tu peux réutiliser dans plusieurs bots.

Onchebot en a quelque uns, `Misc` contient des commandes à la con comme "insulte" ou "love". `Vote` contient un système de vote simple.

Ils sont ajouté dans un bot dans la fonction `add_bot`:

```python
import onchebot
from onchebot.modules import Misc

risitas = onchebot.add_user(username="Risitas", password="ElMuchacho")

bot = onchebot.add_bot(
    id="carabistouille",
    user=risitas,
    topic_id=123,
    modules=[Misc(admin="Prout")]
)

onchebot.start()
```

Ils peuvent avoir des paramètres, `Misc` a besoin du paramètre `admin`, qui est un pseudo qui ne peut pas être insulté ![](https://risibank.fr/cache/medias/0/29/2952/295294/thumb.png)

### Prometheus et Loki

Onchebot exporte des metrics prometheus, que tu peux utiliser pour te faire un dashboard ![](https://risibank.fr/cache/medias/0/14/1488/148834/thumb.png)

Il peut aussi envoyer ses logs à loki.

### La fonction `onchebot.setup()`

Tu auras peut-être besoin de changer des paramètres (comme le port pour se connecter à redis), dans ce cas tu peux appeler `onchebot.setup()` (idéalement tout en haut, après les imports).

Les paramètres par défaut:

```python
onchebot.setup(
    redis_host: str = "localhost",
    redis_port: int = 6379,
    redis_username: Optional[str] = None,
    redis_password: Optional[str] = None,
    prometheus_host: str = "localhost",
    prometheus_port: int = 9464,
    loki_url: Optional[str] = None,
)
```

## Les exemples

Tu peux aller voir les [exemples](onchebot/examples/) (des bots crées dans une fonction `create`) si besoin.

L'exemple [apod.py](onchebot/examples/apod.py) contient le code pour le [topic de l'image d'astronomie du jour](https://onche.org/topic/772195/l-image-d-astronomie-du-jour) ![](https://risibank.fr/cache/medias/0/29/2968/296894/thumb.png)

## Comment ça marche

Onchebot est en deux parties: [producer](onchebot/producer.py) et [consumer](onchebot/consumer.py).

Le _producer_ va aller chercher les messages et topics sur onche et les envoyer dans des streams redis.

Le _consumer_ va lire les streams redis, et executer le comportement des bots que tu as défini.

Ils sont lancés dans deux threads différents ![](https://risibank.fr/cache/medias/0/5/521/52158/thumb.png)
