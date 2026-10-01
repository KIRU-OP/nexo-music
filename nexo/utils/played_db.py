"""
Played history v2 (MongoDB + motor) - same song dobara na bajे,
chahe title / artist / channel ka naam alag ho.

Isko `nexo/utils/played_db.py` naam se rakho.

Kaise pehchanta hai (same song):
  1. Videoid same ho                                   -> same
  2. Title ka gaane wala hissa match kare
     ("Tu Hai Kahan - Raffey" vs "Tu Hai Kahan | AUR")
     AUR duration lagbhag same ho (+-5 sec)             -> same
  3. Duration pata na ho to: title ka 2+ shabd wala
     hissa match kare ya poora title 85%+ milta ho     -> same

Collection: played_history
Document  : {"chat_id": int, "items": [{"v": videoid, "t": title, "d": seconds}]}
"""

import logging
import re
from difflib import SequenceMatcher
from typing import List, Optional

# Apne project ka mongo client path yahan se match karo
from nexo.core.mongo import mongodb

LOGGER = logging.getLogger(__name__)

playeddb = mongodb.played_history

MAX_HISTORY = 300
DURATION_TOLERANCE = 5  # (purana, ab use nahi)
DURATION_LOOSE = 12  # seconds: re-upload / intro ka farq

# chat_id -> list[{"v","t","d"}]
_CACHE: dict = {}

_NOISE = re.compile(
    r"\(.*?\)|\[.*?\]|\bofficial\b|\bvideo\b|\baudio\b|\blyrics?\b|\blyrical\b|"
    r"\bfull song\b|\bfull\b|\bhd\b|\b4k\b|\bhq\b|\bmusic\b|\bsong\b|\bnew\b|"
    r"\bft\.?\b|\bfeat\.?\b|\bvevo\b|\btopic\b",
    re.IGNORECASE,
)
_SPLIT = re.compile(r"\s[-–—|:]\s|\||\sby\s|\sx\s|,", re.IGNORECASE)


# ------------------------------------------------------------ helpers
def _clean(text: str) -> str:
    t = _NOISE.sub(" ", (text or "").lower())
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _strip(title: Optional[str], ignore: str = "") -> str:
    """Artist/context ka naam title se hata do (same artist ke alag gaane
    'same song' na ban jayein). ignore = 'tuntun yadav' jaisa phrase."""
    title = title or ""
    parts = [x.strip() for x in (ignore or "").split("|") if x.strip()]
    for part in parts:  # "pawan singh|pavan singh" jaise kai spelling
        title = re.sub(re.escape(part), " ", title, flags=re.IGNORECASE)
    return title


def _segments(title: Optional[str], ignore: str = "") -> List[str]:
    """'Tu Hai Kahan - Raffey, Usama' -> ['tu hai kahan', 'raffey', 'usama']"""
    if not title:
        return []
    out = []
    for part in _SPLIT.split(_strip(title, ignore)):
        c = _clean(part)
        if len(c) >= 2:
            out.append(c)
    return out


def to_seconds(d) -> int:
    """int / float / '3:45' / '1:02:10' -> seconds. Na samajh aaye to 0."""
    if d is None:
        return 0
    if isinstance(d, (int, float)):
        return int(d)
    try:
        parts = [int(p) for p in str(d).strip().split(":")]
    except ValueError:
        return 0
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return sec


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _tokens(title: Optional[str], ignore: str = "") -> set:
    return set(_clean(_strip(title or "", ignore)).split())


