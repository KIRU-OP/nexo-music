"""
Autoplay context DB (MongoDB + motor) - alag database.

Idea: user jo search kare, autoplay usi category mein rahe.
    "tuntun yadav"   -> sirf Tuntun Yadav ke gaane      (kind = artist)
    "pawan singh"    -> sirf Pawan Singh ke gaane       (kind = artist)
    "shilpa raj"     -> sirf Shilpa Raj ke gaane        (kind = artist)
    "sad songs"      -> sirf sad gaane                  (kind = topic)
    "girl songs"     -> sirf ladki ke gaane             (kind = topic)
    "tu hai kahan"   -> ek gaana hai, artist nahi       (kind = song)
                        (is case mein normal related-autoplay chalta hai)

Latest search hamesha purana context badal deta hai.

Isko `nexo/utils/autoplay_context_db.py` naam se rakho.

Collection: autoplay_context
Document  : {
    "chat_id": int,
    "query":   "tuntun yadav songs",   # user ne jo likha
    "core":    "tuntun yadav",         # generic words hata ke
    "search":  "tuntun yadav songs",   # YouTube par ye search hoga
    "kind":    "pending" | "artist" | "topic" | "song",
    "updated": unix time,
}

"pending" ka matlab: abhi pata nahi artist hai ya gaane ka naam.
Pehle autoplay par YouTube.autoplay_context() ye decide karke save kar deta hai.
"""

import logging
import re
import time
from typing import Optional, Tuple

# Apne project ka mongo client path yahan se match karo
from nexo.core.mongo import mongodb

LOGGER = logging.getLogger(__name__)

contextdb = mongodb.autoplay_context

# chat_id -> context dict (cache)
_CACHE: dict = {}

# Ye shabd artist ka naam nahi hote. Inhe hatane ke baad kuch bache to
# wo "core" (artist/gaane ka naam) hai, kuch na bache to topic/mood query hai.
_STOPWORDS = {
    # generic
    "song", "songs", "gana", "gane", "gaana", "gaane", "geet", "music", "video",
    "videos", "audio", "new", "latest", "old", "hit", "hits", "top", "best",
    "superhit", "super", "hot", "playlist", "jukebox", "mashup", "all", "full",
    "ke", "ka", "ki", "ko", "se", "ye", "wala", "wale", "wali", "play", "bajao",
    "chalao", "laga", "lagao", "do", "de", "please", "pls", "mp3", "hd",
    "official", "lyrics", "lyrical", "status", "remix", "dj", "nonstop",
    # language
    "hindi", "bhojpuri", "punjabi", "english", "haryanvi", "marathi", "tamil",
    "telugu", "bengali", "gujarati", "rajasthani", "urdu", "pahadi",
    # mood / topic
    "sad", "dard", "dukhi", "dukh", "bewafa", "bewafai", "breakup", "judai",
    "heartbreak", "emotional", "cry", "love", "romantic", "romance", "pyar",
    "ishq", "mohabbat", "party", "dance", "dancing", "wedding", "shaadi",
    "bhakti", "devotional", "bhajan", "aarti", "holi", "chhath", "chhat",
    "lofi", "lo", "fi", "slowed", "reverb", "sufi", "ghazal", "qawwali",
    "rap", "rock", "pop", "classical", "retro", "romantic", "motivational",
    "sleep", "study", "workout", "gym", "travel", "rain", "barish",
    # gender / voice
    "girl", "girls", "ladki", "ladkiyon", "ladies", "female", "women",
    "woman", "boy", "boys", "ladka", "male", "voice", "singer", "singers",
}

_URL = re.compile(r"https?://|www\.|youtu\.be|youtube\.com", re.IGNORECASE)


# ------------------------------------------------------------ helpers
def _norm(text: Optional[str]) -> str:
    t = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def parse_query(query: str) -> Optional[Tuple[str, str, str]]:
    """Query se (core, kind, search_text) nikalo.

    None = URL / khali query, context mat banao.
    """
    query = (query or "").strip()
    if not query or _URL.search(query):
        return None

    q = _norm(query)
    tokens = q.split()
    core_tokens = [t for t in tokens if t not in _STOPWORDS]
    core = " ".join(core_tokens)

    if not core:
        # sirf mood/topic words: "sad songs", "girl songs", "party dj"
        search = q if re.search(r"\bsongs?\b|\bgane\b|\bgaane\b", q) else f"{q} songs"
        return "", "topic", search

    # Artist ya gaane ka naam: abhi decide nahi, pehle autoplay par verify hoga
    return core, "pending", f"{core} songs"


def matches_core(core: str, title: Optional[str], channel: Optional[str] = None) -> bool:
    """Kya title/channel mein artist ka poora naam hai?
    Spelling ke space ka farq bhi chalta hai ('tuntunyadav')."""
    if not core:
        return True
    hay = _norm(f"{title or ''} {channel or ''}")
    if not hay:
        return False
    if core in hay:
        return True
    if core.replace(" ", "") in hay.replace(" ", ""):
        return True
    return all(tok in hay.split() for tok in core.split())


def looks_like_artist(core: str, results: list, durations: list) -> bool:
    """Artist hai ya single song ka naam?

    Artist search -> bahut saare alag gaane (alag-alag duration).
    Song search   -> same gaane ke versions (lagbhag same duration).
    """
    matched = []
    for r, d in zip(results, durations):
        ch = (r.get("channel") or {}).get("name") if isinstance(r.get("channel"), dict) else None
        if d and matches_core(core, r.get("title"), ch):
            matched.append(d)

    if len(matched) < 8:
        return False

    clusters = []
    for d in sorted(matched):
        if not clusters or d - clusters[-1] > 8:
            clusters.append(d)
    return len(clusters) >= 6


# ------------------------------------------------------------ DB API
async def set_context(chat_id: int, query: str) -> Optional[dict]:
    """User ne naya search kiya -> context update karo.
    Play command mein har naye user-search par call karo.
    URL / khali query par purana context hata deta hai."""
    chat_id = int(chat_id)
    parsed = parse_query(query)
    if not parsed:
        await clear_context(chat_id)
        return None

    core, kind, search = parsed
    doc = {
        "chat_id": chat_id,
        "query": query.strip()[:200],
        "core": core,
        "search": search,
        "kind": kind,
        "updated": int(time.time()),
    }
    await contextdb.update_one({"chat_id": chat_id}, {"$set": doc}, upsert=True)
    _CACHE[chat_id] = doc
    LOGGER.info(
        "Autoplay context set | chat_id=%s | kind=%s | core=%r", chat_id, kind, core
    )
    return doc


async def get_context(chat_id: int) -> Optional[dict]:
    chat_id = int(chat_id)
    if chat_id in _CACHE:
        return _CACHE[chat_id]
    doc = await contextdb.find_one({"chat_id": chat_id}, {"_id": 0})
    if doc:
        _CACHE[chat_id] = doc
    return doc


async def set_context_kind(chat_id: int, kind: str) -> None:
    """kind: 'artist' | 'topic' | 'song' (verify hone ke baad save)."""
    chat_id = int(chat_id)
    await contextdb.update_one({"chat_id": chat_id}, {"$set": {"kind": kind}})
    if chat_id in _CACHE:
        _CACHE[chat_id]["kind"] = kind


async def clear_context(chat_id: int) -> None:
    chat_id = int(chat_id)
    _CACHE.pop(chat_id, None)
    await contextdb.delete_one({"chat_id": chat_id})
