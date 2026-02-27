# commands/setup_channel.py
import traceback
import discord

from views.setup_wizard import build_setup_embed, build_setup_view

async def safe_defer(interaction: discord.Interaction, *, ephemeral=True):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass

async def safe_followup(interaction: discord.Interaction, content=None, *, embed=None, view=None, ephemeral=True):
    try:
        await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
    except Exception:
        pass

def register(tree: discord.app_commands.CommandTree, dm):
    @tree.command(name="setup_channel", description="このチャンネルに予約枠パネルを作成（ウィザード）")
    async def setup_channel(interaction: discord.Interaction):
        # ✅ 3秒対策（これが無いと “反応しません” が出る）
        await safe_defer(interaction, ephemeral=True)

        try:
            # client.setup_state を使う
            st = dm.get_or_init_setup_state(interaction.client.setup_state, interaction.user.id)

            embed = build_setup_embed(st)
            view = build_setup_view(st)

            await safe_followup(interaction, embed=embed, view=view, ephemeral=True)

        except Exception as e:
            print("setup_channel error:", repr(e))
            print(traceback.format_exc())
            await safe_followup(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)