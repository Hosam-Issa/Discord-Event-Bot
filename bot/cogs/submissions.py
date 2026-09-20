import discord
from discord.ext import commands
from discord import app_commands
from bot.db.database import get_connection
import os
from bot.config import ADMIN_CHANNEL_ID
from bot.cogs.approvals import ApprovalView

os.makedirs('images/submissions', exist_ok=True)  # ensure the folder exists before any save() call

# Discord requires a fixed list of choices for the "tile" dropdown — 0 to 24, minus the
# free center tile (12), which players never need to submit for.
TILE_CHOICES = [
    app_commands.Choice(name=f"Tile {i}", value=i)
    for i in range(25) if i != 12
]

class Submissions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='submit', description='Command to submit drops.')
    @app_commands.describe(
        tile='Which tile this drop is for',
        drop_name='Name of the drop',
        image='Screenshot of the drop'
    )
    @app_commands.choices(tile=TILE_CHOICES)
    async def submission(
        self, 
        interaction: discord.Interaction, 
        tile: app_commands.Choice[int], 
        drop_name: str, 
        image: discord.Attachment
    ):
        # Defer immediately — this command does several DB queries plus an image save
        # plus a second Discord send, which can easily exceed Discord's 3-second window.
        await interaction.response.defer(ephemeral=True)
        
        try:
            conn = get_connection()
            cur = conn.cursor()

            # Look up the submitter's internal player record via their Discord id.
            cur.execute("SELECT id, team_id, osrs_name FROM players WHERE discord_id = ?", (interaction.user.id,))
            player_row = cur.fetchone()
            if player_row is None:
                await interaction.response.send_message("You're not registered yet, ask an admin to add you to a team.")
                conn.close()
                return

            player_id = player_row["id"]
            team_id = player_row["team_id"]

            # Convert the chosen tile *position* (what the player picked) into the tile's
            # internal database id (what the foreign keys actually reference).
            cur.execute("SELECT id FROM tiles WHERE position = ?", (tile.value,))
            tile_row = cur.fetchone()
            tile_id = tile_row["id"]

            # Save the screenshot locally rather than relying on Discord's CDN link,
            # which can expire — filename ties it back to the player + tile for traceability.
            save_path = f'images/submissions/submission_{player_id}_{tile_id}.png'
            await image.save(save_path)

            # Insert the new pending submission row.
            cur.execute("""
                INSERT INTO submissions (tile_id, team_id, player_id, drop_name, image_path, submitted_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (tile_id, team_id, player_id, drop_name, save_path))

            conn.commit()
            submission_id = cur.lastrowid  # the id SQLite just generated for this row
        finally:
            conn.close()

        # Post the submission to the admin review channel with Approve/Reject buttons attached.
        admin_channel = interaction.guild.get_channel(ADMIN_CHANNEL_ID)
        sent_message = await admin_channel.send(
            content=f"{drop_name} posted by {player_row['osrs_name']}",
            file=discord.File(save_path),
            view=ApprovalView()
        )

        # Record which Discord message corresponds to this submission, so the button
        # callbacks can look it up later (including after a bot restart).
        conn2 = get_connection()
        try:
            cur2 = conn2.cursor()
            cur2.execute("UPDATE submissions SET message_id = ? WHERE id = ?", (sent_message.id, submission_id))
            conn2.commit()
        finally:
            conn2.close()

        # Final reply goes through followup, not response.
        await interaction.followup.send("Drop submitted... Awaiting admin review.")

async def setup(bot):
    await bot.add_cog(Submissions(bot))