# views/setup_wizard.py
import discord
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def _fmt(st: dict) -> str:
    day = st.get("day") or "未選択"
    start = st.get("start") or "未選択"
    end = st.get("end") or "未選択"
    interval = st.get("interval") or "未選択"
    ch = st.get("notify_channel_id")
    chtxt = f"<#{ch}>" if ch else "未選択"
    everyone = "ON" if st.get("everyone") else "OFF"
    title = st.get("title") or "（なし）"
    page = st.get("page", 1)

    return (
        f"**ページ**: {page}/2\n"
        f"**日付**: {day}\n"
        f"**開始**: {start}\n"
        f"**終了**: {end}\n"
        f"**間隔**: {interval}\n"
        f"**通知チャンネル**: {chtxt}\n"
        f"**@everyone**: {everyone}\n"
        f"**タイトル**: {title}\n"
    )


def build_setup_embed(st: dict) -> discord.Embed:
    e = discord.Embed(
        title="🧩 募集パネル作成（ウィザード）",
        description=_fmt(st),
    )
    e.set_footer(text="※ row制限対策済み（0〜4のみ使用）")
    return e


def _hour_options():
    opts = []
    for h in range(0, 24):
        opts.append(discord.SelectOption(label=f"{h:02d}", value=f"{h:02d}"))
    return opts  # 24 <= 25 OK


def _min_options():
    opts = []
    for m in range(0, 60, 5):
        opts.append(discord.SelectOption(label=f"{m:02d}", value=f"{m:02d}"))
    return opts  # 12 <= 25 OK


class _IntervalSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="間隔を選んで（必須）",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="20分", value="20"),
                discord.SelectOption(label="25分", value="25"),
                discord.SelectOption(label="30分", value="30"),
            ],
            custom_id="setup:interval",
            row=0,  # ✅ row固定
        )


class _HourSelect(discord.ui.Select):
    def __init__(self, custom_id: str, placeholder: str, row: int):
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=_hour_options(),
            custom_id=custom_id,
            row=row,  # ✅ row固定
        )


class _MinSelect(discord.ui.Select):
    def __init__(self, custom_id: str, placeholder: str, row: int):
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=_min_options(),
            custom_id=custom_id,
            row=row,  # ✅ row固定
        )


class _DayToday(discord.ui.Button):
    def __init__(self):
        super().__init__(label="今日", style=discord.ButtonStyle.primary, custom_id="setup:day:today", row=0)


class _DayTomorrow(discord.ui.Button):
    def __init__(self):
        super().__init__(label="明日", style=discord.ButtonStyle.primary, custom_id="setup:day:tomorrow", row=0)


class _EveryoneToggle(discord.ui.Button):
    def __init__(self, on: bool):
        super().__init__(
            label=f"@everyone: {'ON' if on else 'OFF'}",
            style=discord.ButtonStyle.secondary,
            custom_id="setup:everyone:toggle",
            row=0,
        )


class _Next(discord.ui.Button):
    def __init__(self):
        super().__init__(label="次へ ▶", style=discord.ButtonStyle.success, custom_id="setup:page:next", row=0)


class _Back(discord.ui.Button):
    def __init__(self):
        super().__init__(label="◀ 戻る", style=discord.ButtonStyle.secondary, custom_id="setup:page:back", row=2)


class _Create(discord.ui.Button):
    def __init__(self):
        super().__init__(label="✅ 作成", style=discord.ButtonStyle.success, custom_id="setup:create", row=2)


class _Cancel(discord.ui.Button):
    def __init__(self):
        super().__init__(label="✖ キャンセル", style=discord.ButtonStyle.danger, custom_id="setup:cancel", row=2)


class _NotifyChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            channel_types=[discord.ChannelType.text],
            placeholder="3分前通知を送るチャンネル（必須）",
            min_values=1,
            max_values=1,
            custom_id="setup:notify_channel",
            row=0,  # ✅ row固定
        )


class _TitleModalButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="タイトル入力（任意）", style=discord.ButtonStyle.secondary, custom_id="setup:title:open", row=1)


class TitleModal(discord.ui.Modal, title="募集タイトル（任意）"):
    title_text = discord.ui.TextInput(
        label="タイトル（空でもOK）",
        required=False,
        max_length=80,
        placeholder="例）夜の募集 / 周回 / 作業枠 など",
    )

    def __init__(self, st: dict):
        super().__init__()
        self._st = st

    async def on_submit(self, interaction: discord.Interaction):
        t = str(self.title_text.value or "").strip()
        self._st["title"] = t or None
        await interaction.response.send_message("✅ タイトルを保存しました", ephemeral=True)


class SetupWizardView(discord.ui.View):
    def __init__(self, st: dict):
        super().__init__(timeout=None)
        page = int(st.get("page", 1))

        # ページ1（時間・日付・間隔）
        if page == 1:
            # row0: 今日/明日 + 間隔Select + everyone + 次へ で 5個以内
            self.add_item(_DayToday())
            self.add_item(_DayTomorrow())
            self.add_item(_IntervalSelect())
            self.add_item(_EveryoneToggle(bool(st.get("everyone"))))
            self.add_item(_Next())

            # row1〜4: 時間（hour/min を分割）
            self.add_item(_HourSelect("setup:start_hour", "開始：時（必須）", row=1))
            self.add_item(_MinSelect("setup:start_min", "開始：分（5分刻み・必須）", row=2))
            self.add_item(_HourSelect("setup:end_hour", "終了：時（必須）", row=3))
            self.add_item(_MinSelect("setup:end_min", "終了：分（5分刻み・必須）", row=4))

        # ページ2（通知チャンネル・作成）
        else:
            # row0: 通知チャンネル
            self.add_item(_NotifyChannelSelect())

            # row1: タイトル入力（任意）
            self.add_item(_TitleModalButton())

            # row2: 戻る / 作成 / キャンセル
            self.add_item(_Back())
            self.add_item(_Create())
            self.add_item(_Cancel())


def build_setup_view(st: dict) -> discord.ui.View:
    # row を絶対 0〜4 しか使わない View を返す
    return SetupWizardView(st)