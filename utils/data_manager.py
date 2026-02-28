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
            raise RuntimeError("Supabaseが未接続です（SUPABASE_URL/KEY/DNS を確認）")

    # -----------------------------
    # ✅ 管理者 or 管理ロール判定
    # -----------------------------
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
                },
                on_conflict="guild_id",
            ).execute()

        await self._db(work)

        if role_id is None:
            return (True, "✅ 管理ロール設定を解除しました（管理者のみ実行可能になります）")
        return (True, "✅ 管理ロールを設定しました（このロール持ちは管理コマンド実行OK）")

    async def is_manager(self, interaction: discord.Interaction) -> bool:
        # 管理者ならOK
        try:
            m = interaction.user
            if isinstance(m, discord.Member) and m.guild_permissions.administrator:
                return True
        except Exception:
            pass

        # 管理ロールならOK
        try:
            rid = await self.get_manager_role_id(str(interaction.guild_id))
            if not rid:
                return False
            m = interaction.user
            if not isinstance(m, discord.Member):
                return False
            return any(r.id == int(rid) for r in m.roles)
        except Exception:
            return False

    # -----------------------------
    # panels
    # -----------------------------
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
        self._require_db()

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
                            "notify_channel_id": notify_channel_id,
                            "created_by": created_by,
                            "notify_enabled": True,
                            "notify_paused": False,
                        }
                    )
                    .execute()
                    .data
                )

            panel = await self._db(work_insert_panel)
        except Exception:
            return {
                "ok": False,
                "error": "このチャンネルでは、その時間帯に既に募集があります（時間が重なる募集は作れません）。作り直すなら /reset_channel を先に実行してね。"
            }

        if not panel:
            return {"ok": False, "error": "作成に失敗しました"}

        panel_id = panel[0]["id"]

        inserts = []
        cur = start_at
        while cur < end_at:
            nxt = cur + timedelta(minutes=int(interval_minutes))
            inserts.append(
                {
                    "panel_id": panel_id,
                    "start_at": to_utc_iso(cur),
                    "end_at": to_utc_iso(nxt),
                    "is_break": False,
                    "reserver_user_id": None,
                    "reserver_name": None,
                    "reserved_at": None,
                    "notified": False,
                    "channel_id": int(channel_id),
                    "guild_id": int(guild_id),
                    "slot_time": fmt_hm(cur),
                }
            )
            cur = nxt

        if inserts:
            def work_insert_slots():
                sb.table("slots").insert(inserts).execute()

            await self._db(work_insert_slots)

        return {"ok": True, "panel_id": panel_id}

    # -----------------------------
    # reset 用：指定日の募集を削除
    # -----------------------------
    async def delete_panel_by_channel_day(self, guild_id: str, channel_id: str, day_date) -> bool:
        """
        /reset_channel 用
        指定 guild/channel/day の panel を消す（slots も一緒に消す）
        """
        self._require_db()
        day_str = str(day_date)

        def work():
            panels = (
                sb.table("panels")
                .select("id")
                .eq("guild_id", guild_id)
                .eq("channel_id", channel_id)
                .eq("day", day_str)
                .execute()
                .data
                or []
            )

            panel_ids = [p["id"] for p in panels]
            if panel_ids:
                sb.table("slots").delete().in_("panel_id", panel_ids).execute()
                sb.table("panels").delete().in_("id", panel_ids).execute()
                return True
            return False

        return await self._db(work)

    # -----------------------------
    # render
    # -----------------------------
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
            buttons.append(
                {
                    "slot_id": r["id"],
                    "label": label,
                    "style": style,
                    "disabled": disabled,
                }
            )

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

    # （以下 toggle_reserve / break / send_3min_reminders はあなたのままでOK）