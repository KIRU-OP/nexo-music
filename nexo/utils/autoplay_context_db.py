"""
Autoplay context DB (MongoDB + motor) - v2

User jo search kare, autoplay usi category mein rahe:
    "pawan singh" / "tuntun yadav" / "arijit singh"  -> sirf us artist ke gaane   (artist)
    "sad songs" / "aarti" / "lofi" / "tamil songs"   -> usi topic ke gaane        (topic)
    "tu hai kahan"                                   -> ek gaana, related autoplay (song)

Fark v1 se:
  * Sab languages ka bada artist database (autoplay_data.py)
  * Artist ka naam pehle pehchana jata hai, topic words baad mein.
    Isliye "Aarti Tabiyar" artist banta hai, aur akela "aarti" devotional topic.
  * Topic mein namesake artists hat jaate hain ("aarti" search par Aarti naam ki
    singer ke gaane nahi aate), aur artist mode mein doosre artist ka gaana kabhi nahi aata.
  * Jo artist list mein nahi, wo YouTube se pehchana jata hai aur DB mein seekh liya jata hai.

Isko `nexo/utils/autoplay_context_db.py` naam se rakho
(saath mein `nexo/utils/autoplay_data.py`).

Collections:
  autoplay_context : {"chat_id", "query", "kind", "core", "aliases", "ignore",
                      "search", "require_any", "exclude", "topics", "updated"}
  autoplay_artists : {"name", "aliases", "learned": True, "ts"}   (seekhe hue artists)
"""

import logging
import re
import time
from difflib import get_close_matches
from typing import Dict, List, Optional, Tuple

# Apne project ka mongo client path yahan se match karo
from nexo.core.mongo import mongodb
from nexo.utils.autoplay_data import (
    AMBIGUOUS_FIRST_NAMES,
    ALIASES,
    ARTISTS,
    GENERIC_WORDS,
    NAMESAKE_ARTISTS,
    PLAY_WORDS,
    TOPICS,
)

LOGGER = logging.getLogger(__name__)

contextdb = mongodb.autoplay_context
artistsdb = mongodb.autoplay_artists

_CACHE: dict = {}  # chat_id -> context

_URL = re.compile(r"https?://|www\.|youtu\.be|youtube\.com", re.IGNORECASE)

# Devanagari bhi rakho (Hindi mein search karne wale ke liye)
_CLEAN = re.compile(r"[^\w\s\u0900-\u097F]")


def _norm(text: Optional[str]) -> str:
    t = _CLEAN.sub(" ", (text or "").lower())
    return re.sub(r"\s+", " ", t).strip()


# =====================================================================
# ARTIST INDEX (built-in + seekhe hue)
# =====================================================================
# Naam ke aakhir mein ye shabd ho to wo sirf label hai ("Karthik Telugu")
_SUFFIX_NOISE = {
    "tamil", "telugu", "kannada", "bengali", "odia", "assamese", "marathi", "bhakti",
    "bhajan", "pakistan", "punjabi", "female", "english", "spanish", "japanese",
    "songs", "song", "legend", "official", "hindi", "bhojpuri", "gujarati", "malayalam",
}

_LOOKUP: Dict[str, str] = {}      # alias(norm) -> canonical(norm)
_NOSPACE: Dict[str, str] = {}     # alias bina space -> canonical
_BY_TOKENS: Dict[int, List[str]] = {}  # token count -> [alias...]  (fuzzy ke liye)
_ALIASES_OF: Dict[str, set] = {}  # canonical -> {saare alias}
_NAMESAKES: Dict[str, List[str]] = {}  # "aarti" -> ["aarti tabiyar", ...]
_LEARNED_LOADED = False


def _register(name: str, aliases: Optional[List[str]] = None) -> None:
    canon = _norm(name)
    if not canon:
        return
    toks = canon.split()
    if toks[-1] in _SUFFIX_NOISE:
        base = " ".join(toks[:-1])
        if len(base.split()) < 2:
            return  # "karthik telugu" jaisa naam: akela naam bahut generic
        canon = base

    group = _ALIASES_OF.setdefault(canon, set())
    for a in [canon] + [x for x in (aliases or [])]:
        n = _norm(a)
        if not n:
            continue
        group.add(n)
        _LOOKUP[n] = canon
        _NOSPACE[n.replace(" ", "")] = canon


