import discord
from discord.ext import commands
from discord import app_commands
from bot.db.database import get_connection

class Register(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='register', description='Register a player to a team')
    async def register(self, interaction: discord.Interaction, osrs_name: str):
        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute("SELECT id, role_id, name FROM teams")
            all_teams = cur.fetchall()

            member_role_ids = {role.id for role in interaction.user.roles}

            matched_teams = [t for t in all_teams if t["role_id"] in member_role_ids]

            if len(matched_teams) == 0:
                await interaction.response.send_message("You don't have a team role yet. Ask an admin to assign you one.")
                conn.close()
                return
            if len(matched_teams) > 1:
                await interaction.response.send_message("You have more than one team role. Ask an admin to fix this.")
                conn.close()
                return

            team_id = matched_teams[0]["id"]
            team_name = matched_teams[0]["name"]

            cur.execute("""
                INSERT INTO players (discord_id, discord_username, osrs_name, team_id)
                VALUES (?, ?, ?, ?)
            """, (interaction.user.id, interaction.user.name, osrs_name, team_id))

            conn.commit()
        finally:
            conn.close()

        await interaction.response.send_message(f"Sucessfully added {interaction.user.name} to {team_name}")

async def setup(bot):
    await bot.add_cog(Register(bot))