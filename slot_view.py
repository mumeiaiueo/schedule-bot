async def callback(self, interaction: discord.Interaction):

    if slot in data["reservations"]:
        await interaction.response.send_message("埋まってる", ephemeral=True)
        return

    data["reservations"][slot] = interaction.user.id
    save_data(data)

    # ⭐ メッセージ更新
    channel = interaction.channel
    message = await channel.fetch_message(data["message_id"])

    msg = "📅 予約枠\n"
    for s in data["slots"]:
        if s in data["reservations"]:
            user = await interaction.guild.fetch_member(data["reservations"][s])
            msg += f"🔴 {s} {user.mention}\n"
        else:
            msg += f"🟢 {s}\n"

    await message.edit(content=msg, view=SlotView(data["slots"]))

    await interaction.response.send_message("予約完了", ephemeral=True)
