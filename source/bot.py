import discord
from discord.ext import commands
from discord.ext.commands import bot
import asyncio
import logging
import json

with open("./token.json", "r") as bot_token_file:
    bot_token_json = json.loads(bot_token_file.read())
    bot_token = bot_token_json["botToken"]


logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler("gotosleeplog.txt", "w", "utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(handler)

sleepingbot = commands.Bot("s!")

@sleepingbot.event
async def on_ready():
    print("Loading up...")
    print("My name is " + sleepingbot.user.name)
    print("My ID is " + str(sleepingbot.user.id))
    print("Roll out, autobots")
    await sleepingbot.change_presence(status="Oh god I'm alive")


@sleepingbot.command(pass_context=True)
async def sleep(ctx):
    await ctx.send("Go to sleep")

sleepingbot.run(bot_token)
