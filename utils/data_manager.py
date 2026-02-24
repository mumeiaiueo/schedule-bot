import asyncio
from datetime import timedelta
import discord

from utils.db import sb
from utils.time_utils import jst_now, to_utc_iso, from_utc_iso, fmt_hm
from views.panel_view import PanelView, build_panel_embed


class DataManager:
    # --- 共通：Supabase(同期)を別スレッドで回す ---
    async def _db(self, fn):
        return await asyncio.to_thread(fn)

    # ---------- notify prefs ----------
    async def get_notify_enabled(self, guild_id: str, user_id: str) -> bool:
        def work():
            return sb.table("user_prefs").select("notify_enabled") \
                .eq("guild_id", guild_id).eq("user_id", user_id).execute().data

        rows = await self._db(work)
        if not rows:
            return True  # デフォルトON
        return bool(rows[0]["notify_enabled"])

    async def set_notify_enabled(self, guild_id: str, user_id: str, enabled: bool):
        def work_select():
            return sb.table("user_prefs").select("id") \
                .eq("guild_id", guild_id).eq("user_id", user_id).execute().data

        rows = await self._db(work_select)

        if rows:
            def work_update():
                sb.table("user_prefs").update({
                    "notify_enabled": enabled,
                    "updated_at": to_utc_iso(jst_now()),
                }).eq("id", rows[0]["id"]).execute()
            await self._db(work_update)
        else:
            def work_insert():
                sb.table("user_prefs").insert({
                    "guild_id": guild_id,
                    "user_id": user_id,
                    "notify_enabled": enabled,
                }).execute()
            await self._db(work_insert)

    # ---------- panels ----------
    async def create_panel(
        self,
        guild_id: str,
        channel_id: str,
        day_date,
        title: str | None,
        start_at,
        end_at,
        interval_minutes: int,
        notify_channel_id: str,
        created_by: str,
    ):
        # panels作成（重なり禁止はDB制約で弾かれる想定）
        try:
            def work_insert_panel():
                return sb.table("panels").insert({
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "day": str(day_date),
                    "title": title,
                    "start_at": to_utc_iso(start_at),
                    "end_at": to_utc_iso(end_at),
                    "interval_minutes": interval_minutes,
                    "notify_channel_id": notify_channel_id,
                    "created_by": created_by,
                }).execute().data

            panel = await self._db(work_insert_panel)
        except Exception:
            return {
                "ok": False,
                "error": "このチャンネルでは、その時間帯に既に募集があります（時間が重なる募集は作れません）。作り直すなら /reset_channel を先に実行してね。"
            }

        if not panel:
            return {"ok": False, "error": "作成に失敗しました"}

        panel_id = panel[0]["id"]

        # ✅ slots作成：channel_id / guild_id / slot_time / user_id は使わない（slotsに無い）
        inserts = []
        cur = start_at
        while cur < end_at:
            nxt = cur + timedelta(minutes=interval_minutes)
            inserts.append({
                "panel_id": panel_id,
                "start_at": to_utc_iso(cur),
                "end_at": to_utc_iso(nxt),
                "is_break": False,
                "reserver_user_id": None,
                "reserver_name": None,
                "reserved_at": None,
                "notified": False,
            })
            cur = nxt

        if inserts:
            def work_insert_slots():
                sb.table("slots").insert(inserts).execute()
            await self._db(work_insert_slots)

        return {"ok": True, "panel_id": panel_id}

    # /reset_channel 用：指定日の募集を削除（slots→panels）
    async def delete_panel_by_channel_day(self, guild_id: str, channel_id: str, day_date) -> bool:
        def work_select():
            return sb.table("panels").select("id") \
                .eq("guild_id", guild_id).eq("channel_id", channel_id).eq("day", str(day_date)) \
                .order("start_at") \
                .execute().data or []

        rows = await self._db(work_select)
        if not rows:
            return False

        panel_ids = [r["id"] for r in rows]

        def work_delete():
            # slots は panel_id で削除
            sb.table("slots").delete().in_("panel_id", panel_ids).execute()
            for pid in panel_ids:
                sb.table("panels").delete().eq("id", pid).execute()

        await self._db(work_delete)
        return True

    # 互換：/reset_channel が delete_panel を呼ぶ場合に備える（今日を消す運用は delete_panel_by_channel_day 推奨）
    async def delete_panel(self, guild_id: str, channel_id: str, day_date) -> bool:
        return await self.delete_panel_by_channel_day(guild_id, channel_id, day_date)

    async def update_notify_channel_for_channel_day(self, guild_id: str, channel_id: str, day_date, notify_channel_id: str) -> bool:
        def work_select():
            return sb.table("panels").select("id") \
                .eq("guild_id", guild_id).eq("channel_id", channel_id).eq("day", str(day_date)) \
                .order("start_at") \
                .execute().data or []

        rows = await self._db(work_select)
        if not rows:
            return False

        def work_update():
            for r in rows:
                sb.table("panels").update({"notify_channel_id": notify_channel_id}).eq("id", r["id"]).execute()

        await self._db(work_update)
        return True

    # ---------- UI render ----------
    async def render_panel(self, bot: discord.Client, panel_id: int):
        def work_panel():
            return sb.table("panels").select("*").eq("id", panel_id).execute().data

        panel_rows = await self._db(work_panel)
        if not panel_rows:
            return
        panel = panel_rows[0]

        channel = bot.get_channel(int(panel["channel_id"]))
        if not channel:
            return

        def work_slots():
            return sb.table("slots").select("*").eq("panel_id", panel_id).order("start_at").execute().data or []

        slots = await self._db(work_slots)

        lines = []
        buttons = []

        for r in slots[:25]:
            sdt = from_utc_iso(r["start_at"])
            label = fmt_hm(sdt)

            if r.get("is_break"):
                dot = "⚪"
                mention = ""
                style = discord.ButtonStyle.secondary
                disabled = True
            elif r.get("reserver_user_id"):
                dot = "🔴"
                mention = f" <@{r['reserver_user_id']}>"
                style = discord.ButtonStyle.danger
                disabled = False  # 本人キャンセルのため押せる（toggleで制御）
            else:
                dot = "🟢"
                mention = ""
                style = discord.ButtonStyle.success
                disabled = False

            lines.append(f"{dot} {label}{mention}")
            buttons.append({
                "slot_id": r["id"],
                "label": label,
                "style": style,
                "disabled": disabled,
            })

        day_text = f"📅 {panel['day']}（JST） / interval {panel['interval_minutes']}min"
        title = panel.get("title") or "募集パネル"
        embed = build_panel_embed(title, day_text, lines)
        view = PanelView(panel_id, buttons)

        mid = panel.get("panel_message_id")
        if mid:
            try:
                msg = await channel.fetch_message(int(mid))
                await msg.edit(embed=embed, view=view)
                return
            except Exception:
                pass

        msg = await channel.send(embed=embed, view=view)

        def work_update_mid():
            sb.table("panels").update({"panel_message_id": str(msg.id)}).eq("id", panel_id).execute()

        await self._db(work_update_mid)

