import traceback

import discord
from discord.ext import commands
from bot.db.database import get_connection
from bot.config import ADMIN_ROLE_ID

class RejectionModal(discord.ui.Modal, title="Reason for rejection"):
    reason = discord.ui.TextInput(label="Reason", style=discord.TextStyle.paragraph)

    def __init__(self, submission_id, original_message):
        super().__init__()
        self.submission_id = submission_id
        self.original_message = original_message

    async def on_submit(self, interaction: discord.Interaction):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE submissions
                SET status = 'rejected', rejection_reason = ?, reviewed_by = ?, reviewed_at = datetime('now')
                WHERE id = ?
            """, (str(self.reason), interaction.user.id, self.submission_id))
            conn.commit()
        finally:
            conn.close()

        await self.original_message.edit(content=f"❌ Rejected by {interaction.user.name}: {self.reason}", view=None)
        await interaction.response.send_message("Rejection recorded.", ephemeral=True)

class ApprovalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        return any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="bingo_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_admin(interaction):
            await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
            return

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, team_id, tile_id FROM submissions WHERE message_id = ?", (interaction.message.id,))
            row = cur.fetchone()
            if row is None:
                await interaction.response.send_message(
                    "Couldn't find a submission for this message -- it may be out of sync.", ephemeral=True
                )
                return

            cur.execute("""
                UPDATE submissions SET status = 'approved', reviewed_by = ?, reviewed_at = datetime('now')
                WHERE id = ?
            """, (interaction.user.id, row["id"]))

            cur.execute("""
                INSERT INTO team_tile_status (team_id, tile_id, completed, completed_at)
                VALUES (?, ?, 1, datetime('now'))
                ON CONFLICT(team_id, tile_id) DO UPDATE SET completed = 1, completed_at = datetime('now')
            """, (row["team_id"], row["tile_id"]))

            conn.commit()
        finally:
            conn.close()

        await interaction.response.edit_message(content=f"✅ Approved by {interaction.user.name}", view=None)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red, custom_id="bingo_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_admin(interaction):
            await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
            return

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM submissions WHERE message_id = ?", (interaction.message.id,))
            row = cur.fetchone()
            if row is None:
                await interaction.response.send_message(
                    "Couldn't find a submission for this message -- it may be out of sync.", ephemeral=True
                )
                return
        finally:
            conn.close()

        await interaction.response.send_modal(RejectionModal(row["id"], interaction.message))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        traceback.print_exception(type(error), error, error.__traceback__)
        if not interaction.response.is_done():
            await interaction.response.send_message("Something went wrong. Check the logs.", ephemeral=True)

class Approvals(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(Approvals(bot))