def _build_index() -> None:
    for _lang, blob in ARTISTS.items():
        for raw in blob.split(","):
            _register(raw)
    for canon, als in ALIASES.items():
        _register(canon, als)
    for nm in NAMESAKE_ARTISTS:
        _register(nm)

    for a in _LOOKUP:
        _BY_TOKENS.setdefault(len(a.split()), []).append(a)

    # "aarti" jaisa shabd jin artists ke naam se shuru hota hai
    for w in AMBIGUOUS_FIRST_NAMES:
        _NAMESAKES[w] = sorted({c for c in _ALIASES_OF if c.startswith(w + " ")})


_build_index()


def artist_count() -> int:
    return len(_ALIASES_OF)


def _add_to_index(canon: str, aliases: List[str]) -> None:
    _register(canon, aliases)
    for a in _ALIASES_OF.get(_norm(canon), []):
        bucket = _BY_TOKENS.setdefault(len(a.split()), [])
        if a not in bucket:
            bucket.append(a)


async def load_learned_artists() -> int:
    """Bot start par ek baar (ya pehli query par apne aap) seekhe hue artists load karo."""
    global _LEARNED_LOADED
    _LEARNED_LOADED = True
    n = 0
    try:
        async for doc in artistsdb.find({}):
            _add_to_index(doc.get("name", ""), doc.get("aliases", []))
            n += 1
    except Exception as err:
        LOGGER.warning("load_learned_artists failed: %s", err)
    LOGGER.info("Artists: %s built-in + %s learned", artist_count() - n, n)
    return n


async def add_artist(name: str, aliases: Optional[List[str]] = None, learned: bool = False) -> None:
    """Naya artist jodo (DB mein save + turant use hone lage)."""
    canon = _norm(name)
    if not canon or canon in _ALIASES_OF:
        return
    aliases = [a for a in (aliases or []) if _norm(a)]
    await artistsdb.update_one(
        {"name": canon},
        {"$set": {"name": canon, "aliases": aliases, "learned": learned, "ts": int(time.time())}},
        upsert=True,
    )
    _add_to_index(canon, aliases)
    LOGGER.info("Artist added | %s | learned=%s", canon, learned)


async def learn_artist(core: str) -> None:
    """YouTube se verify hua artist DB mein seekh lo (agli baar seedha pehchana jayega)."""
    await add_artist(core, learned=True)


async def add_artists_bulk(names: List[str]) -> int:
    """Ek saath bahut saare naam: await add_artists_bulk(open('names.txt').read().split(','))"""
    n = 0
    for nm in names:
        if _norm(nm) and _norm(nm) not in _ALIASES_OF:
            await add_artist(nm)
            n += 1
    return n


# =====================================================================
# TOPIC INDEX
# =====================================================================
_TOPIC_PHRASES: List[Tuple[str, str]] = []  # (phrase, topic_key)
_STOP_TOKENS = set(PLAY_WORDS) | set(GENERIC_WORDS)

for _key, _t in TOPICS.items():
    for _w in _t["words"]:
        _n = _norm(_w)
        if not _n:
            continue
        _TOPIC_PHRASES.append((_n, _key))
        for _tok in _n.split():
            _STOP_TOKENS.add(_tok)
_TOPIC_PHRASES.sort(key=lambda x: -len(x[0]))  # lambe phrase pehle

_TOPIC_TOKENS = {tok for ph, _ in _TOPIC_PHRASES for tok in ph.split()}


# Sirf "command" shabd: gaane ke naam mein aa sakne wale shabd (hai, ka, hi, ...) NAHI
_COMMAND_WORDS = {
    "play", "bajao", "baja", "chalao", "chala", "laga", "lagao", "lagado", "do", "de",
    "dena", "please", "pls", "plz", "mp3", "hd", "sunao", "sunaao", "suna", "bhai", "bro",
    "yaar", "mujhe", "kro", "karo", "kar", "krdo", "official", "video", "videos", "audio",
    "lyrics", "lyrical", "status", "vevo",
}

