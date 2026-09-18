from dotenv import load_dotenv
import os

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GULID_ID = int(os.getenv("GUILD_ID"))