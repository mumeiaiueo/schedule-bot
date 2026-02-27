print("✅ LOADED data_manager.py v2026-02-27 FIXED v2")

import asyncio
from datetime import timedelta
import discord

from utils.db import sb
from utils.time_utils import jst_now, to_utc_iso, from_utc_iso, fmt_hm
from views.panel_view import PanelView, BreakSelectView, build_panel_embed


class DataManager:
    async def _db(self, fn):
        return await asyncio.to_thread(fn)

    def _require_db(self):
        if sb is None:
            raise RuntimeError("Supabaseが未接続です（SUPABASE_URL/KEY or DNS を確認）")

    # ---------- guild settings (manager role) ----------
    async def get_manager_role_id(self, guild_id: str):
        self._require_db()

        def work():
            rows = (
                sb.table("guild_settings")
                .select("manager_role_id")
                .eq("guild_id", int(guild_id))
                .limit(1)
                .execute()
                .data
                or []
            )
            if not rows:
                return None
            return rows[0].get("manager_role_id")

        return await self._db(work)

    async def set_manager_role_id(self, guild_id: str, role_id: int | None):
        self._require_db()

        def work():
            sb.table("guild_settings").upsert(
                {
                    "guild_id": int(guild_id),
                    "manager_role_id": role_id,
                    "updated_at": to_utc_iso(jst_now()),
                },
                on_conflict="guild_id",
            ).execute()

        await self._db(work)

        if role_id is None:
            return (True, "✅ 管理ロール設定を解除しました（管理者のみ実行可能になります）")
        return (True, "✅ 管理ロールを設定しました（このロール持ちは管理コマンド実行OK）")

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
        everyone: bool = False,
    ):
        self._require_db()

        try:
            def work_insert_panel():
                return sb.table("panels").insert({
                    "guild_id": int(guild_id),
                    "channel_id": int(channel_id),
                    "day": str(day_date),
                    "title": title,
                    "start_at": to_utc_iso(start_at),
                    "end_at": to_utc_iso(end_at),
                    "interval_minutes": int(interval_minutes),
                    "notify_channel_id": int(notify_channel_id),
                    "created_by": str(created_by),
                    "notify_enabled": True,
                    "notify_paused": False,
                    "everyone": bool(everyone),
                }).execute().data

            panel = await self._db(work_insert_panel)
        except Exception as e:
            return {"ok": False, "error": f"panel insert failed: {repr(e)}"}

        if not panel:
            return {"ok": False, "error": "作成に失敗しました"}

        panel_id = panel[0]["id"]

        inserts = []
        cur = start_at
        while cur < end_at:
            nxt = cur + timedelta(minutes=int(interval_minutes))
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

    async def delete_panel(self, guild_id: str, channel_id: str) -> bool:
        self._require_db()

        def work():
            panels = sb.table("panels").select("id") \
                .eq("guild_id", int(guild_id)).eq("channel_id", int(channel_id)).execute().data or []
            panel_ids = [p["id"] for p in panels]
            if panel_ids:
                sb.table("slots").delete().in_("panel_id", panel_ids).execute()
            sb.table("panels").delete().eq("guild_id", int(guild_id)).eq("channel_id", int(channel_id)).execute()
            return len(panel_ids) > 0

        return await self._db(work)

    # ---------- UI render ----------
    async def render_panel(self, bot: discord.Client, panel_id: int):
        self._require_db()

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
                disabled = False
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
        view = PanelView(self, panel_id, buttons)

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
    async def toggle_reserve(self, slot_id: int, user_id: str, user_name: str):
        self._require_db()

        def work_slot():
            return sb.table("slots").select("*").eq("id", slot_id).execute().data
        slot_rows = await self._db(work_slot)
        if not slot_rows:
            return (False, "枠が見つかりません")
        slot = slot_rows[0]

        if slot.get("is_break"):
            return (False, "休憩枠です（予約できません）")

        # 空き → 予約（先着）
        if not slot.get("reserver_user_id"):
            def work_update():
                return sb.table("slots").update({
                    "reserver_user_id": str(user_id),
                    "reserver_name": user_name,
                    "reserved_at": to_utc_iso(jst_now()),
                    "notified": False,
                }).eq("id", slot_id).is_("reserver_user_id", None).execute().data

            updated = await self._db(work_update)
            if not updated:
                return (False, "その枠はもう埋まっています")
            return (True, "予約しました ✅（もう一度押すとキャンセル）")

        # 予約済み → 本人ならキャンセル
        if str(slot.get("reserver_user_id")) == str(user_id):
            def work_cancel():
                sb.table("slots").update({
                    "reserver_user_id": None,
                    "reserver_name": None,
                    "reserved_at": None,
                    "notified": False,
                }).eq("id", slot_id).execute()
            await self._db(work_cancel)
            return (True, "キャンセルしました ✅")

        return (False, "その枠は埋まっています（本人のみキャンセル可）")

    # ---------- break select (admin) ----------
    async def build_break_select_view(self, panel_id: int) -> BreakSelectView:
        self._require_db()

        def work_slots():
            return sb.table("slots").select("*").eq("panel_id", panel_id).order("start_at").execute().data or []
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

            options.append(discord.SelectOption(label=label, value=str(r["id"]), description=desc))

        return BreakSelectView(self, panel_id, options)

    async def toggle_break_slot(self, panel_id: int, slot_id: int):
        self._require_db()

        def work_slot():
            return sb.table("slots").select("*").eq("id", slot_id).eq("panel_id", panel_id).execute().data
        rows = await self._db(work_slot)
        if not rows:
            return (False, "枠が見つかりません")
        slot = rows[0]

        if slot.get("reserver_user_id") and not bool(slot.get("is_break")):
            return (False, "予約が入っている枠は休憩にできません")

        new_val = not bool(slot.get("is_break"))

        def work_update():
            sb.table("slots").update({"is_break": new_val}).eq("id", slot_id).execute()
        await self._db(work_update)

        return (True, "休憩にしました" if new_val else "休憩を解除しました")

    # ---------- 3min reminders ----------
    async def send_3min_reminders(self, bot: discord.Client):
        self._require_db()

        # 予約あり・未通知だけ取得
        def work_rows():
            return (
                sb.table("slots")
                .select("id,panel_id,start_at,reserver_user_id,notified")
                .eq("notified", False)
                .not_.is_("reserver_user_id", "null")
                .execute()
                .data
                or []
            )

        rows = await self._db(work_rows)
        now = jst_now()

        for slot in rows:
            # botが落ちかけてるなら抜ける
            try:
                if bot.is_closed() or (hasattr(bot, "is_ready") and not bot.is_ready()):
                    return
            except Exception:
                return

            start = from_utc_iso(slot["start_at"])
            diff = (start - now).total_seconds()

            # 3分前（誤差吸収）
            if not (160 <= diff <= 220):
                continue

            # panel設定チェック
            def work_panel():
                return sb.table("panels").select("notify_enabled,notify_paused,notify_channel_id,everyone").eq("id", slot["panel_id"]).limit(1).execute().data or []
            panel_rows = await self._db(work_panel)
            if not panel_rows:
                continue
            panel = panel_rows[0]

            if not panel.get("notify_enabled", True):
                continue
            if panel.get("notify_paused", False):
                continue

            notify_ch = bot.get_channel(int(panel["notify_channel_id"]))
            if not notify_ch:
                continue

            uid = str(slot["reserver_user_id"])
            mention = f"<@{uid}>"
            if panel.get("everyone"):
                mention = f"@everyone {mention}"

            try:
                await notify_ch.send(f"⏰ 3分前：{fmt_hm(start)} の枠です {mention}")
            except Exception:
                continue

            def work_set_notified():
                sb.table("slots").update({"notified": True}).eq("id", slot["id"]).execute()
            await self._db(work_set_notified)