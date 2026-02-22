import discord
from discord import app_commands

def setup(bot: discord.Client):

    @bot.tree.command(name="notifyset", description="3分前通知を送るチャンネルを設定（管理者のみ）")
    @app_commands.checks.has_permissions(administrator=True)
    async def notifyset(interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild.id)
        ch_id = str(channel.id)  # DB保存は文字列で統一

        async with bot.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO guild_settings (guild_id, notify_channel)
                VALUES ($1, $2)
                ON CONFLICT (guild_id)
                DO UPDATE SET notify_channel = EXCLUDED.notify_channel
                """,
                guild_id,
                ch_id
            )

        await interaction.followup.send(f"✅ 通知チャンネルを {channel.mention} に設定しました", ephemeral=True)

    # ✅ 追加：通知チャンネルにテスト送信（これで「送れる/送れない」を切り分けできる）
    @bot.tree.command(name="pingnotify", description="通知チャンネルにテスト送信（管理者のみ）")
    @app_commands.checks.has_permissions(administrator=True)
    async def pingnotify(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild.id)

        async with bot.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT notify_channel FROM guild_settings WHERE guild_id=$1",
                guild_id
            )

        if not row or not row["notify_channel"]:
            return await interaction.followup.send(
                "❌ 通知チャンネルが未設定です。先に /notifyset してね",
                ephemeral=True
            )

        notify_channel = row["notify_channel"]  # TEXT想定
        ch = bot.get_channel(int(notify_channel))
        if ch is None:
            try:
                ch = await bot.fetch_channel(int(notify_channel))
            except Exception:
                return await interaction.followup.send(
                    "❌ 通知チャンネルが見つかりません（権限不足/削除/ID違いの可能性）",
                    ephemeral=True
                )

        await ch.send("✅ テスト通知：pingnotify からの送信です（メンションも動作OK）")
        await interaction.followup.send(f"✅ {ch.mention} にテスト送信しました", ephemeral=True)
