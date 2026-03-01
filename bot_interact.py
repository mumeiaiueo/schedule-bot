from __future__ import annotations

import traceback
from datetime import datetime

import discord

from utils.time_utils import jst_now, jst_today_date, build_range_jst
from views.setup_wizard import build_setup_embed, build_setup_view, TitleModal


def _default_setup_state() -> dict:
    return {
        "step": 1,
        "day": "today",            # default today
        "start_hour": None,
        "start_min": None,
        "end_hour": None,
        "end_min": None,
        "start": None,             # "HH:MM"
        "end": None,               # "HH:MM"
        "interval": None,          # int
        "notify_channel_id": None, # str
        "everyone": False,         # 作成時に1回だけ @everyone
        "title": None,             # optional
    }


def _ensure_state(bot: discord.Client, user_id: int) -> dict:
    if not hasattr(bot, "setup_state") or bot.setup_state is None:
        bot.setup_state = {}
    st = bot.setup_state.get(user_id)
    if not isinstance(st, dict):
        st = _default_setup_state()
        bot.setup_state[user_id] = st

    # key補完
    base = _default_setup_state()
    for k, v in base.items():
        st.setdefault(k, v)

    if st.get("step") not in (1, 2):
        st["step"] = 1

    return st


def _recalc_hm(st: dict):
    if st.get("start_hour") is not None and st.get("start_min") is not None:
        st["start"] = f"{int(st['start_hour']):02d}:{int(st['start_min']):02d}"
    else:
        st["start"] = None

    if st.get("end_hour") is not None and st.get("end_min") is not None:
        st["end"] = f"{int(st['end_hour']):02d}:{int(st['end_min']):02d}"
    else:
        st["end"] = None


def _parse_panel_slot(custom_id: str):
    # panel:slot:{panel_id}:{slot_id}
    if not custom_id.startswith("panel:slot:"):
        return None
    parts = custom_id.split(":")
    if len(parts) != 4:
        return None
    try:
        return int(parts[2]), int(parts[3])
    except Exception:
        return None


def _parse_one_id(prefix: str, custom_id: str):
    if not custom_id.startswith(prefix):
        return None
    parts = custom_id.split(":")
    if len(parts) != 3:
        return None
    try:
        return int(parts[2])
    except Exception:
        return None


async def _safe_ephemeral(interaction: discord.Interaction, text: str):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except Exception:
        pass


async def _safe_edit_message(interaction: discord.Interaction, *, embed=None, view=None, content=None):
    try:
        if interaction.message:
            await interaction.message.edit(content=content, embed=embed, view=view)
            return
    except Exception:
        pass
    try:
        await interaction.edit_original_response(content=content, embed=embed, view=view)
    except Exception:
        pass


