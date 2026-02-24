import asyncio
from datetime import timedelta
import discord

from utils.db import sb
from utils.time_utils import jst_now, to_utc_iso, from_utc_iso, fmt_hm
from views.panel_view import PanelView, build_panel_embed  # BreakSelectViewは使わない版


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

        # slots 作成（あなたのDB列：guild_id/channel_id/slot_time/start_at/user_id/notified/panel_id）
        inserts = []
        cur = start_at
        while cur < end_at:
            inserts.append({
                "guild_id": int(guild_id),
                "channel_id": int(channel_id),
                "panel_id": panel_id,
                "slot_time": fmt_hm(cur),       # "19:00" みたいな表示用
                "start_at": to_utc_iso(cur),
                "user_id": None,               # 未予約
                "notified": False,
            })
            cur = cur + timedelta(minutes=interval_minutes)

        if inserts:
            def work_insert_slots():
                sb.table("slots").insert(inserts).execute()
            await self._db(work_insert_slots)

        return {"ok": True, "panel_id": panel_id}

    # /reset_channel 用：guild+channel の募集を全削除（slots→panelsの順）
    async def delete_panel(self, guild_id: str, channel_id: str) -> bool:
        def work():
            panels = sb.table("panels").select("id") \
                .eq("guild_id", guild_id).eq("channel_id", channel_id).execute().data or []
            panel_ids = [p["id"] for p in panels]

            if panel_ids:
                sb.table("slots").delete().in_("panel_id", panel_ids).execute()

            sb.table("panels").delete().eq("guild_id", guild_id).eq("channel_id", channel_id).execute()
            return len(panel_ids) > 0

        return await self._db(work)

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
            sb.table("slots").delete().in_("panel_id", panel_ids).execute()
            for pid in panel_ids:
                sb.table("panels").delete().eq("id", pid).execute()

        await self._db(work_delete)
        return True

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
    async def render_panel(self, bot: discord.Client, panel_id):
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

            if r.get("user_id"):
                dot = "🔴"
                mention = f" <@{r['user_id']}>"
                style = discord.ButtonStyle.danger
            else:
                dot = "🟢"
                mention = ""
                style = discord.ButtonStyle.success

            lines.append(f"{dot} {label}{mention}")
            buttons.append({
                "slot_id": r["id"],
                "label": label,
                "style": style,
                "disabled": False,   # 本人キャンセルのため押せる（制御はtoggle_reserve側）
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

    # ---------- reserve toggle ----------
    async def toggle_reserve(self, slot_id, user_id: str):
        def work_slot():
            return sb.table("slots").select("*").eq("id", slot_id).execute().data

        slot_rows = await self._db(work_slot)
        if not slot_rows:
            return (False, "枠が見つかりません")
        slot = slot_rows[0]

        panel_id = slot["panel_id"]

        # 空き → 予約（先着）
        if not slot.get("user_id"):
            def work_existing():
                return sb.table("slots").select("id") \
                    .eq("panel_id", panel_id).eq("user_id", int(user_id)).execute().data

            existing = await self._db(work_existing)
            if existing:
                return (False, "すでにこの募集で予約しています（1人1枠）")

            def work_update():
                return sb.table("slots").update({
                    "user_id": int(user_id),
                    "notified": False,
                }).eq("id", slot_id).is_("user_id", None).execute().data

            updated = await self._db(work_update)
            if not updated:
                return (False, "その枠はもう埋まっています")

            return (True, "予約しました ✅（もう一度押すとキャンセル）")

        # 予約済み → 本人ならキャンセル
        if int(slot["user_id"]) == int(user_id):
            def work_cancel():
                sb.table("slots").update({
                    "user_id": None,
                    "notified": False,
                }).eq("id", slot_id).execute()

            await self._db(work_cancel)
            return (True, "キャンセルしました ✅")

        # 他人の予約
        return (False, "その枠は埋まっています（本人のみキャンセル可）")

    # ---------- 3min reminders ----------
    async def send_3min_reminders(self, bot: discord.Client):
        def work_rows():
            return sb.table("slots").select("*") \
                .eq("notified", False) \
                .not_.is_("user_id", "null") \
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

                uid = str(slot["user_id"])
                enabled = await self.get_notify_enabled(panel["guild_id"], uid)

                if enabled:
                    await notify_ch.send(f"⏰ 3分前：{fmt_hm(start)} の枠です <@{uid}>")

                def work_set_notified():
                    sb.table("slots").update({"notified": True}).eq("id", slot["id"]).execute()

                await self._db(work_set_notified)