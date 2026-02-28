import traceback
from datetime import datetime, timedelta, timezone
import discord
from views.setup_wizard import build_setup_embed, build_setup_view


async def safe_defer(interaction: discord.Interaction):
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)


async def safe_send(interaction: discord.Interaction, msg: str):
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


async def _refresh_setup(interaction: discord.Interaction, st: dict):
    embed = build_setup_embed(st)
    view = build_setup_view(st)
    await interaction.message.edit(embed=embed, view=view)


def _get_state(client, user_id):
    if not hasattr(client, "setup_state"):
        client.setup_state = {}
    if user_id not in client.setup_state:
        client.setup_state[user_id] = {
            "step": 1,
            "day": None,
            "start_hour": None,
            "start_min": None,
            "end_hour": None,
            "end_min": None,
            "start": None,
            "end": None,
            "interval": None,
            "notify_channel_id": None,
            "everyone": False,
        }
    return client.setup_state[user_id]


async def handle_interaction(client, interaction: discord.Interaction):
    try:
        if interaction.type != discord.InteractionType.component:
            return

        data = interaction.data or {}
        custom_id = data.get("custom_id")
        values = data.get("values") or []

        if not custom_id:
            return

        await safe_defer(interaction)
        st = _get_state(client, interaction.user.id)

        if custom_id == "setup:step:next":
            st["step"] = 2
            await _refresh_setup(interaction, st)
            return

        if custom_id == "setup:step:back":
            st["step"] = 1
            await _refresh_setup(interaction, st)
            return

        if custom_id == "setup:day:today":
            st["day"] = "today"

        elif custom_id == "setup:day:tomorrow":
            st["day"] = "tomorrow"

        elif custom_id == "setup:start_hour":
            st["start_hour"] = values[0]

        elif custom_id == "setup:start_min":
            st["start_min"] = values[0]

        elif custom_id == "setup:end_hour":
            st["end_hour"] = values[0]

        elif custom_id == "setup:end_min":
            st["end_min"] = values[0]

        elif custom_id == "setup:interval":
            st["interval"] = int(values[0])

        elif custom_id == "setup:notify_channel":
            st["notify_channel_id"] = str(values[0])

        elif custom_id == "setup:everyone:toggle":
            st["everyone"] = not st["everyone"]

        if st.get("start_hour") and st.get("start_min"):
            st["start"] = f"{st['start_hour']}:{st['start_min']}"

        if st.get("end_hour") and st.get("end_min"):
            st["end"] = f"{st['end_hour']}:{st['end_min']}"

        if custom_id == "setup:create":
            missing = []
            for k in ["day", "start", "end", "interval", "notify_channel_id"]:
                if not st.get(k):
                    missing.append(k)

            if missing:
                await safe_send(interaction, f"未入力: {', '.join(missing)}")
                return

            JST = timezone(timedelta(hours=9))
            today = datetime.now(JST).date()
            day = today if st["day"] == "today" else today + timedelta(days=1)

            sh, sm = map(int, st["start"].split(":"))
            eh, em = map(int, st["end"].split(":"))

            start_at = datetime(day.year, day.month, day.day, sh, sm, tzinfo=JST)
            end_at = datetime(day.year, day.month, day.day, eh, em, tzinfo=JST)

            await safe_send(interaction, "✅ 作成完了（ここにDB処理入れる）")
            client.setup_state.pop(interaction.user.id, None)
            return

        await _refresh_setup(interaction, st)

    except Exception as e:
        print(traceback.format_exc())
        await safe_send(interaction, f"エラー: {e}")