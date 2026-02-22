        # 3分前通知ループ起動
        try:
            from commands.remind import start_remind
            start_remind(self)
            print("🔥 remind 起動処理呼び出し完了")
        except Exception as e:
            print("⚠ remind 起動失敗:", e)