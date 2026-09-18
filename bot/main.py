import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
from bot.db.database import get_connection, init_db
from bot.db.seed import seed_if_needed
from bot.config import DISCORD_TOKEN, GUILD_ID

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

init_db()
seed_if_needed()

@bot.event
async def on_ready():
    await bot.load_extension("bot.cogs.submissions")
    await bot.load_extension("bot.cogs.teams")

    bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
    synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Successfully synced {len(synced)} commands.")

bot.run(os.getenv("DISCORD_TOKEN"))