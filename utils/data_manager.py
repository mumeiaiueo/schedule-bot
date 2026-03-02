import asyncio
from datetime import datetime
from utils import db
from utils.time_utils import JST

class DataManager:
    def _require_db(self):
        if db.sb is None:
            raise RuntimeError("Supabase未接続です（SUPABASE_URL/KEY）")

    async def _db(self, fn):
        return await asyncio.to_thread(fn)

    # ====== panel create ======
    async def create_panel_record(
        self,
        guild_id: int,
        channel_id: int,
        day,  # date
        title: str,
        start_at: datetime,
        end_at: datetime,
        interval_minutes: int,
        notify_channel_id: int,
        mention_everyone: bool,
        created_by: int,
    ):
        """
        panels の列構造に合わせて upsert する
        on_conflict は (guild_id, day) を想定
        """
        self._require_db()

        def work():
            row = {
                "guild_id": str(guild_id),
                "channel_id": str(channel_id),
                "day": day.isoformat(),  # date
                "title": title or "",
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "interval_minutes": int(interval_minutes),
                "notify_channel_id": str(notify_channel_id),
                "mention_everyone": bool(mention_everyone),
                "created_by": str(created_by),
                "updated_at": datetime.now(JST).isoformat(),  # もし列が無いなら消してOK
            }

            return db.sb.table("panels").upsert(
                row,
                on_conflict="guild_id,day"
            ).execute()

        return await self._db(work)