# =========================================================
# ▶▶▶ ここに入れる（toggle_reserve の直前） ▶▶▶
# =========================================================

# ---------- break toggle (admin) ----------
async def build_break_select_view(self, panel_id: int):
    from views.panel_view import BreakSelectView

    def work_slots():
        return (
            sb.table("slots")
            .select("*")
            .eq("panel_id", panel_id)
            .order("start_at")
            .execute()
            .data
            or []
        )

    slots = await self._db(work_slots)

    options = []
    for r in slots[:25]:
        sdt = from_utc_iso(r["start_at"])
        label = fmt_hm(sdt)

        if r.get("is_break"):
            desc = "休憩中（選ぶと解除）"
        elif r.get("reserver_user_id"):
            desc = "予約あり（休憩不可）"
        else:
            desc = "空き（選ぶと休憩）"

        options.append(
            discord.SelectOption(
                label=label,
                value=str(r["id"]),
                description=desc,
            )
        )

    return BreakSelectView(panel_id, options)


async def toggle_break_slot(self, panel_id: int, slot_id: int):
    def work_slot():
        return (
            sb.table("slots")
            .select("*")
            .eq("id", slot_id)
            .eq("panel_id", panel_id)
            .execute()
            .data
            or []
        )

    rows = await self._db(work_slot)
    if not rows:
        return (False, "枠が見つかりません")

    slot = rows[0]

    if slot.get("reserver_user_id") and not slot.get("is_break"):
        return (False, "予約が入っている枠は休憩にできません")

    new_val = not bool(slot.get("is_break"))

    def work_update():
        sb.table("slots").update({"is_break": new_val}).eq("id", slot_id).execute()

    await self._db(work_update)
    return (True, "休憩にしました" if new_val else "休憩を解除しました")

