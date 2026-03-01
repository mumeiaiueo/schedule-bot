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
                .data
                or []
            )
            return rows[0]["manager_role_id"] if rows else None

        return await self._db(work)

    async def set_manager_role_id(self, guild_id: str, role_id: int | None):
        self._require_db()

        def work():
            payload = {"guild_id": int(guild_id), "manager_role_id": (int(role_id) if role_id else None)}
            sb.table("guild_settings").upsert(payload).execute()
            return True

        await self._db(work)

        if role_id:
            return True, f"✅ 管理ロールを設定しました: <@&{int(role_id)}>"
        return True, "✅ 管理ロールを解除しました（管理者のみ操作可能に戻しました）"

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
            return {"ok": False, "error": "その時間帯に既に募集があります（/reset を先に実行）"}

        if not panel:
            return {"ok": False, "error": "作成失敗"}

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
            await self._db(lambda: sb.table("slots").insert(inserts).execute())

        return {"ok": True, "panel_id": panel_id}

    # =============================
    # /reset 用（指定日の募集削除）
    # =============================

    async def delete_panel_by_channel_day(self, guild_id: str, channel_id: str, day_date) -> bool:
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
            panel_ids = [int(p["id"]) for p in panels]
            if not panel_ids:
                return False

            # slots -> panels の順で削除
            sb.table("slots").delete().in_("panel_id", panel_ids).execute()
            sb.table("panels").delete().in_("id", panel_ids).execute()
            return True

        return await self._db(work)

    # =============================
    # 通知ON/OFF（3分前通知の停止/再開）
    # =============================

    async def toggle_notify_paused(self, panel_id: int):
        self._require_db()

        def work():
            rows = (
                sb.table("panels")
                .select("notify_paused")
                .eq("id", int(panel_id))
                .limit(1)
                .execute()
                .data
                or []
            )
            if not rows:
                return None

            cur = bool(rows[0].get("notify_paused", False))
            new_val = not cur
            sb.table("panels").update({"notify_paused": new_val}).eq("id", int(panel_id)).execute()
            return new_val

        new_val = await self._db(work)
        if new_val is None:
            return False, "パネルが見つかりません"
        return True, ("通知OFFにしました" if new_val else "通知ONにしました")

    # =============================
    # 休憩（break）
    # =============================

    async def build_break_select_view(self, panel_id: int) -> BreakSelectView:
        self._require_db()

        slots = await self._db(
            lambda: sb.table("slots")
            .select("*")
            .eq("panel_id", int(panel_id))
            .order("start_at")
            .execute()
            .data
            or []
        )

        options: list[discord.SelectOption] = []
        for r in slots[:25]:
            label = r.get("slot_time") or fmt_hm(from_utc_iso(r["start_at"]))

            if r.get("is_break"):
                emoji = "⚪"
                suffix = "休憩（解除）"
            elif r.get("reserver_user_id"):
                emoji = "🔴"
                suffix = "予約済み（休憩不可）"
            else:
                emoji = "🟢"
                suffix = "空き（休憩にする）"

            options.append(
                discord.SelectOption(
                    label=f"{label} - {suffix}",
                    value=str(int(r["id"])),
                    emoji=emoji,
                )
            )

        if not options:
            options = [discord.SelectOption(label="枠がありません", value="0")]

        return BreakSelectView(int(panel_id), options)

    async def toggle_break_slot(self, panel_id: int, slot_id: int):
        self._require_db()

        rows = await self._db(lambda: sb.table("slots").select("*").eq("id", int(slot_id)).execute().data or [])
        if not rows:
            return False, "枠が見つかりません"

        slot = rows[0]
        if int(slot.get("panel_id", 0)) != int(panel_id):
            return False, "不正な枠です（panel不一致）"

        if slot.get("reserver_user_id"):
            return False, "予約済みの枠は休憩にできません"

        new_val = not bool(slot.get("is_break", False))

        await self._db(
            lambda: sb.table("slots")
            .update({"is_break": new_val, "notified": False})
            .eq("id", int(slot_id))
            .execute()
        )

        return True, ("休憩にしました" if new_val else "休憩を解除しました")

    # =============================
    # パネル描画
    # =============================

    async def render_panel(self, bot: discord.Client, panel_id: int):
        self._require_db()

        panel_rows = await self._db(lambda: sb.table("panels").select("*").eq("id", int(panel_id)).execute().data or [])
        if not panel_rows:
            return
        panel = panel_rows[0]

        channel = bot.get_channel(int(panel["channel_id"]))
        if not channel:
            return

        slots = await self._db(
            lambda: sb.table("slots")
            .select("*")
            .eq("panel_id", int(panel_id))
            .order("start_at")
            .execute()
            .data
            or []
        )

        lines = []
        buttons = []

        for r in slots[:20]:
            sdt = from_utc_iso(r["start_at"])
            label = fmt_hm(sdt)

            if r.get("is_break"):
                dot = "⚪"
                style = discord.ButtonStyle.secondary
                disabled = True
            elif r.get("reserver_user_id"):
                dot = "🔴"
                style = discord.ButtonStyle.danger
                disabled = False
            else:
                dot = "🟢"
                style = discord.ButtonStyle.success
                disabled = False

            mention = f" <@{r['reserver_user_id']}>" if r.get("reserver_user_id") else ""
            lines.append(f"{dot} {label}{mention}")

            buttons.append(
                {
                    "slot_id": int(r["id"]),
                    "label": label,
                    "style": style,
                    "disabled": disabled,
                }
            )

        embed = build_panel_embed(
            panel.get("title"),
            f"📅 {panel['day']}（JST） / interval {panel['interval_minutes']}min",
            lines,
        )

        view = PanelView(int(panel_id), buttons, notify_paused=bool(panel.get("notify_paused", False)))

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
            lambda: sb.table("panels")
            .update({"panel_message_id": str(msg.id)})
            .eq("id", int(panel_id))
            .execute()
        )

    # =============================
    # 予約（押すと予約/本人はキャンセル）
    # =============================

    async def toggle_reserve(self, slot_id: int, user_id: str, user_name: str):
        self._require_db()

        rows = await self._db(lambda: sb.table("slots").select("*").eq("id", int(slot_id)).execute().data or [])
        if not rows:
            return False, "枠が見つかりません"

        slot = rows[0]

        if slot.get("is_break"):
            return False, "休憩枠です"

        if not slot.get("reserver_user_id"):
            updated = await self._db(
                lambda: sb.table("slots")
                .update(
                    {
                        "reserver_user_id": str(user_id),
                        "reserver_name": str(user_name),
                        "reserved_at": to_utc_iso(jst_now()),
                        "notified": False,
                    }
                )
                .eq("id", int(slot_id))
                .is_("reserver_user_id", None)
                .execute()
                .data
            )
            if not updated:
                return False, "すでに埋まっています"
            return True, "予約しました（もう一度押すとキャンセル）"

        if str(slot.get("reserver_user_id")) == str(user_id):
            await self._db(
                lambda: sb.table("slots")
                .update(
                    {
                        "reserver_user_id": None,
                        "reserver_name": None,
                        "reserved_at": None,
                        "notified": False,
                    }
                )
                .eq("id", int(slot_id))
                .execute()
            )
            return True, "キャンセルしました"

        return False, "他の人が予約済み"

    # =============================
    # 3分前通知（連続枠はまとめて1回）
    # =============================

    async def send_3min_reminders(self, bot: discord.Client):
        self._require_db()

        rows = await self._db(
            lambda: sb.table("slots")
            .select("*")
            .eq("notified", False)
            .eq("is_break", False)
            .not_.is_("reserver_user_id", "null")
            .order("start_at")
            .execute()
            .data
            or []
        )

        now = jst_now()

        # 3分前ウィンドウ
        candidates = []
        for slot in rows:
            start = from_utc_iso(slot["start_at"])
            diff = (start - now).total_seconds()
            if 160 <= diff <= 220:
                candidates.append(slot)

        if not candidates:
            return

        panel_cache: dict[int, dict | None] = {}

        async def get_panel(pid: int):
            if pid in panel_cache:
                return panel_cache[pid]
            p = await self._db(
                lambda: sb.table("panels").select("*").eq("id", int(pid)).limit(1).execute().data or []
            )
            panel_cache[pid] = (p[0] if p else None)
            return panel_cache[pid]

        # (panel_id, user_id) でまとめる
        groups: dict[tuple[int, str], list[dict]] = {}
        for s in candidates:
            key = (int(s["panel_id"]), str(s["reserver_user_id"]))
            groups.setdefault(key, []).append(s)

        for (panel_id, user_id), slots in groups.items():
            panel = await get_panel(panel_id)
            if not panel:
                continue
            if panel.get("notify_paused"):
                continue

            notify_ch = bot.get_channel(int(panel["notify_channel_id"]))
            if not notify_ch:
                continue

            # start_at順にして連続をマージ
            slots_sorted = sorted(slots, key=lambda x: x["start_at"])

            merged = []
            for s in slots_sorted:
                s_start = from_utc_iso(s["start_at"])
                s_end = from_utc_iso(s["end_at"])
                if not merged:
                    merged.append([s_start, s_end, [s]])
                    continue

                prev_start, prev_end, bucket = merged[-1]
                if abs((s_start - prev_end).total_seconds()) <= 60:
                    merged[-1][1] = s_end
                    bucket.append(s)
                else:
                    merged.append([s_start, s_end, [s]])

            for start_dt, end_dt, bucket in merged:
                try:
                    await notify_ch.send(f"⏰ 3分前：{fmt_hm(start_dt)}～{fmt_hm(end_dt)} の枠です <@{user_id}>")
                except Exception:
                    continue

                ids = [int(x["id"]) for x in bucket]
                await self._db(lambda: sb.table("slots").update({"notified": True}).in_("id", ids).execute())