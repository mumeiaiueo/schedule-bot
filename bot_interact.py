import traceback
import discord

from views.setup_wizard import build_setup_view, build_setup_embed, TitleModal
from utils.time_utils import hm_to_minutes, make_dt_from_hm, day_key_to_date

def _hhmm(st: dict, which: str) -> str | None:
    hh = st.get(f"{which}_hour")
    mm = st.get(f"{which}_min")
    if not hh or not mm:
        return None
    return f"{hh}:{mm}"

async def handle_component(bot, interaction: discord.Interaction):
    try:
        st = bot.wizard_state.get(interaction.user.id)
        if not st:
            if not interaction.response.is_done():
                await interaction.response.send_message("状態がありません。/setup をやり直してね", ephemeral=True)
            return

        data = interaction.data or {}
        cid = data.get("custom_id") or ""
        values = data.get("values", []) or []

        # ===== buttons =====
        if cid.startswith("setup:day:"):
            st["day"] = cid.split(":")[-1]

        elif cid == "setup:step:2":
            st["step"] = 2

        elif cid == "setup:step:1":
            st["step"] = 1

        elif cid == "setup:everyone:toggle":
            st["everyone"] = not bool(st.get("everyone", False))

        elif cid == "setup:title:open":
            if not interaction.response.is_done():
                await interaction.response.send_modal(TitleModal(st))
            return

        # ===== selects =====
        if cid == "setup:start_hour" and values:
            st["start_hour"] = values[0]
        elif cid == "setup:start_min" and values:
            st["start_min"] = values[0]
        elif cid == "setup:end_hour" and values:
            st["end_hour"] = values[0]
        elif cid == "setup:end_min" and values:
            st["end_min"] = values[0]
        elif cid == "setup:interval" and values:
            st["interval"] = values[0]
        elif cid == "setup:notify_channel" and values:
            st["notify_channel"] = int(values[0])

        # start/end 表示用の "HH:MM" を埋める（embedで見やすくする）
        st["start"] = _hhmm(st, "start")
        st["end"] = _hhmm(st, "end")

        # ===== create =====
                if cid == "setup:create":
            # まず必ずACK（ここで無反応が消える）
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            try:
                if not st.get("start") or not st.get("end"):
                    await interaction.followup.send("開始/終了を選んでね", ephemeral=True)
                    return
                if not st.get("interval"):
                    await interaction.followup.send("間隔を選んでね", ephemeral=True)
                    return

                # DB保存（あなたの create_panel_record 呼び出し）
                # ↓ここはあなたの実装に合わせて（前に渡した版ならそのまま）
                await bot.dm.create_panel_record(
                    guild_id=interaction.guild_id,
                    channel_id=interaction.channel_id,
                    day_key=st["day"],
                    payload={
                        "start": st["start"],
                        "end": st["end"],
                        "interval": int(st["interval"]),
                        "title": st.get("title", ""),
                        "everyone": bool(st.get("everyone", False)),
                        "notify_channel": st.get("notify_channel") or interaction.channel_id,
                    }
                )

                await interaction.followup.send("✅ 作成しました（DB保存）", ephemeral=True)

                # 画面更新は message.edit（responseはもう使ってるから）
                await interaction.message.edit(
                    embed=build_setup_embed(st),
                    view=build_setup_view(st)
                )
                return

            except Exception:
                print("❌ setup:create error")
                print(traceback.format_exc())
                await interaction.followup.send("❌ 作成に失敗（ログを見てね）", ephemeral=True)
                return

            day_key = st.get("day", "today")
            start_at = make_dt_from_hm(day_key, st["start_hour"], st["start_min"])
            end_at = make_dt_from_hm(day_key, st["end_hour"], st["end_min"])
            day_date = day_key_to_date(day_key)

            notify_ch = st.get("notify_channel") or interaction.channel_id

            await bot.dm.create_panel_record(
                guild_id=interaction.guild_id,
                channel_id=interaction.channel_id,
                day=day_date,
                title=st.get("title", ""),
                start_at=start_at,
                end_at=end_at,
                interval_minutes=int(st["interval"]),
                notify_channel_id=notify_ch,
                mention_everyone=bool(st.get("everyone", False)),
                created_by=interaction.user.id,
            )

            # ✅ 成功通知
            await interaction.followup.send("✅ 作成しました（panels に保存済み）", ephemeral=True)

            # ✅ パネル自体も見た目更新（ここは response じゃなく message.edit でOK）
            await interaction.message.edit(
                embed=build_setup_embed(st),
                view=build_setup_view(st)
            )
            return

        # ===== normal UI update =====
        embed = build_setup_embed(st)
        view = build_setup_view(st)

        # ここは defer してないので edit_message でOK
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.message.edit(embed=embed, view=view)

    except Exception:
        print("❌ handle_component error")
        print(traceback.format_exc())
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("内部エラー。ログ見てね", ephemeral=True)
        except Exception:
            pass