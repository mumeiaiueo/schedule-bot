# utils/data_manager.py
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
            raise RuntimeError("Supabase未接続（SUPABASE_URL/KEY を確認）")

    # =============================
    # 管理者 / 管理ロール
    # =============================

    async def get_manager_role_id(self, guild_id: str):
        self._require_db()

        def work():
            rows = (
                sb.table("guild_settings")
                .select("manager_role_id")
                .eq("guild_id", int(guild_id))
                .limit(1)
                .execute()
                .data or []
            )
            return rows[0].get("manager_role_id") if rows else None

        return await self._db(work)

    async def set_manager_role_id(self, guild_id: str, role_id: int | None):
        self._require_db()

        def work():
            sb.table("guild_settings").upsert(
                {"guild_id": int(guild_id), "manager_role_id": role_id},
                on_conflict="guild_id",
            ).execute()

        await self._db(work)

        if role_id is None:
            return True, "✅ 管理ロールを解除しました（管理者のみ操作可能になります）"
        return True, "✅ 管理ロールを設定しました（このロール持ちは管理操作OK）"

    async def is_manager(self, interaction: discord.Interaction) -> bool:
        # 管理者ならOK
        try:
            member = interaction.user
            if isinstance(member, discord.Member) and member.guild_permissions.administrator:
                return True
        except Exception:
            pass

        # 管理ロールならOK
        try:
            rid = await self.get_manager_role_id(str(interaction.guild_id))
            if not rid:
                return False
            member = interaction.user
            if not isinstance(member, discord.Member):
                return False
            return any(r.id == int(rid) for r in member.roles)
        except Exception:
            return False

    # =============================
    # パネル作成（@everyoneは最初の1回だけ）
    # =============================

    async def create_panel(
        self,
        guild_id: str,
        channel_id: str,
        day_date,
        title: str | None,
        start_at,
        end_at,
        interval_minutes: int,
        created_by: str,
        everyone: bool,
    ):
        self._require_db()

        # panels insert
        try:
            def work_insert_panel():
                return (
                    sb.table("panels")
                    .insert({
                        "guild_id": guild_id,
                        "channel_id": channel_id,
                        "day": str(day_date),
                        "title": title,
                        "start_at": to_utc_iso(start_at),
                        "end_at": to_utc_iso(end_at),
                        "interval_minutes": int(interval_minutes),
                        "created_by": created_by,
                        "panel_message_id": None,
                        "notify_paused": False,   # 3分前通知OFFならTrue
                        "notify_enabled": True,   # 予備（常にTrue運用でもOK）
                        "everyone": bool(everyone),
                    })
                    .execute()
                    .data
                )

            panel = await self._db(work_insert_panel)

        except Exception:
            return {"ok": False, "error": "その時間帯に既に募集があります（/reset_channel で消してから作り直してね）"}

        if not panel:
            return {"ok": False, "error": "作成失敗"}

        panel_id = int(panel[0]["id"])

        # slots insert
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
                "channel_id": int(channel_id),
                "guild_id": int(guild_id),
                "slot_time": fmt_hm(cur),
            })
            cur = nxt

        if inserts:
            await self._db(lambda: sb.table("slots").insert(inserts).execute())

        return {"ok": True, "panel_id": panel_id}

    # =============================
    # reset（指定チャンネルの募集を削除）
    # =============================

    async def delete_panel_by_channel_day(self, guild_id: str, channel_id: str, day_date) -> bool:
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
                .data or []
            )
            ids = [p["id"] for p in panels]
            if not ids:
                return False
            sb.table("slots").delete().in_("panel_id", ids).execute()
            sb.table("panels").delete().in_("id", ids).execute()
            return True

        return await self._db(work)

    # =============================
    # 3分前通知 ON/OFF（管理者が押す）
    # =============================

    async def toggle_notify_paused(self, panel_id: int):
        self._require_db()

        def work():
            rows = (
                sb.table("panels")
                .select("notify_paused")
                .eq("id", panel_id)
                .limit(1)
                .execute()
                .data or []
            )
            if not rows:
                return None
            cur = bool(rows[0].get("notify_paused", False))
            new_val = not cur
            sb.table("panels").update({"notify_paused": new_val}).eq("id", panel_id).execute()
            return new_val

        new_val = await self._db(work)
        if new_val is None:
            return False, "パネルが見つかりません"
        return True, ("3分前通知をOFFにしました" if new_val else "3分前通知をONにしました")

    # =============================
    # パネル描画
    # =============================

    async def render_panel(self, bot: discord.Client, panel_id: int):
        self._require_db()

        panel_rows = await self._db(lambda: sb.table("panels").select("*").eq("id", panel_id).execute().data)
        if not panel_rows:
            return

        panel = panel_rows[0]
        channel = bot.get_channel(int(panel["channel_id"]))
        if not channel:
            return

        slots = await self._db(
            lambda: sb.table("slots").select("*").eq("panel_id", panel_id).order("start_at").execute().data or []
        )

        lines = []
        buttons = []

        # 画面都合で20枠だけボタン化、表示は最大25行まで
        for r in slots[:25]:
            sdt = from_utc_iso(r["start_at"])
            label = fmt_hm(sdt)

            if r.get("is_break"):
                dot = "⚪"
                style = discord.ButtonStyle.secondary
                disabled = True
                mention = ""
            elif r.get("reserver_user_id"):
                dot = "🔴"
                style = discord.ButtonStyle.danger
                disabled = False
                mention = f" <@{r['reserver_user_id']}>"
            else:
                dot = "🟢"
                style = discord.ButtonStyle.success
                disabled = False
                mention = ""

            lines.append(f"{dot} {label}{mention}")

            # ボタンは20個まで（PanelViewが20想定）
            if len(buttons) < 20:
                buttons.append({"slot_id": r["id"], "label": label, "style": style, "disabled": disabled})

        day_text = f"📅 {panel['day']}（JST） / interval {panel['interval_minutes']}min"
        title = panel.get("title") or "募集パネル"
        embed = build_panel_embed(title, day_text, lines)
        view = PanelView(panel_id, buttons, notify_paused=bool(panel.get("notify_paused", False)))

        mid = panel.get("panel_message_id")

        # 既存メッセ更新（@everyoneは付けない）
        if mid:
            try:
                msg = await channel.fetch_message(int(mid))
                await msg.edit(content=None, embed=embed, view=view)
                return
            except Exception:
                pass

        # 初回投稿（@everyoneは最初の1回だけ）
        content = "@everyone 募集開始！" if bool(panel.get("everyone")) else None
        msg = await channel.send(content=content, embed=embed, view=view)

        await self._db(
            lambda: sb.table("panels").update({"panel_message_id": str(msg.id)}).eq("id", panel_id).execute()
        )

    # =============================
    # 予約（本人は押すとキャンセル）
    # =============================

    async def toggle_reserve(self, slot_id: int, user_id: str, user_name: str):
        self._require_db()

        rows = await self._db(lambda: sb.table("slots").select("*").eq("id", slot_id).execute().data)
        if not rows:
            return False, "枠が見つかりません"
        slot = rows[0]

        if slot.get("is_break"):
            return False, "休憩枠です（予約できません）"

        # 予約する
        if not slot.get("reserver_user_id"):
            updated = await self._db(
                lambda: sb.table("slots")
                .update({
                    "reserver_user_id": str(user_id),
                    "reserver_name": user_name,
                    "reserved_at": to_utc_iso(jst_now()),
                    "notified": False,
                })
                .eq("id", slot_id)
                .is_("reserver_user_id", None)
                .execute()
                .data
            )
            if not updated:
                return False, "その枠はもう埋まっています"
            return True, "予約しました ✅（もう一度押すとキャンセル）"

        # 本人キャンセル
        if str(slot.get("reserver_user_id")) == str(user_id):
            await self._db(
                lambda: sb.table("slots").update({
                    "reserver_user_id": None,
                    "reserver_name": None,
                    "reserved_at": None,
                    "notified": False,
                }).eq("id", slot_id).execute()
            )
            return True, "キャンセルしました ✅"

        return False, "その枠は埋まっています（本人のみキャンセル可）"

    # =============================
    # 休憩（管理者/管理ロール）
    # =============================

    async def build_break_select_view(self, panel_id: int) -> BreakSelectView:
        self._require_db()

        slots = await self._db(
            lambda: sb.table("slots").select("*").eq("panel_id", panel_id).order("start_at").execute().data or []
        )

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

        return BreakSelectView(panel_id, options)

    async def toggle_break_slot(self, panel_id: int, slot_id: int):
        self._require_db()

        rows = await self._db(
            lambda: sb.table("slots").select("*").eq("id", slot_id).eq("panel_id", panel_id).execute().data
        )
        if not rows:
            return False, "枠が見つかりません"
        slot = rows[0]

        # 予約ありは休憩不可（ただし既に休憩なら解除OK）
        if slot.get("reserver_user_id") and not bool(slot.get("is_break")):
            return False, "予約が入っている枠は休憩にできません"

        new_val = not bool(slot.get("is_break"))
        await self._db(lambda: sb.table("slots").update({"is_break": new_val}).eq("id", slot_id).execute())
        return True, ("休憩にしました" if new_val else "休憩を解除しました")

    # =============================
    # 3分前通知（チャンネル＝パネルのチャンネルに送る）
    # =============================

    async def send_3min_reminders(self, bot: discord.Client):
        try:
            if bot.is_closed() or (hasattr(bot, "is_ready") and not bot.is_ready()):
                return
        except Exception:
            return

        self._require_db()

        rows = await self._db(
            lambda: sb.table("slots")
            .select("*")
            .eq("notified", False)
            .not_.is_("reserver_user_id", "null")
            .execute()
            .data or []
        )

        now = jst_now()

        for slot in rows:
            start = from_utc_iso(slot["start_at"])
            diff = (start - now).total_seconds()

            # 3分前（だいたい160〜220秒）
            if not (160 <= diff <= 220):
                continue

            panel_rows = await self._db(
                lambda: sb.table("panels").select("*").eq("id", slot["panel_id"]).execute().data or []
            )
            if not panel_rows:
                continue

            panel = panel_rows[0]
            if panel.get("notify_enabled", True) is False:
                continue
            if panel.get("notify_paused", False):
                continue

            ch = bot.get_channel(int(panel["channel_id"]))
            if not ch:
                continue

            try:
                uid = str(slot["reserver_user_id"])
                await ch.send(f"⏰ 3分前：{fmt_hm(start)} の枠です <@{uid}>")
            except Exception:
                continue

            await self._db(lambda: sb.table("slots").update({"notified": True}).eq("id", slot["id"]).execute())