# utils/data_manager.py
import asyncio
from datetime import timedelta
import discord

from utils.db import sb
from utils.time_utils import to_utc_iso, from_utc_iso, fmt_hm
from views.panel_view import PanelView, build_panel_embed


class DataManager:
    async def _db(self, fn):
        return await asyncio.to_thread(fn)

    def _require_db(self):
        if sb is None:
            raise RuntimeError("Supabase未接続（SUPABASE_URL/KEY を確認）")

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
        everyone: bool,
    ):
        self._require_db()

        # panels insert
        try:
            def work_insert_panel():
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
                            "notify_paused": False,
                            "everyone": bool(everyone),
                        }
                    )
                    .execute()
                    .data
                )

            panel = await self._db(work_insert_panel)
        except Exception:
            return {"ok": False, "error": "その時間帯に既に募集があります（重複不可）"}

        if not panel:
            return {"ok": False, "error": "作成失敗"}

        panel_id = int(panel[0]["id"])

        # slots insert
        inserts = []
        cur = start_at
        while cur < end_at:
            nxt = cur + timedelta(minutes=int(interval_minutes))
            inserts.append(
                {
                    "panel_id": panel_id,
                    "start_at": to_utc_iso(cur),
                    "end_at": to_utc_iso(nxt),
                    "slot_time": fmt_hm(cur),
                    "is_break": False,
                    "reserver_user_id": None,
                    "reserver_name": None,
                    "reserved_at": None,
                    "notified": False,
                }
            )
            cur = nxt

        if inserts:
            await self._db(lambda: sb.table("slots").insert(inserts).execute())

        return {"ok": True, "panel_id": panel_id}

    async def render_panel(self, bot: discord.Client, panel_id: int):
        self._require_db()

        panel_rows = await self._db(lambda: sb.table("panels").select("*").eq("id", panel_id).execute().data or [])
        if not panel_rows:
            return
        panel = panel_rows[0]

        ch = bot.get_channel(int(panel["channel_id"]))
        if not ch:
            return

        slots = await self._db(
            lambda: sb.table("slots").select("*").eq("panel_id", panel_id).order("start_at").execute().data or []
        )

        lines = []
        for r in slots[:25]:
            sdt = from_utc_iso(r["start_at"])
            label = fmt_hm(sdt)
            if r.get("is_break"):
                dot = "⚪"
                mention = ""
            elif r.get("reserver_user_id"):
                dot = "🔴"
                mention = f" <@{r['reserver_user_id']}>"
            else:
                dot = "🟢"
                mention = ""
            lines.append(f"{dot} {label}{mention}")

        title = panel.get("title") or "募集パネル"
        day_text = f"📅 {panel['day']}（JST） / interval {panel['interval_minutes']}min"
        embed = build_panel_embed(title, day_text, lines)
        view = PanelView()

        # @everyone は「募集投稿の1回だけ」
        content = "@everyone" if bool(panel.get("everyone")) else None

        msg = await ch.send(content=content, embed=embed, view=view)

        # panel_message_id保存（次の段階で更新編集に使う）
        await self._db(lambda: sb.table("panels").update({"panel_message_id": str(msg.id)}).eq("id", panel_id).execute())