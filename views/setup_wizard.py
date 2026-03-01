import discord
class SetupWizardView(discord.ui.View):
    def __init__(self, st: dict):
        super().__init__(timeout=600)
        step = int(st.get("step") or 1)
        day = st.get("day") or "today"

        # ===== Row 0：日付 =====
        self.add_item(_btn("今日", "setup:day:today",
                           discord.ButtonStyle.primary if day == "today"
                           else discord.ButtonStyle.secondary,
                           row=0))

        self.add_item(_btn("明日", "setup:day:tomorrow",
                           discord.ButtonStyle.primary if day == "tomorrow"
                           else discord.ButtonStyle.secondary,
                           row=0))

        if step == 1:
            # ===== Row 1〜4：時刻選択 =====
            self.add_item(_sel("setup:start_hour",
                               f"開始(時) 現在:{_val_or_dash(st.get('start_hour'))}",
                               _hour_options(),
                               row=1))

            self.add_item(_sel("setup:start_min",
                               f"開始(分) 現在:{_val_or_dash(st.get('start_min'))}",
                               _min_options(),
                               row=2))

            self.add_item(_sel("setup:end_hour",
                               f"終了(時) 現在:{_val_or_dash(st.get('end_hour'))}",
                               _hour_options(),
                               row=3))

            self.add_item(_sel("setup:end_min",
                               f"終了(分) 現在:{_val_or_dash(st.get('end_min'))}",
                               _min_options(),
                               row=4))

            # 次へは row=0 に置かず row=4 に変更
            self.add_item(_btn("次へ",
                               "setup:step:next",
                               discord.ButtonStyle.success,
                               row=4))

        else:
            # ===== Step2 =====

            # Row1: 間隔
            self.add_item(_sel("setup:interval",
                               f"間隔（分） 現在:{_val_or_dash(st.get('interval'))}",
                               _interval_options(),
                               row=1))

            # Row2: 通知チャンネル
            cs = discord.ui.ChannelSelect(
                custom_id="setup:notify_channel",
                placeholder="通知チャンネル（未選択=このチャンネル）",
                min_values=1,
                max_values=1,
                channel_types=[discord.ChannelType.text],
                row=2,
            )
            cs.callback = _noop
            self.add_item(cs)

            # Row3: タイトル
            self.add_item(_btn("📝 タイトル入力",
                               "setup:title:open",
                               discord.ButtonStyle.secondary,
                               row=3))

            # Row3: @everyone
            everyone = bool(st.get("everyone"))
            self.add_item(_btn("@everyone ON" if everyone else "@everyone OFF",
                               "setup:everyone:toggle",
                               discord.ButtonStyle.danger if everyone else discord.ButtonStyle.secondary,
                               row=3))

            # Row4: 戻る & 作成
            self.add_item(_btn("戻る",
                               "setup:step:back",
                               discord.ButtonStyle.secondary,
                               row=4))

            self.add_item(_btn("作成",
                               "setup:create",
                               discord.ButtonStyle.success,
                               row=4))