def _same_song(a: dict, b: dict, ignore: str = "") -> bool:
    """Same gaana hai ya nahi (naam / artist / channel alag ho tab bhi).

    ignore = artist ka naam (context se). Wo title se hata ke compare hota hai,
    taaki same artist ke alag gaane 'same' na ban jayein.
    """
    if a.get("v") and a.get("v") == b.get("v"):
        return True

    da, db = to_seconds(a.get("d")), to_seconds(b.get("d"))
    diff = abs(da - db) if (da and db) else None

    ta, tb = _tokens(a.get("t"), ignore), _tokens(b.get("t"), ignore)
    if not ta or not tb:
        return False

    shared = ta & tb
    small = min(len(ta), len(tb))
    containment = len(shared) / small  # chhota title kitna bada title mein hai

    # 1) Chhota title poora bade title ke andar (artist/extra shabd alag ho)
    #    "tu hai kahan"  vs  "aur tu hai kahan raffey usama"
    if small >= 2 and containment == 1.0:
        if diff is None or diff <= DURATION_LOOSE or len(shared) >= 3:
            return True

    # 2) Zyadatar shabd milte hon (3+ shabd) aur duration kareeb ho
    if len(shared) >= 3 and containment >= 0.6:
        if diff is None or diff <= DURATION_LOOSE:
            return True

    # 3) Title ki spelling thodi alag ho
    fa, fb = _clean(_strip(a.get("t", ""), ignore)), _clean(_strip(b.get("t", ""), ignore))
    if fa and fb and _ratio(fa, fb) >= 0.8:
        if diff is None or diff <= DURATION_LOOSE:
            return True

    return False


async def _load(chat_id: int) -> list:
    chat_id = int(chat_id)
    if chat_id in _CACHE:
        return _CACHE[chat_id]
    doc = await playeddb.find_one({"chat_id": chat_id}) or {}
    _CACHE[chat_id] = list(doc.get("items", []))
    return _CACHE[chat_id]


# ------------------------------------------------------------ public API
async def add_played(
    chat_id: int,
    videoid: Optional[str],
    title: Optional[str] = None,
    duration=None,
    ignore: str = "",
) -> None:
    """Song start hote hi call karo."""
    chat_id = int(chat_id)
    items = await _load(chat_id)

    item = {"v": str(videoid or ""), "t": title or "", "d": to_seconds(duration)}
    if any(_same_song(item, old, ignore) for old in items):
        return  # pehle se hai

    items.append(item)
    if len(items) > MAX_HISTORY:
        del items[: len(items) - MAX_HISTORY]

    await playeddb.update_one(
        {"chat_id": chat_id},
        {
            "$set": {"chat_id": chat_id},
            "$push": {"items": {"$each": [item], "$slice": -MAX_HISTORY}},
        },
        upsert=True,
    )


async def is_played(
    chat_id: int,
    videoid: Optional[str] = None,
    title: Optional[str] = None,
    duration=None,
    ignore: str = "",
) -> bool:
    items = await _load(chat_id)
    cand = {"v": str(videoid or ""), "t": title or "", "d": to_seconds(duration)}
    return any(_same_song(cand, old, ignore) for old in items)


async def filter_unplayed(
    chat_id: int,
    candidates: List[dict],
    id_key: str = "id",
    title_key: str = "title",
    duration_key: str = "duration",
    ignore: str = "",
) -> List[dict]:
    """Candidates mein se sirf wo gaane jo pehle nahi baje.
    Candidates ke andar bhi duplicate hata deta hai.

    candidates = [{"id": "abc", "title": "...", "duration": "3:45"}, ...]
    Key names apne search result ke hisaab se badlo.
    """
    fresh: List[dict] = []
    seen: List[dict] = []
    for c in candidates:
        cand = {
            "v": str(c.get(id_key) or ""),
            "t": c.get(title_key) or "",
            "d": to_seconds(c.get(duration_key)),
        }
        if await is_played(chat_id, cand["v"], cand["t"], cand["d"], ignore):
            continue
        if any(_same_song(cand, s, ignore) for s in seen):
            continue
        seen.append(cand)
        fresh.append(c)
    return fresh


async def get_played_count(chat_id: int) -> int:
    return len(await _load(chat_id))


async def clear_played(chat_id: int) -> None:
    """History saaf karo (autoplay OFF/ON ya stop par)."""
    chat_id = int(chat_id)
    _CACHE.pop(chat_id, None)
    await playeddb.delete_one({"chat_id": chat_id})
    LOGGER.info("Played history cleared | chat_id=%s", chat_id)
