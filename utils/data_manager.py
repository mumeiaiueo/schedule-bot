# utils/data_manager.py
from __future__ import annotations

import asyncio
from datetime import timedelta
import discord

from utils.time_utils import jst_now, to_utc_iso, from_utc_iso, fmt_hm
from utils.db import sb
from views.panel_view import PanelView


class DataManager:
    async def _db(self, fn):
        return await asyncio.to_thread(fn)

    def _require_db(self):
        if sb is None:
            raise RuntimeError("Supabase未接続（SUPABASE_URL/KEY を確認）")

    # -----------------------------
    # ✅ 管理者 / 管理ロール
    # -----------------------------
    async def get_manager_role_id(self, guild_id: str) -> int | None:
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
            v = rows[0].get("manager_role_id")
            return int(v) if v is not None else None

        return await self._db(work)

    async def set_manager_role_id(self, guild_id: str, role_id: int | None) -> None:
        self._require_db()

        def work():
            sb.table("guild_settings").upsert(
                {"guild_id": int(guild_id), "manager_role_id": role_id},
                on_conflict="guild_id",
            ).execute()

        await self._db(work)

    async def is_manager(self, interaction: discord.Interaction) -> bool:
        """管理者 or 指定の管理ロール保持者なら True"""
        # 管理者
        try:
            m = interaction.user
            if isinstance(m, discord.Member) and m.guild_permissions.administrator:
                return True
        except Exception:
            pass

        # 管理ロール
        try:
            rid = await self.get_manager_role_id(str(interaction.guild_id))
            if not rid:
                return False
            m = interaction.user
            if not isinstance(m, discord.Member):
                return False
            return any(r.id == rid for r in m.roles)
        except Exception:
            return False

    # -----------------------------
    # パネル作成
    # -----------------------------
    async def create_panel(
        self,
        guild_id: str,
        channel_id: str,
        day_date,
        title,
        start_at,
        end_at,
        interval_minutes,
        notify_channel_id,
        created_by,
        everyone: bool = False,
    ):
        self._require_db()
        try:
            def insert_panel():
                return (
                    sb.table("panels")
                    .insert(
                        {
                            "guild_id": guild_id,
                            "channel_id": channel_id,
                            "day": str(day_date),
                            "title": title,
                            "start_at": to_utc_iso(start_at),
                            "end_at": to_utc_iso(end_at),
                            "interval_minutes": int(interval_minutes),
                            "notify_channel_id": str(notify_channel_id),
                            "created_by": created_by,
                            "notify_enabled": True,
                            "notify_paused": False,
                        }
                    )
                    .execute()
                    .data
                )

            panel = await self._db(insert_panel)
            panel_id = int(panel[0]["id"])

            inserts = []
            cur = start_at
            while cur < end_at:
                nxt = cur + timedelta(minutes=int(interval_minutes))
                inserts.append(
                    {
                        "panel_id": panel_id,
                        "start_at": to_utc_iso(cur),
                        "end_at": to_utc_iso(nxt),
                        "reserver_user_id": None,
                        "is_break": False,
                        "notified": False,
                    }
                )
                cur = nxt

            if inserts:
                await self._db(lambda: sb.table("slots").insert(inserts).execute())

            return {"ok": True, "panel_id": panel_id}

        except Exception as e:
            return {"ok": False, "error": str(e)}

    # -----------------------------
    # パネル描画
    # -----------------------------
    async def render_panel(self, bot, panel_id: int):
        self._require_db()

        panel = (
            await self._db(lambda: sb.table("panels").select("*").eq("id", panel_id).execute().data)
        )
        if not panel:
            return
        panel = panel[0]

        slots = await self._db(
            lambda: sb.table("slots")
            .select("*")
            .eq("panel_id", panel_id)
            .order("start_at")
            .execute()
            .data
        )

        channel = bot.get_channel(int(panel["channel_id"]))
        if not channel:
            return

        lines = []
        buttons = []

        for s in slots[:20]:
            start = from_utc_iso(s["start_at"])
            label = fmt_hm(start)

            if s.get("is_break"):
                emoji = "⚪"
                style = discord.ButtonStyle.secondary
                disabled = True
            elif s.get("reserver_user_id"):
                emoji = "🔴"
                style = discord.ButtonStyle.danger
                disabled = False
            else:
                emoji = "🟢"
                style = discord.ButtonStyle.success
                disabled = False

            mention = f" <@{s['reserver_user_id']}>" if s.get("reserver_user_id") else ""
            lines.append(f"{emoji} {label}{mention}")
            buttons.append(
                {
                    "slot_id": int(s["id"]),
                    "label": label,
                    "style": style,
                    "disabled": disabled,
                }
            )

        embed = discord.Embed(
            title=panel.get("title") or "募集パネル",
            description="\n".join(lines),
        )

        view = PanelView(panel_id, buttons, notify_paused=bool(panel.get("notify_paused", False)))

        mid = panel.get("panel_message_id")
        if mid:
            try:
                msg = await channel.fetch_message(int(mid))
                await msg.edit(embed=embed, view=view)
                return
            except Exception:
                pass

        msg = await channel.send(embed=embed, view=view)

        await self._db(
            lambda: sb.table("panels").update({"panel_message_id": str(msg.id)}).eq("id", panel_id).execute()
        )

    # -----------------------------
    # 予約切替
    # -----------------------------
    async def toggle_reserve(self, slot_id: int, user_id: str):
        self._require_db()

        slot = (
            await self._db(lambda: sb.table("slots").select("*").eq("id", slot_id).execute().data)
        )
        if not slot:
            return False, "枠が見つかりません"
        slot = slot[0]

        if slot.get("is_break"):
            return False, "休憩中です"

        if not slot.get("reserver_user_id"):
            await self._db(
                lambda: sb.table("slots")
                .update({"reserver_user_id": str(user_id), "notified": False})
                .eq("id", slot_id)
                .execute()
            )
            return True, "予約しました"

        if str(slot.get("reserver_user_id")) == str(user_id):
            await self._db(
                lambda: sb.table("slots")
                .update({"reserver_user_id": None, "notified": False})
                .eq("id", slot_id)
                .execute()
            )
            return True, "キャンセルしました"

        return False, "他の人が予約済みです"

    # -----------------------------
    # 通知トグル（パネル単位）
    # -----------------------------
    async def toggle_notify_paused(self, panel_id: int) -> bool:
        self._require_db()

        panel = (
            await self._db(lambda: sb.table("panels").select("notify_paused").eq("id", panel_id).limit(1).execute().data)
        )
        if not panel:
            raise RuntimeError("panel not found")

        cur = bool(panel[0].get("notify_paused", False))
        new_val = not cur

        await self._db(
            lambda: sb.table("panels").update({"notify_paused": new_val}).eq("id", panel_id).execute()
        )
        return new_val

    # -----------------------------
    # 3分前通知（募集チャンネル固定）
    # -----------------------------
    async def send_3min_reminders(self, bot):
        self._require_db()

        rows = await self._db(
            lambda: sb.table("slots")
            .select("*")
            .eq("notified", False)
            .not_.is_("reserver_user_id", "null")
            .execute()
            .data
        )

        now = jst_now()

        for slot in rows or []:
            start = from_utc_iso(slot["start_at"])
            diff = (start - now).total_seconds()

            if not (160 <= diff <= 220):
                continue

            panel = await self._db(
                lambda: sb.table("panels").select("*").eq("id", slot["panel_id"]).limit(1).execute().data
            )
            if not panel:
                continue
            panel = panel[0]

            if bool(panel.get("notify_paused", False)):
                continue

            ch = bot.get_channel(int(panel["channel_id"]))
            if not ch:
                continue

            try:
                await ch.send(f"⏰ 3分前です <@{slot['reserver_user_id']}>")
            except Exception:
                continue

            await self._db(
                lambda: sb.table("slots").update({"notified": True}).eq("id", slot["id"]).execute()
            )