async def handle_interaction(bot: discord.Client, interaction: discord.Interaction):
    try:
        data = interaction.data or {}
        custom_id = data.get("custom_id") or ""

        dm = getattr(bot, "dm", None)
        if dm is None:
            await _safe_ephemeral(interaction, "❌ DataManager未初期化")
            return

        # =========================
        # modal submit（タイトル入力）
        # =========================
        if interaction.type == discord.InteractionType.modal_submit:
            if custom_id == "setup:title:modal":
                st = _ensure_state(bot, interaction.user.id)
                try:
                    title = (data.get("components")[0]["components"][0]["value"] or "").strip()
                except Exception:
                    title = ""
                st["title"] = title or None

                embed = build_setup_embed(st)
                view = build_setup_view(st)
                await _safe_ephemeral(interaction, "✅ タイトルを反映しました")
                # モーダルは “元メッセ” が無いので、ユーザーはもう一度 /setup のメッセを見る形
                # ただし state は保存されてるのでOK
                return

        # =========================
        # setup wizard
        # =========================
        if custom_id.startswith("setup:"):
            st = _ensure_state(bot, interaction.user.id)
            values = data.get("values") or []

            # 日付
            if custom_id == "setup:day:today":
                st["day"] = "today"
            elif custom_id == "setup:day:tomorrow":
                st["day"] = "tomorrow"

            # 時刻
            elif custom_id == "setup:start_hour" and values:
                st["start_hour"] = values[0]
            elif custom_id == "setup:start_min" and values:
                st["start_min"] = values[0]
            elif custom_id == "setup:end_hour" and values:
                st["end_hour"] = values[0]
            elif custom_id == "setup:end_min" and values:
                st["end_min"] = values[0]

            # Step移動
            elif custom_id == "setup:step:next":
                _recalc_hm(st)
                if not st.get("start") or not st.get("end"):
                    await _safe_ephemeral(interaction, "❌ 開始/終了を選んでください")
                else:
                    st["step"] = 2

            elif custom_id == "setup:step:back":
                st["step"] = 1

            # Step2
            elif custom_id == "setup:interval" and values:
                try:
                    st["interval"] = int(values[0])
                except Exception:
                    st["interval"] = None

            elif custom_id == "setup:everyone:toggle":
                st["everyone"] = not bool(st.get("everyone"))

            elif custom_id == "setup:notify_channel" and values:
                # ChannelSelect は values に channel_id が入る
                st["notify_channel_id"] = str(values[0])

            elif custom_id == "setup:title:open":
                # ここは bot_app 側で defer してないので send_modal OK
                await interaction.response.send_modal(TitleModal())
                return

            elif custom_id == "setup:create":
                _recalc_hm(st)

                if not st.get("start") or not st.get("end"):
                    await _safe_ephemeral(interaction, "❌ 開始/終了を選んでください")
                    st["step"] = 1
                elif not st.get("interval"):
                    await _safe_ephemeral(interaction, "❌ 間隔（分）を選んでください")
                    st["step"] = 2
                else:
                    # 日付
                    day_date = jst_today_date(0 if st["day"] == "today" else 1)

                    # 時刻
                    sh, sm = int(st["start_hour"]), int(st["start_min"])
                    eh, em = int(st["end_hour"]), int(st["end_min"])
                    start_at, end_at = build_range_jst(day_date, sh, sm, eh, em)

                    # 通知チャンネル（未選択ならこのチャンネル）
                    notify_channel_id = st.get("notify_channel_id") or str(interaction.channel_id)

                    # 作成
                    res = await dm.create_panel(
                        guild_id=str(interaction.guild_id),
                        channel_id=str(interaction.channel_id),
                        day_date=day_date,
                        title=st.get("title"),
                        start_at=start_at,
                        end_at=end_at,
                        interval_minutes=int(st["interval"]),
                        notify_channel_id=str(notify_channel_id),
                        created_by=str(interaction.user.id),
                    )
                    if not res.get("ok"):
                        await _safe_ephemeral(interaction, f"❌ 作成失敗: {res.get('error')}")
                    else:
                        panel_id = int(res["panel_id"])
                        await dm.render_panel(bot, panel_id)

                        # ✅ @everyone は「作成時に1回だけ」
                        if st.get("everyone"):
                            try:
                                ch = bot.get_channel(int(interaction.channel_id))
                                if ch:
                                    await ch.send("@everyone")
                            except Exception:
                                pass

                        await _safe_ephemeral(interaction, "✅ 作成しました！パネルを確認してね")

                        # state削除
                        try:
                            bot.setup_state.pop(interaction.user.id, None)
                        except Exception:
                            pass
                        return

            # 再描画
            _recalc_hm(st)
            embed = build_setup_embed(st)
            view = build_setup_view(st)
            await _safe_edit_message(interaction, embed=embed, view=view)
            return

        # =========================
        # panel: slot reserve
        # =========================
        ps = _parse_panel_slot(custom_id)
        if ps:
            panel_id, slot_id = ps
            ok, msg = await dm.toggle_reserve(
                slot_id=slot_id,
                user_id=str(interaction.user.id),
                user_name=getattr(interaction.user, "display_name", None) or interaction.user.name,
            )
            await _safe_ephemeral(interaction, ("✅ " if ok else "❌ ") + msg)
            await dm.render_panel(bot, panel_id)
            return

        # notify toggle（管理者/管理ロール）
        panel_id = _parse_one_id("panel:notifytoggle:", custom_id)
        if panel_id is not None:
            if not await dm.is_manager(interaction):
                await _safe_ephemeral(interaction, "❌ 管理者/管理ロールのみ操作できます")
                return
            ok, msg = await dm.toggle_notify_paused(panel_id)
            await _safe_ephemeral(interaction, ("✅ " if ok else "❌ ") + msg)
            await dm.render_panel(bot, panel_id)
            return

        # break toggle（管理者/管理ロール）→ select表示
        panel_id = _parse_one_id("panel:breaktoggle:", custom_id)
        if panel_id is not None:
            if not await dm.is_manager(interaction):
                await _safe_ephemeral(interaction, "❌ 管理者/管理ロールのみ操作できます")
                return
            view = await dm.build_break_select_view(panel_id)
            await _safe_ephemeral(interaction, "🛠 休憩にする/解除する枠を選んでね（予約済みは不可）")
            try:
                await interaction.followup.send("⬇️ ここから選択", view=view, ephemeral=True)
            except Exception:
                pass
            return

        # break select（管理者/管理ロール）
        panel_id = _parse_one_id("panel:breakselect:", custom_id)
        if panel_id is not None:
            if not await dm.is_manager(interaction):
                await _safe_ephemeral(interaction, "❌ 管理者/管理ロールのみ操作できます")
                return
            values = data.get("values") or []
            if not values:
                return
            try:
                slot_id = int(values[0])
            except Exception:
                await _safe_ephemeral(interaction, "❌ 選択値が不正です")
                return

            ok, msg = await dm.toggle_break_slot(panel_id, slot_id)
            await _safe_ephemeral(interaction, ("✅ " if ok else "❌ ") + msg)
            await dm.render_panel(bot, panel_id)
            return

    except Exception:
        print("handle_interaction error")
        print(traceback.format_exc())
        try:
            await _safe_ephemeral(interaction, "❌ ボタン処理でエラー（ログ確認）")
        except Exception:
            pass