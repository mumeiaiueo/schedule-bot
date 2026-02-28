async def on_interaction(self, interaction: discord.Interaction):
    # ボタン・セレクトは自前処理
    if interaction.type == discord.InteractionType.component:
        try:
            await handle_interaction(self, interaction)
        except Exception:
            print("handle_interaction error")
            print(traceback.format_exc())
        return

    # スラッシュコマンドは標準処理に任せる
    try:
        await self.tree._call(interaction)   # ← ここ変更
    except Exception:
        print("slash process error")
        print(traceback.format_exc())