# =====================================================================
# QUERY PARSING
# =====================================================================
def find_artists(tokens: List[str]) -> Tuple[List[str], List[bool]]:
    """Query ke tokens mein se artists dhundo (lambe naam pehle, fuzzy spelling bhi).
    Return: (canonical names, used-token mask)"""
    used = [False] * len(tokens)
    found: List[str] = []
    effective = len(tokens)

    for n in range(min(5, len(tokens)), 0, -1):
        for i in range(0, len(tokens) - n + 1):
            if any(used[i : i + n]) or len(found) >= 3:
                continue
            phrase = " ".join(tokens[i : i + n])
            canon = _LOOKUP.get(phrase) or _NOSPACE.get(phrase.replace(" ", ""))

            if not canon and n >= 2 and len(phrase) >= 7:
                cands = _BY_TOKENS.get(n, [])
                m = get_close_matches(phrase, cands, n=1, cutoff=0.9)
                if m:
                    canon = _LOOKUP.get(m[0])

            if not canon:
                continue

            if n == 1:
                tok = tokens[i]
                # Common shabd / topic word akela ho to artist mat maano
                if tok in _STOP_TOKENS and tok not in AMBIGUOUS_FIRST_NAMES:
                    if canon.split() != [tok]:
                        continue
                if tok in AMBIGUOUS_FIRST_NAMES and canon != tok:
                    continue  # "aarti" akela -> topic, artist nahi
                if len(tok) <= 2 and effective > 2:
                    continue  # "kk", "rm" jaisa chhota naam lambi query mein skip
                if len(canon.split()) == 1 and effective > 4:
                    continue  # akela single-word naam bahut lambi query mein skip

            found.append(canon)
            for j in range(i, i + n):
                used[j] = True
    return found, used


def find_topics(q: str) -> List[str]:
    padded = f" {q} "
    keys: List[str] = []
    for phrase, key in _TOPIC_PHRASES:
        if f" {phrase} " in padded and key not in keys:
            keys.append(key)
    return keys


def parse_query(query: str) -> Optional[dict]:
    """Query se context nikalo. None = URL / khali (context mat banao)."""
    query = (query or "").strip()
    if not query or _URL.search(query):
        return None

    tokens = [t for t in _norm(query).split() if t not in PLAY_WORDS]
    if not tokens:
        return None
    q = " ".join(tokens)

    # ---- 1) Artist pehle (taaki "Aarti Tabiyar" artist bane, topic nahi)
    names, used = find_artists(tokens)
    if names:
        core = names[0]
        group: set = set()
        for nm in names:
            group |= _ALIASES_OF.get(nm, {nm})
        rest = " ".join(t for t, u in zip(tokens, used) if not u)
        topic_words = [
            t for t in rest.split() if t in _TOPIC_TOKENS and t not in GENERIC_WORDS
        ]
        search = " ".join([core] + topic_words + ["songs"]).strip()
        return {
            "kind": "artist",
            "core": core,
            "aliases": sorted(group - {core}, key=len, reverse=True),
            "ignore": "|".join(sorted(group, key=len, reverse=True)),
            "search": search,
            "require_any": [],
            "exclude": [],
            "topics": find_topics(rest) if rest else [],
        }

    # ---- 2) Topic (mood / devotional / festival / language / playlist ...)
    topics = find_topics(q)
    if topics:
        require: List[str] = []
        for k in topics:
            for w in TOPICS[k].get("require_any", []):
                nw = _norm(w)
                if nw and nw not in require:
                    require.append(nw)

        # "aarti" jaise ambiguous shabd ke namesake artists ko topic se bahar rakho
        exclude: List[str] = []
        for w in tokens:
            exclude.extend(_NAMESAKES.get(w, []))

        bare = all(t in _TOPIC_TOKENS or t in _STOP_TOKENS for t in tokens)
        search = q if re.search(r"\b(songs?|gane|gaane|gana|geet)\b", q) else f"{q} songs"
        if bare and len(topics) == 1:
            suffix = TOPICS[topics[0]].get("search_suffix")
            if suffix:
                search = f"{q}{suffix}"
        return {
            "kind": "topic",
            "core": "",
            "aliases": [],
            "ignore": "",
            "search": search,
            "require_any": require,
            "exclude": sorted(set(exclude)),
            "topics": topics,
        }

    # ---- 3) Kuch pehchana nahi: unknown artist ho sakta hai ya gaane ka naam
    raw_tokens = _norm(query).split()
    core_tokens = [
        t for t in raw_tokens if t not in _COMMAND_WORDS and t not in GENERIC_WORDS
    ]
    if not core_tokens:
        return {
            "kind": "topic",
            "core": "",
            "aliases": [],
            "ignore": "",
            "search": q if "song" in q else f"{q} songs",
            "require_any": [],
            "exclude": [],
            "topics": [],
        }
    core = " ".join(core_tokens)
    return {
        "kind": "pending",
        "core": core,
        "aliases": [],
        "ignore": core,
        "search": f"{core} songs",
        "require_any": [],
        "exclude": [],
        "topics": [],
    }