# =========================================================
# ▶▶▶ ここまで追加 ▶▶▶
# ======================================================

    # ---------- reserve toggle ----------
    async def toggle_reserve(self, slot_id: int, user_id: str, user_name: str):
        def work_slot():
            return sb.table("slots").select("*").eq("id", slot_id).execute().data

        slot_rows = await self._db(work_slot)
        if not slot_rows:
            return (False, "枠が見つかりません")
        slot = slot_rows[0]

        if slot.get("is_break"):
            return (False, "休憩枠です")

        panel_id = slot["panel_id"]

        # 空き → 予約（先着）
        if not slot.get("reserver_user_id"):
            # 1人1枠（同panel）
            def work_existing():
                return sb.table("slots").select("id") \
                    .eq("panel_id", panel_id).eq("reserver_user_id", user_id).execute().data

            existing = await self._db(work_existing)
            if existing:
                return (False, "すでにこの募集で予約しています（1人1枠）")

            def work_update():
                return sb.table("slots").update({
                    "reserver_user_id": user_id,
                    "reserver_name": user_name,
                    "reserved_at": to_utc_iso(jst_now()),
                    "notified": False,
                }).eq("id", slot_id).is_("reserver_user_id", None).execute().data

            updated = await self._db(work_update)
            if not updated:
                return (False, "その枠はもう埋まっています")

            return (True, "予約しました ✅（もう一度押すとキャンセル）")

        # 予約済み → 本人ならキャンセル
        if slot["reserver_user_id"] == user_id:
            def work_cancel():
                sb.table("slots").update({
                    "reserver_user_id": None,
                    "reserver_name": None,
                    "reserved_at": None,
                    "notified": False,
                }).eq("id", slot_id).execute()

            await self._db(work_cancel)
            return (True, "キャンセルしました ✅")

        # 他人の予約
        return (False, "その枠は埋まっています（本人のみキャンセル可）")

    # ---------- 3min reminders ----------
    async def send_3min_reminders(self, bot: discord.Client):
        # 未通知 & 予約済みのみ
        def work_rows():
            return sb.table("slots").select("*") \
                .eq("notified", False) \
                .not_.is_("reserver_user_id", "null") \
                .execute().data or []

        rows = await self._db(work_rows)

        now = jst_now()
        for slot in rows:
            start = from_utc_iso(slot["start_at"])
            diff = (start - now).total_seconds()

            # 3分前（誤差吸収）
            if 160 <= diff <= 220:
                def work_panel():
                    return sb.table("panels").select("*").eq("id", slot["panel_id"]).execute().data

                panel_rows = await self._db(work_panel)
                if not panel_rows:
                    continue
                panel = panel_rows[0]

                notify_ch = bot.get_channel(int(panel["notify_channel_id"]))
                if not notify_ch:
                    continue

                uid = slot["reserver_user_id"]
                enabled = await self.get_notify_enabled(panel["guild_id"], uid)

                if enabled:
                    await notify_ch.send(f"⏰ 3分前：{fmt_hm(start)} の枠です <@{uid}>")

                def work_set_notified():
                    sb.table("slots").update({"notified": True}).eq("id", slot["id"]).execute()

                await self._db(work_set_notified)