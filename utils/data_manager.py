# utils/data_manager.py
import asyncio
from datetime import timedelta
import discord

from utils.db import sb
from utils.time_utils import jst_now, to_utc_iso, from_utc_iso, fmt_hm
from views.panel_view import PanelView, BreakSelectView, build_panel_embed


class DataManager:
    def __init__(self):
        # render連打防止（panel_id単位でロック）
        self._render_locks: dict[int, asyncio.Lock] = {}

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
                            "guild_id": str(guild_id),
                            "channel_id": str(channel_id),
                            "day": str(day_date),
                            "title": title,
                            "start_at": to_utc_iso(start_at),
                            "end_at": to_utc_iso(end_at),
                            "interval_minutes": int(interval_minutes),
                            "notify_channel_id": str(notify_channel_id),
                            "created_by": str(created_by),
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
                    # slots側は int で持つ前提（あなたの既存コード互換）
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
    # reset 用：指定日の募集を削除（slotsも消す）
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
                .eq("guild_id", str(guild_id))
                .eq("channel_id", str(channel_id))
                .eq("day", day_str)
                .execute()
                .data
                or []
            )

            panel_ids = [p["id"] for p in panels]
            if not panel_ids:
                return False

            sb.table("slots").delete().in_("panel_id", panel_ids).execute()
            sb.table("panels").delete().in_("id", panel_ids).execute()
            return True

        return await self._db(work)

    # （互換用：日付指定なし削除が欲しい場合）
    async def delete_panel(self, guild_id: str, channel_id: str) -> bool:
        self._require_db()

        def work():
            panels = (
                sb.table("panels")
                .select("id")
                .eq("guild_id", str(guild_id))
                .eq("channel_id", str(channel_id))
                .execute()
                .data
                or []
            )
            panel_ids = [p["id"] for p in panels]
            if panel_ids:
                sb.table("slots").delete().in_("panel_id", panel_ids).execute()
                sb.table("panels").delete().eq("guild_id", str(guild_id)).eq("channel_id", str(channel_id)).execute()
                return True
            return False

        return await self._db(work)

    # -----------------------------
    # render（429対策：ロック＋軽いスリープ）
    # -----------------------------
    async def render_panel(self, bot: discord.Client, panel_id: int):
        self._require_db()

        # panel_id単位のロック（連打で429になりやすいので抑える）
        lock = self._render_locks.get(panel_id)
        if lock is None:
            lock = asyncio.Lock()
            self._render_locks[panel_id] = lock

        async with lock:
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
                    await asyncio.sleep(0.3)  # API間隔を少し空ける
                    return
                except Exception:
                    pass

            msg = await channel.send(embed=embed, view=view)

            def work_update_mid():
                sb.table("panels").update({"panel_message_id": str(msg.id)}).eq("id", panel_id).execute()

            await self._db(work_update_mid)
            await asyncio.sleep(0.3)

    # -----------------------------
    # reserve
    # -----------------------------
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

        if not slot.get("reserver_user_id"):
            def work_update():
                return (
                    sb.table("slots")
                    .update(
                        {
                            "reserver_user_id": str(user_id),
                            "reserver_name": user_name,
                            "reserved_at": to_utc_iso(jst_now()),
                            "notified": False,
                        }
                    )
                    .eq("id", slot_id)
                    .is_("reserver_user_id", None)
                    .execute()
                    .data
                )

            updated = await self._db(work_update)
            if not updated:
                return (False, "その枠はもう埋まっています")
            return (True, "予約しました ✅（もう一度押すとキャンセル）")

        if str(slot.get("reserver_user_id")) == str(user_id):
            def work_cancel():
                sb.table("slots").update(
                    {
                        "reserver_user_id": None,
                        "reserver_name": None,
                        "reserved_at": None,
                        "notified": False,
                    }
                ).eq("id", slot_id).execute()

            await self._db(work_cancel)
            return (True, "キャンセルしました ✅")

        return (False, "その枠は埋まっています（本人のみキャンセル可）")

    # -----------------------------
    # break
    # -----------------------------
    async def build_break_select_view(self, panel_id: int) -> BreakSelectView:
        self._require_db()

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
        self._require_db()

        def work_slot():
            return (
                sb.table("slots")
                .select("*")
                .eq("id", slot_id)
                .eq("panel_id", panel_id)
                .execute()
                .data
            )

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

    # -----------------------------
    # 3min reminders
    # -----------------------------
    async def send_3min_reminders(self, bot: discord.Client):
        try:
            if bot.is_closed() or (hasattr(bot, "is_ready") and not bot.is_ready()):
                return
        except Exception:
            return

        self._require_db()

        def work_rows():
            return (
                sb.table("slots")
                .select("*")
                .eq("notified", False)
                .not_.is_("reserver_user_id", "null")
                .execute()
                .data
                or []
            )

        try:
            rows = await self._db(work_rows)
        except Exception:
            return

        now = jst_now()

        for slot in rows:
            start = from_utc_iso(slot["start_at"])
            diff = (start - now).total_seconds()

            if not (160 <= diff <= 220):
                continue

            def work_panel():
                return sb.table("panels").select("*").eq("id", slot["panel_id"]).execute().data or []

            try:
                panel_rows = await self._db(work_panel)
            except Exception:
                continue

            if not panel_rows:
                continue

            panel = panel_rows[0]

            if not panel.get("notify_enabled", True):
                continue
            if panel.get("notify_paused", False):
                continue

            try:
                notify_ch = bot.get_channel(int(panel["notify_channel_id"]))
            except Exception:
                notify_ch = None
            if not notify_ch:
                continue

            try:
                uid = str(slot["reserver_user_id"])
                await notify_ch.send(f"⏰ 3分前：{fmt_hm(start)} の枠です <@{uid}>")
                await asyncio.sleep(0.2)  # 連投抑制
            except Exception:
                continue

            def work_set_notified():
                sb.table("slots").update({"notified": True}).eq("id", slot["id"]).execute()

            try:
                await self._db(work_set_notified)
            except Exception:
                pass