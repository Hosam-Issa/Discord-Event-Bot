import discord
from discord.ext import commands
from discord import app_commands
from bot.db.database import get_connection
import os

os.makedirs('images/submissions', exist_ok=True)

# Placeholder tile choices, change to actual tiles on use
TILE_CHOICES = [
    app_commands.Choice(name=f"Tile {i}", value=i)
    for i in range(25) if i != 12
]

class Submissions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='submit', description='Command to submit drops.')
    @discord.app_commands.describe(
        tile='Which tile this drop is for',
        drop_name='Name of the drop',
        image='Screenshot of the drop'
    )
    @app_commands.choices(tile=TILE_CHOICES)
    async def submission(
        self, 
        interaction: 
        discord.Interaction, 
        tile: app_commands.Choice[int], 
        drop_name: str, 
        image: discord.Attachment
    ):
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id, team_id FROM players WHERE discord_id = ?", (interaction.user.id,))
        player_row = cur.fetchone()
        if player_row is None:
            await interaction.response.send_message("You're not registered yet, ask an admin to add you to a team.")
            conn.close()
            return

        player_id = player_row["id"]
        team_id = player_row["team_id"]

        cur.execute("SELECT id FROM tiles WHERE position = ?", (tile.value,))
        tile_row = cur.fetchone()
        tile_id = tile_row["id"]

        save_path = f'images/submissions/submission_{player_id}_{tile_id}.png'
        await image.save(save_path)

        cur.execute("""
            INSERT INTO submissions (tile_id, team_id, player_id, drop_name, image_path, submitted_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (tile_id, team_id, player_id, drop_name, save_path))

        conn.commit()
        conn.close()

        await interaction.response.send_message("Drop submitted, awaiting admin review.")

async def setup(bot):
    await bot.add_cog(Submissions(bot))