import asyncio
from datetime import datetime
from utils import db
from utils.time_utils import JST

class DataManager:
    def _require_db(self):
        # ✅ db.sb を見る（from import sb は禁止）
        if db.sb is None:
            raise RuntimeError("Supabase未接続です（SUPABASE_URL/KEY）")

    async def _db(self, fn):
        return await asyncio.to_thread(fn)

    # ====== manager role ======
    async def set_manager_role(self, guild_id: int, role_id: int | None):
        self._require_db()

        def work():
            data = {"guild_id": guild_id, "manager_role_id": role_id}
            return db.sb.table("guild_settings").upsert(data, on_conflict="guild_id").execute()

        return await self._db(work)

    async def get_manager_role(self, guild_id: int):
        self._require_db()

        def work():
            res = (
                db.sb.table("guild_settings")
                .select("manager_role_id")
                .eq("guild_id", guild_id)
                .limit(1)
                .execute()
            )
            rows = res.data or []
            return rows[0]["manager_role_id"] if rows else None

        return await self._db(work)

    def is_manager(self, interaction, manager_role_id: int | None) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        if not manager_role_id:
            return False
        return any(r.id == int(manager_role_id) for r in getattr(interaction.user, "roles", []))

    # ====== panel create (最小) ======
    async def create_panel_record(self, guild_id: int, channel_id: int, day_key: str, payload: dict):
        self._require_db()

        def work():
            row = {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "day_key": day_key,  # "today" or "tomorrow"
                "payload": payload,
                "updated_at": datetime.now(JST).isoformat(),
            }
            # ✅ on_conflict は Supabase 側のユニーク制約に合わせる
            # もし panels に (guild_id, day_key) の unique が無いならエラーになるので注意
            return db.sb.table("panels").upsert(row, on_conflict="guild_id,day_key").execute()

        return await self._db(work)

    async def reset_day(self, guild_id: int, day_key: str):
        self._require_db()

        def work():
            db.sb.table("panels").delete().eq("guild_id", guild_id).eq("day_key", day_key).execute()
            db.sb.table("slots").delete().eq("guild_id", guild_id).eq("day_key", day_key).execute()
            return True

        return await self._db(work)

    # ====== 3分前通知（今は空でOK） ======
    async def send_3min_reminders(self, bot):
        return