async def callback(self, interaction: discord.Interaction):

    data = load_data()
    slot = self.slot

    # ⭐ reservations 初期化（これが神）
    data.setdefault("reservations", {})

    # 重複防止
    if slot in data["reservations"]:
        await interaction.response.send_message("埋まってる", ephemeral=True)
        return

    # 予約保存
    data["reservations"][slot] = interaction.user.id
    save_data(data)

    # ⭐ 先に応答
    await interaction.response.send_message("予約完了", ephemeral=True)

    # ⭐ メッセージ更新
    try:
        channel = interaction.channel
        message = await channel.fetch_message(data["message_id"])

        msg = "📅 予約枠\n"
        for s in data["slots"]:
            if s in data["reservations"]:
                user_id = data["reservations"][s]
                msg += f"🔴 {s} <@{user_id}>\n"
            else:
                msg += f"🟢 {s}\n"

        await message.edit(content=msg, view=SlotView(data["slots"]))

    except Exception as e:
        print("edit error:", e)
