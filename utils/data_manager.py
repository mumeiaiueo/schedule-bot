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
            raise RuntimeError("Supabase未接続")

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
            return rows[0]["manager_role_id"] if rows else None

        return await self._db(work)

    async def set_manager_role_id(self, guild_id: str, role_id: int | None):
        self._require_db()

        def work():
            # upsert
            payload = {
                "guild_id": int(guild_id),
                "manager_role_id": (int(role_id) if role_id is not None else None),
            }
            sb.table("guild_settings").upsert(payload).execute()
            return True

        await self._db(work)
        if role_id is None:
            return True, "✅ 管理ロールを解除しました"
        return True, f"✅ 管理ロールを設定しました: role_id={role_id}"

    async def is_manager(self, interaction: discord.Interaction) -> bool:
        try:
            member = interaction.user
            if isinstance(member, discord.Member):
                if member.guild_permissions.administrator:
                    return True

                role_id = await self.get_manager_role_id(str(interaction.guild_id))
                if role_id:
                    return any(r.id == int(role_id) for r in member.roles)
        except Exception:
            pass
        return False

    # =============================
    # パネル作成
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
        notify_channel_id: str,
        created_by: str,
        everyone: bool,
    ):
        self._require_db()

        # 同じguild+channel+dayは1つだけにしたいならここで事前削除/チェックも可能
        # 今は「重複は insert 失敗で弾く」運用に合わせる

        try:
            def work_insert_panel():
                return (
                    sb.table("panels")
                    .insert({
                        "guild_id": int(guild_id),
                        "channel_id": int(channel_id),
                        "day": str(day_date),
                        "title": title,
                        "start_at": to_utc_iso(start_at),
                        "end_at": to_utc_iso(end_at),
                        "interval_minutes": int(interval_minutes),
                        "notify_channel_id": int(notify_channel_id),
                        "created_by": str(created_by),
                        "notify_paused": False,
                        "everyone": bool(everyone),
                    })
                    .execute()
                    .data
                )

            panel = await self._db(work_insert_panel)

        except Exception:
            return {"ok": False, "error": "その日/チャンネルに既に募集があります（/reset で削除してから）"}

        if not panel:
            return {"ok": False, "error": "作成失敗"}

        panel_id = int(panel[0]["id"])

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
                "slot_time": fmt_hm(cur),
            })
            cur = nxt

        if inserts:
            await self._db(lambda: sb.table("slots").insert(inserts).execute())

        return {"ok": True, "panel_id": panel_id}

    # =============================
    # 通知ON/OFF（パネル単位）
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
            cur = bool(rows[0]["notify_paused"])
            new_val = not cur
            sb.table("panels").update({"notify_paused": new_val}).eq("id", panel_id).execute()
            return new_val

        new_val = await self._db(work)
        if new_val is None:
            return False, "パネルが見つかりません"
        return True, ("通知OFFにしました" if new_val else "通知ONにしました")

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

        slots = await self._db(lambda: sb.table("slots").select("*").eq("panel_id", panel_id).order("start_at").execute().data or [])

        lines = []
        buttons = []

        for r in slots[:20]:
            sdt = from_utc_iso(r["start_at"])
            label = fmt_hm(sdt)

            if r["is_break"]:
                dot = "⚪"
                style = discord.ButtonStyle.secondary
                disabled = True
            elif r["reserver_user_id"]:
                dot = "🔴"
                style = discord.ButtonStyle.danger
                disabled = False
            else:
                dot = "🟢"
                style = discord.ButtonStyle.success
                disabled = False

            mention = f" <@{r['reserver_user_id']}>" if r["reserver_user_id"] else ""
            lines.append(f"{dot} {label}{mention}")

            buttons.append({
                "slot_id": int(r["id"]),
                "label": label,
                "style": style,
                "disabled": disabled,
            })

        subtitle = f"📅 {panel['day']}（JST） / interval {panel['interval_minutes']}min"
        embed = build_panel_embed(panel.get("title"), subtitle, lines)
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
        await self._db(lambda: sb.table("panels").update({"panel_message_id": str(msg.id)}).eq("id", panel_id).execute())

    # =============================
    # 予約（競合防止）
    # =============================

    async def toggle_reserve(self, slot_id: int, user_id: str, user_name: str):
        self._require_db()

        rows = await self._db(lambda: sb.table("slots").select("*").eq("id", slot_id).execute().data)
        if not rows:
            return False, "枠が見つかりません"
        slot = rows[0]

        if slot["is_break"]:
            return False, "休憩枠です"

        # 空き→予約（競合防止：is_(None) 条件）
        if not slot["reserver_user_id"]:
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
                return False, "すでに埋まっています"
            return True, "予約しました"

        # 自分→キャンセル
        if str(slot["reserver_user_id"]) == str(user_id):
            await self._db(lambda: sb.table("slots").update({
                "reserver_user_id": None,
                "reserver_name": None,
                "reserved_at": None,
                "notified": False,
            }).eq("id", slot_id).execute())
            return True, "キャンセルしました"

        return False, "他の人が予約済み"

    # =============================
    # 休憩（toggle）
    # =============================

    async def build_break_select_view(self, panel_id: int):
        self._require_db()
        slots = await self._db(lambda: sb.table("slots").select("*").eq("panel_id", panel_id).order("start_at").execute().data or [])

        options = []
        for s in slots[:25]:
            # 予約済みは休憩不可（仕様）
            if s["reserver_user_id"]:
                continue
            label = fmt_hm(from_utc_iso(s["start_at"]))
            state = "休憩" if s["is_break"] else "空き"
            options.append(discord.SelectOption(
                label=f"{label} ({state})",
                value=str(int(s["id"])),
            ))

        if not options:
            options = [discord.SelectOption(label="操作できる枠がありません", value="0")]

        return BreakSelectView(panel_id, options)

    async def toggle_break_slot(self, panel_id: int, slot_id: int):
        self._require_db()

        def work():
            rows = sb.table("slots").select("*").eq("id", slot_id).limit(1).execute().data or []
            if not rows:
                return None
            s = rows[0]
            if int(s["panel_id"]) != int(panel_id):
                return "mismatch"
            if s["reserver_user_id"]:
                return "reserved"
            new_val = not bool(s["is_break"])
            sb.table("slots").update({"is_break": new_val}).eq("id", slot_id).execute()
            return new_val

        res = await self._db(work)
        if res is None:
            return False, "枠が見つかりません"
        if res == "mismatch":
            return False, "不正な枠です"
        if res == "reserved":
            return False, "予約済み枠は休憩にできません"
        return True, ("休憩にしました" if res else "休憩を解除しました")

    # =============================
    # /reset（今日/明日を削除）
    # =============================

    async def delete_panels_by_day(self, guild_id: str, channel_id: str, day_str: str):
        self._require_db()

        def work():
            panels = (
                sb.table("panels")
                .select("id")
                .eq("guild_id", int(guild_id))
                .eq("channel_id", int(channel_id))
                .eq("day", day_str)
                .execute()
                .data or []
            )
            panel_ids = [int(p["id"]) for p in panels]
            if not panel_ids:
                return 0

            # slots -> panels の順で削除
            for pid in panel_ids:
                sb.table("slots").delete().eq("panel_id", pid).execute()
                sb.table("panels").delete().eq("id", pid).execute()
            return len(panel_ids)

        return await self._db(work)

    # =============================
    # 3分前通知（連続枠まとめて1回）
    # =============================

    async def send_3min_reminders(self, bot: discord.Client):
        self._require_db()

        # notified=False & reserverあり & is_break=False
        rows = await self._db(
            lambda: sb.table("slots")
            .select("*")
            .eq("notified", False)
            .eq("is_break", False)
            .not_.is_("reserver_user_id", "null")
            .order("start_at")
            .execute()
            .data or []
        )

        now = jst_now()

        # 3分前対象だけ拾う
        targets = []
        for slot in rows:
            start = from_utc_iso(slot["start_at"])
            diff = (start - now).total_seconds()
            if 160 <= diff <= 220:
                targets.append(slot)

        if not targets:
            return

        # panelごとにまとめる
        by_panel = {}
        for s in targets:
            by_panel.setdefault(int(s["panel_id"]), []).append(s)

        for panel_id, slots in by_panel.items():
            panel_rows = await self._db(lambda: sb.table("panels").select("*").eq("id", panel_id).limit(1).execute().data or [])
            if not panel_rows:
                continue
            panel = panel_rows[0]
            if panel.get("notify_paused"):
                continue

            notify_ch = bot.get_channel(int(panel["notify_channel_id"]))
            if not notify_ch:
                continue

            # userごとに連続枠をまとめる（start_at順）
            slots.sort(key=lambda x: x["start_at"])
            grouped = []
            cur = None

            for s in slots:
                uid = str(s["reserver_user_id"])
                st = from_utc_iso(s["start_at"])
                en = from_utc_iso(s["end_at"])
                if cur and cur["uid"] == uid and cur["end"] == st:
                    cur["end"] = en
                    cur["slot_ids"].append(int(s["id"]))
                else:
                    if cur:
                        grouped.append(cur)
                    cur = {"uid": uid, "start": st, "end": en, "slot_ids": [int(s["id"])]}
            if cur:
                grouped.append(cur)

            # 送信＆notified更新
            for g in grouped:
                start_hm = fmt_hm(g["start"])
                end_hm = fmt_hm(g["end"])
                uid = g["uid"]
                try:
                    await notify_ch.send(f"⏰ {start_hm}〜{end_hm} の枠です <@{uid}>")
                except Exception:
                    continue

                # まとめてnotified=True
                ids = g["slot_ids"]
                await self._db(lambda: sb.table("slots").update({"notified": True}).in_("id", ids).execute())