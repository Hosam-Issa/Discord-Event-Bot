import os
import discord
from discord.ext import commands
from discord import app_commands
from bot.db.database import get_connection, get_all_team_scores, get_top_players_for_team
from bot.config import ADMIN_ROLE_ID, LEADERBOARD_CHANNEL_ID
from bot.rendering.board_image import render_team_board

os.makedirs('images/boards', exist_ok=True)

# Combines get_top_players_for_team (per-team query) across every team into one
# structure the embed-building function can consume directly.
def get_top_players_grouped():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM teams")
        teams = cur.fetchall()
    finally:
        conn.close()

    result = []
    for team in teams:
        top_players = get_top_players_for_team(team["id"], limit=3)
        result.append({"team_name": team["name"], "players": top_players})

    return result

def build_team_scores_embed(team_scores):
    # team_scores is already sorted DESC by get_all_team_scores, so enumerate()
    # gives the correct rank directly.
    lines = [
        f"{i+1}. **{team['team_name']}** — {team['score']} pts"
        for i, team in enumerate(team_scores)
    ]
    embed = discord.Embed(
        title="🏆 Team Standings",
        description="\n".join(lines),
        color=discord.Color.gold()
    )
    return embed

def build_player_leaderboard_embed(top_players_by_team):
    embed = discord.Embed(title="Player Standings", color=discord.Color.from_rgb(192, 192, 192))

    for team in top_players_by_team:
        if team["players"]:
            lines = [
                f"{i+1}. {p['osrs_name']} — {p['score']} pts"
                for i, p in enumerate(team["players"])
            ]
            value = "\n".join(lines)
        else:
            value = "No submissions yet"

        # inline=False -> one team per row, rather than packing up to 3 per row.
        embed.add_field(name=team["team_name"], value=value, inline=False)

    return embed

# Called after every approval to keep the posted board image and both leaderboard
# embeds in sync with the database. Looks up each message by its stored id rather
# than holding a reference, since this can be called long after the messages were
# first posted (even across bot restarts).
async def refresh_leaderboards(guild, team_id):
    leaderboard_channel = guild.get_channel(LEADERBOARD_CHANNEL_ID)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT message_id FROM leaderboard_messages WHERE key = ?", (f"team_board:{team_id}",))
        board_row = cur.fetchone()
        cur.execute("SELECT message_id FROM leaderboard_messages WHERE key = 'team_scores'")
        scores_row = cur.fetchone()
        cur.execute("SELECT message_id FROM leaderboard_messages WHERE key = 'player_leaderboard'")
        players_row = cur.fetchone()
    finally:
        conn.close()

    # Each block is guarded independently in case /setup_leaderboard hasn't been run yet
    # (no stored message ids) — avoids crashing the whole approval flow over a missing message.
    if board_row:
        output_path = f"images/boards/team_{team_id}.png"
        render_team_board(team_id, output_path)  # re-renders from scratch using current completion state
        board_msg = await leaderboard_channel.fetch_message(board_row["message_id"])
        await board_msg.edit(attachments=[discord.File(output_path)])

    if scores_row:
        scores_msg = await leaderboard_channel.fetch_message(scores_row["message_id"])
        await scores_msg.edit(embed=build_team_scores_embed(get_all_team_scores()))

    if players_row:
        players_msg = await leaderboard_channel.fetch_message(players_row["message_id"])
        await players_msg.edit(embed=build_player_leaderboard_embed(get_top_players_grouped()))

class Leaderboards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # One-time (or re-runnable) admin setup: posts the initial boards + leaderboard
    # messages and records their ids so refresh_leaderboards can find them later.
    @app_commands.command(name="setup_leaderboard", description="Post or refresh boards and leaderboards (admin only)")
    async def setup_leaderboard(self, interaction: discord.Interaction):
        if not any (role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("You don't have permission to do this", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)  # posting 6 messages takes a moment

        channel = interaction.guild.get_channel(LEADERBOARD_CHANNEL_ID)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM teams")
            teams = cur.fetchall()

            # Post one board image per team, saving each message's id under a
            # per-team key so future refreshes know which message to edit.
            for team in teams:
                output_path = f"images/boards/team_{team['id']}.png"
                render_team_board(team["id"], output_path)
                key = f"team_board:{team['id']}"

                cur.execute("SELECT message_id FROM leaderboard_messages WHERE key = ?", (key,))
                existing = cur.fetchone()

                if existing:
                    # Message already posted — try to edit it in place instead of posting a new one.
                    try:
                        msg = await channel.fetch_message(existing["message_id"])
                        await msg.edit(content=f"**{team['name']}**", attachments=[discord.File(output_path)])
                    except discord.NotFound:
                        # The old message was deleted manually — fall back to posting a fresh one.
                        msg = await channel.send(content=f"**{team['name']}**", file=discord.File(output_path))
                else:
                    msg = await channel.send(content=f"**{team['name']}**", file=discord.File(output_path))
                    
                # Upsert: lets this command be safely re-run without erroring on duplicate keys.
                cur.execute("""
                    INSERT INTO leaderboard_messages (key, message_id) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET message_id = excluded.message_id
                """, (key, msg.id))

            for key, embed_builder, args in [
                ("team_scores", build_team_scores_embed, (get_all_team_scores(),)),
                ("player_leaderboard", build_player_leaderboard_embed, (get_top_players_grouped(),)),
            ]:
                cur.execute("SELECT message_id FROM leaderboard_messages WHERE key = ?", (key,))
                existing = cur.fetchone()
                embed = embed_builder(*args)

                if existing:
                    try:
                        msg = await channel.fetch_message(existing["message_id"])
                        await msg.edit(embed=embed)
                    except discord.NotFound:
                        msg = await channel.send(embed=embed)
                else:
                    msg = await channel.send(embed=embed)

                cur.execute("""
                    INSERT INTO leaderboard_messages (key, message_id) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET message_id = excluded.message_id
                """, (key, msg.id))

            conn.commit()
        finally:
            conn.close()

        await interaction.followup.send("Leaderboard setup complete.", ephemeral=True)

    @app_commands.command(name="refresh_board", description="Manually refresh a team's board and leaderboards (admin only)")
    @app_commands.describe(team_id="The team's internal ID")
    async def refresh_board(self, interaction: discord.Interaction, team_id: int):
        if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await refresh_leaderboards(interaction.guild, team_id)
        await interaction.followup.send(f"Refreshed leaderboards for team {team_id}.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Leaderboards(bot))