from datetime import datetime, timedelta, timezone
from typing import Optional
from nexo.core.mongo import mongodb

_col = mongodb["welcome"]


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    # Mongo naive datetime return karta hai (UTC), use aware bana do
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def is_on(chat_id: int) -> bool:
    """DB se state padhta hai. Restart ke baad bhi sahi value milegi.
    Agar cooldown khatam ho gaya hai to automatically ON kar deta hai."""
    doc = await _col.find_one({"_id": chat_id}, {"state": 1, "cool_until": 1})
    state = (doc or {}).get("state", "on")

    if state == "on":
        return True

    cool_until = _aware((doc or {}).get("cool_until"))
    if cool_until and datetime.now(timezone.utc) >= cool_until:
        await _col.update_one(
            {"_id": chat_id},
            {"$set": {"state": "off"}, "$unset": {"cool_until": ""}},
        )
        return True

    return False


async def set_state(chat_id: int, flag: str) -> None:
    """Manual on/off. DB mein permanent save hota hai, cooldown hata deta hai."""
    if flag not in ("on", "off"):
        raise ValueError("flag must be 'on' or 'off'")
    await _col.update_one(
        {"_id": chat_id},
        {"$set": {"state": flag}, "$unset": {"cool_until": ""}},
        upsert=True,
    )


async def bump(chat_id: int, time_window: int = 8) -> int:
    now = datetime.now(timezone.utc)
    doc = await _col.find_one({"_id": chat_id}, {"last_ts": 1, "join_cnt": 1})
    last_ts = _aware(doc.get("last_ts")) if doc else None

    if last_ts and (now - last_ts).total_seconds() <= time_window:
        cnt = int((doc.get("join_cnt") or 0)) + 1
    else:
        cnt = 1

    await _col.update_one(
        {"_id": chat_id},
        {"$set": {"last_ts": now, "join_cnt": cnt}},
        upsert=True,
    )
    return cnt


async def cool(chat_id: int, cool_minutes: int = 10) -> None:
    """Spam join par temporary OFF. cool_until DB mein save hota hai,
    isliye bot restart ho to bhi time khatam hone par ON ho jayega."""
    now = datetime.now(timezone.utc)
    await _col.update_one(
        {"_id": chat_id},
        {
            "$set": {
                "state": "off",
                "cool_until": now + timedelta(minutes=cool_minutes),
            }
        },
        upsert=True,
    )


async def auto_on(chat_id: int) -> bool:
    """Purane code se compatible. Ab is_on() bhi yehi kaam karta hai."""
    doc = await _col.find_one({"_id": chat_id}, {"state": 1, "cool_until": 1})
    if (doc or {}).get("state") == "off" and doc.get("cool_until"):
        return await is_on(chat_id)
    return False
