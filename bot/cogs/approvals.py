import traceback
import discord
from discord.ext import commands
from bot.db.database import get_connection
from bot.config import ADMIN_ROLE_ID
from bot.cogs.leaderboards import refresh_leaderboards

# Modal (pop-up form) shown to an admin when they click "Reject"
# collects a reason before the rejection is actually recorded.
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
            conn.close()  # always release the connection, even if the UPDATE fails

        # Edit the original admin-channel message to show the outcome, and remove the buttons
        # so this submission can't be approved/rejected a second time.
        await self.original_message.edit(content=f"❌ Rejected by {interaction.user.name}: {self.reason}", view=None)
        await interaction.response.send_message("Rejection recorded.", ephemeral=True)


# Persistent view (survives bot restarts) attached to every submission message in the
# admin channel. Buttons use fixed custom_ids so Discord can route clicks back to this
# view even after the bot process restarts — the actual submission is looked up via
# interaction.message.id, not stored on the view instance itself.
class ApprovalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # never expire — admins may review much later

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
            # Find which submission this button belongs to via the message it's attached to.
            cur.execute("SELECT id, team_id, tile_id FROM submissions WHERE message_id = ?", (interaction.message.id,))
            row = cur.fetchone()
            if row is None:
                # Defensive check — message exists but has no matching submission row
                # (could happen if data ever gets out of sync).
                await interaction.response.send_message(
                    "Couldn't find a submission for this message -- it may be out of sync.", ephemeral=True
                )
                return

            # Prevent double-approving the same tile for the same team (e.g. from
            # duplicate submissions) — this would otherwise double count in some
            # score calculations even though team_tile_status itself dedupes.
            cur.execute("""
                SELECT completed FROM team_tile_status WHERE team_id = ? AND tile_id = ?
            """, (row["team_id"], row["tile_id"]))
            existing = cur.fetchone()

            if existing and existing["completed"] == 1:
                await interaction.response.send_message(
                    "This tile is already marked complete for this team — approving again would double-count it."
                    "Reject this instead if it's a duplicate.", ephemeral=True
                )
                return

            # Mark this specific submission as approved.
            cur.execute("""
                UPDATE submissions SET status = 'approved', reviewed_by = ?, reviewed_at = datetime('now')
                WHERE id = ?
            """, (interaction.user.id, row["id"]))

            # Mark the tile complete for the team.
            cur.execute("""
                INSERT INTO team_tile_status (team_id, tile_id, completed, completed_at)
                VALUES (?, ?, 1, datetime('now'))
                ON CONFLICT(team_id, tile_id) DO UPDATE SET completed = 1
            """, (row["team_id"], row["tile_id"]))

            conn.commit()
        finally:
            conn.close()

        # Update the admin message to show it's been handled, and remove the buttons.
        await interaction.response.edit_message(content=f"✅ Approved by {interaction.user.name}", view=None)

        # Refresh the team's board image + both leaderboard embeds to reflect the new completion.
        await refresh_leaderboards(interaction.guild, row["team_id"])

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

        # Open the reason form — the actual status update happens in RejectionModal.on_submit,
        # not here, since we need the admin's typed reason first.
        await interaction.response.send_modal(RejectionModal(row["id"], interaction.message))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        # Catches any unhandled exception from the buttons above, logs a full traceback,
        # and gives the admin a visible error instead of a silent timeout.
        traceback.print_exception(type(error), error, error.__traceback__)
        if not interaction.response.is_done():
            await interaction.response.send_message("Something went wrong. Check the logs.", ephemeral=True)


class Approvals(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # No commands live here — this Cog only exists so the extension can be loaded;
        # ApprovalView/RejectionModal are self-contained UI objects, not slash commands.

async def setup(bot):
    await bot.add_cog(Approvals(bot))