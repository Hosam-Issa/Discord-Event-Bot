import discord
from discord.ext import commands
from bot.db.database import init_db
from bot.db.seed import seed_if_needed
from bot.config import DISCORD_TOKEN, GUILD_ID
from bot.cogs.approvals import ApprovalView

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

init_db()
seed_if_needed()

@bot.event
async def on_ready():
    await bot.load_extension("bot.cogs.submissions")
    await bot.load_extension("bot.cogs.teams")
    await bot.load_extension("bot.cogs.approvals")
    await bot.load_extension("bot.cogs.leaderboards")
    bot.add_view(ApprovalView())

    bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
    synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Successfully synced {len(synced)} commands.")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if not interaction.response.is_done():
        await interaction.response.send_message("Something went wrong. Please try again later or contact an admin.", ephemeral=True)
    print(f"Command error: {error}")

bot.run(DISCORD_TOKEN)