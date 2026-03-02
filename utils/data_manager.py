import asyncio
from utils import db
from utils.time_utils import day_from_key, build_dt

class DataManager:
    def _require_db(self):
        if db.sb is None:
            raise RuntimeError("Supabase未接続です（SUPABASE_URL/KEY）")

    async def _db(self, fn):
        return await asyncio.to_thread(fn)

    async def create_panel_record(
        self,
        guild_id: int,
        channel_id: int,
        day_key: str,
        payload: dict
    ):
        """
        panels テーブルに保存（あなたのテーブル構造に合わせる）
        payload:
          start_hh, start_mm, end_hh, end_mm
          interval_minutes, title, mention_everyone, notify_channel_id
        """
        self._require_db()

        def work():
            day = day_from_key(day_key)

            start_at = build_dt(day, payload["start_hh"], payload["start_mm"]).isoformat()
            end_at   = build_dt(day, payload["end_hh"], payload["end_mm"]).isoformat()

            row = {
                "guild_id": str(guild_id),
                "channel_id": str(channel_id),
                "day": str(day),  # date -> "YYYY-MM-DD"
                "title": payload.get("title", "") or "",
                "start_at": start_at,
                "end_at": end_at,
                "interval_minutes": int(payload["interval_minutes"]),
                "notify_channel_id": str(payload.get("notify_channel_id", channel_id)),
                "mention_everyone": bool(payload.get("mention_everyone", False)),
            }

            # ✅ day_key じゃなく day(date) を使って upsert する
            # 既に unique(guild_id, day) がある前提
            return db.sb.table("panels").upsert(row, on_conflict="guild_id,day").execute()

        return await self._db(work)