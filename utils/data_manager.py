# utils/data_manager.py
import asyncio
from datetime import timedelta
import discord
from utils.time_utils import jst_now, to_utc_iso, from_utc_iso, fmt_hm
from utils.db import sb
from views.panel_view import PanelView


class DataManager:

    async def _db(self, fn):
        return await asyncio.to_thread(fn)

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
        everyone=False,
    ):
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
                            "interval_minutes": interval_minutes,
                            "notify_channel_id": notify_channel_id,
                            "created_by": created_by,
                            "notify_enabled": True,
                            "notify_paused": False,
                        }
                    )
                    .execute()
                    .data
                )

            panel = await self._db(insert_panel)
            panel_id = panel[0]["id"]

            inserts = []
            cur = start_at
            while cur < end_at:
                nxt = cur + timedelta(minutes=interval_minutes)
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
    async def render_panel(self, bot, panel_id):
        panel = (
            await self._db(
                lambda: sb.table("panels").select("*").eq("id", panel_id).execute().data
            )
        )[0]

        slots = await self._db(
            lambda: sb.table("slots")
            .select("*")
            .eq("panel_id", panel_id)
            .order("start_at")
            .execute()
            .data
        )

        channel = bot.get_channel(int(panel["channel_id"]))

        lines = []
        buttons = []

        for s in slots[:20]:
            start = from_utc_iso(s["start_at"])
            label = fmt_hm(start)

            if s["is_break"]:
                emoji = "⚪"
                style = discord.ButtonStyle.secondary
                disabled = True
            elif s["reserver_user_id"]:
                emoji = "🔴"
                style = discord.ButtonStyle.danger
                disabled = False
            else:
                emoji = "🟢"
                style = discord.ButtonStyle.success
                disabled = False

            lines.append(f"{emoji} {label}")
            buttons.append(
                {
                    "slot_id": s["id"],
                    "label": label,
                    "style": style,
                    "disabled": disabled,
                }
            )

        embed = discord.Embed(
            title=panel.get("title") or "募集パネル",
            description="\n".join(lines),
        )

        view = PanelView(panel_id, buttons, notify_paused=panel["notify_paused"])

        if panel.get("panel_message_id"):
            try:
                msg = await channel.fetch_message(int(panel["panel_message_id"]))
                await msg.edit(embed=embed, view=view)
                return
            except Exception:
                pass

        msg = await channel.send(embed=embed, view=view)

        await self._db(
            lambda: sb.table("panels")
            .update({"panel_message_id": str(msg.id)})
            .eq("id", panel_id)
            .execute()
        )

    # -----------------------------
    # 予約切替
    # -----------------------------
    async def toggle_reserve(self, slot_id, user_id):
        slot = (
            await self._db(
                lambda: sb.table("slots").select("*").eq("id", slot_id).execute().data
            )
        )[0]

        if slot["is_break"]:
            return False, "休憩中です"

        if not slot["reserver_user_id"]:
            await self._db(
                lambda: sb.table("slots")
                .update(
                    {
                        "reserver_user_id": str(user_id),
                        "notified": False,
                    }
                )
                .eq("id", slot_id)
                .execute()
            )
            return True, "予約しました"

        if str(slot["reserver_user_id"]) == str(user_id):
            await self._db(
                lambda: sb.table("slots")
                .update(
                    {
                        "reserver_user_id": None,
                        "notified": False,
                    }
                )
                .eq("id", slot_id)
                .execute()
            )
            return True, "キャンセルしました"

        return False, "他の人が予約済み"

    # -----------------------------
    # 通知トグル
    # -----------------------------
    async def toggle_notify_paused(self, panel_id):
        panel = (
            await self._db(
                lambda: sb.table("panels").select("*").eq("id", panel_id).execute().data
            )
        )[0]

        new_val = not panel["notify_paused"]

        await self._db(
            lambda: sb.table("panels")
            .update({"notify_paused": new_val})
            .eq("id", panel_id)
            .execute()
        )

        return new_val

    # -----------------------------
    # 3分前通知
    # -----------------------------
    async def send_3min_reminders(self, bot):
        rows = await self._db(
            lambda: sb.table("slots")
            .select("*")
            .eq("notified", False)
            .not_.is_("reserver_user_id", "null")
            .execute()
            .data
        )

        now = jst_now()

        for slot in rows:
            start = from_utc_iso(slot["start_at"])
            diff = (start - now).total_seconds()

            if not (160 <= diff <= 220):
                continue

            panel = (
                await self._db(
                    lambda: sb.table("panels")
                    .select("*")
                    .eq("id", slot["panel_id"])
                    .execute()
                    .data
                )
            )[0]

            if panel["notify_paused"]:
                continue

            ch = bot.get_channel(int(panel["channel_id"]))
            if not ch:
                continue

            await ch.send(f"⏰ 3分前です <@{slot['reserver_user_id']}>")

            await self._db(
                lambda: sb.table("slots")
                .update({"notified": True})
                .eq("id", slot["id"])
                .execute()
            )