# =====================================================================
# MATCHING (YouTube results par filter)
# =====================================================================
def _hay(title: Optional[str], channel: Optional[str]) -> str:
    return _norm(f"{title or ''} {channel or ''}")


def matches_core(
    core: str,
    title: Optional[str],
    channel: Optional[str] = None,
    aliases: Optional[List[str]] = None,
) -> bool:
    """Title / channel mein artist ka naam (ya koi alias) hai?"""
    if not core:
        return True
    hay = _hay(title, channel)
    if not hay:
        return False
    hay_ns = hay.replace(" ", "")
    words = set(hay.split())
    for cand in [core] + list(aliases or []):
        if not cand:
            continue
        if f" {cand} " in f" {hay} ":
            return True
        if len(cand) >= 6 and cand.replace(" ", "") in hay_ns:
            return True
        ctoks = cand.split()
        if len(ctoks) >= 2 and all(t in words for t in ctoks):
            return True
    return False


def matches_topic(ctx: dict, title: Optional[str], channel: Optional[str] = None) -> bool:
    """Topic mode: devotional jaise topic mein require_any, namesake exclude."""
    hay = _hay(title, channel)
    if not hay:
        return False
    for ex in ctx.get("exclude") or []:
        if ex and ex in hay:
            return False  # jaise "aarti tabiyar" wala result
    req = ctx.get("require_any") or []
    if req and not any(r in hay for r in req):
        return False
    return True


def looks_like_artist(core: str, results: list, durations: list) -> bool:
    """Unknown naam: artist hai ya single song ka naam?

    Artist search -> bahut saare alag gaane (alag-alag duration).
    Song search   -> same gaane ke versions (lagbhag same duration).
    """
    matched = []
    for r, d in zip(results, durations):
        ch = r["channel"].get("name") if isinstance(r.get("channel"), dict) else None
        if d and matches_core(core, r.get("title"), ch):
            matched.append(d)
    if len(matched) < 8:
        return False
    clusters: List[int] = []
    for d in sorted(matched):
        if not clusters or d - clusters[-1] > 8:
            clusters.append(d)
    return len(clusters) >= 6


# =====================================================================
# CONTEXT DB API
# =====================================================================
async def set_context(chat_id: int, query: str) -> Optional[dict]:
    """User ne naya search kiya -> context update karo (play command mein call karo)."""
    chat_id = int(chat_id)
    if not _LEARNED_LOADED:
        await load_learned_artists()

    parsed = parse_query(query)
    if not parsed:
        await clear_context(chat_id)
        return None

    doc = {"chat_id": chat_id, "query": query.strip()[:200], "updated": int(time.time())}
    doc.update(parsed)
    await contextdb.update_one({"chat_id": chat_id}, {"$set": doc}, upsert=True)
    _CACHE[chat_id] = doc
    LOGGER.info(
        "Autoplay context | chat_id=%s | kind=%s | core=%r | topics=%s",
        chat_id, doc["kind"], doc.get("core"), doc.get("topics"),
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
    """kind: 'artist' | 'topic' | 'song' (pending verify hone ke baad)."""
    chat_id = int(chat_id)
    await contextdb.update_one({"chat_id": chat_id}, {"$set": {"kind": kind}})
    if chat_id in _CACHE:
        _CACHE[chat_id]["kind"] = kind


async def clear_context(chat_id: int) -> None:
    chat_id = int(chat_id)
    _CACHE.pop(chat_id, None)
    await contextdb.delete_one({"chat_id": chat_id})
