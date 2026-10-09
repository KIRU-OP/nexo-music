import asyncio
import difflib
import logging
import random
import re
import time
from typing import Dict, List, Optional

try:
    from unidecode import unidecode as _unidecode
except ImportError:  # pip install unidecode (Devanagari -> Roman ke liye)
    _unidecode = None

# Apne project ka mongo client path yahan se match karo
from nexo.core.mongo import mongodb

LOGGER = logging.getLogger(__name__)

contextdb = mongodb.autoplay_context
playeddb = mongodb.autoplay_played

_CACHE: Dict[int, dict] = {}      # chat_id -> context
_RECENT: Dict[int, List[dict]] = {}   # chat_id -> played items
_LOCKS: Dict[int, asyncio.Lock] = {}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DATABASE (nexo wale dicts)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEVOTIONAL_WORDS = [
    "bhajan", "aarti", "mantra", "chalisa", "bhakti", "devotional",
    "kirtan", "stotra", "stuti", "vandana", "pooja", "puja",
    "jai shri", "jai ram", "jai hanuman", "jai ganesh", "jai durga",
    "namo namo", "om shanti", "shiv tandav", "shri ram", "jai mata",
    "navratri", "ganpati", "sai baba", "balaji", "tirupati",
    "ramayana", "mahabharata", "bajrang baan", "sunderkand",
]

LANG_TITLE_INDICATORS = {
    "bhojpuri": ["bhojpuri", "pawan singh", "khesari", "pramod premi"],
    "haryanvi": ["haryanvi", "mewati", "khasa aala chahar", "masoom sharma"],
    "gujarati": ["gujarati", "garba", "gujju"],
    "tamil":    ["tamil", "kollywood"],
    "telugu":   ["telugu", "tollywood"],
    "bengali":  ["bengali", "bangla"],
    "marathi":  ["marathi"],
    "punjabi":  ["punjabi", "jatt", "pind", "sidhu", "diljit", "karan aujla", "ammy virk"],
    "english":  ["english song", "english version"],
}

INCOMPATIBLE_LANGS = {
    "hindi":    ["bhojpuri", "haryanvi", "gujarati", "tamil", "telugu", "bengali", "marathi"],
    "punjabi":  ["bhojpuri", "haryanvi", "tamil", "telugu", "bengali"],
    "bhojpuri": ["punjabi", "haryanvi", "tamil", "telugu", "bengali", "gujarati"],
    "haryanvi": ["bhojpuri", "punjabi", "tamil", "telugu", "bengali", "gujarati"],
    "tamil":    ["hindi", "punjabi", "bhojpuri", "haryanvi", "telugu", "bengali"],
    "telugu":   ["hindi", "punjabi", "bhojpuri", "haryanvi", "tamil", "bengali"],
}

SIMILAR_ARTISTS = {
    "arijit singh":      ["jubin nautiyal", "atif aslam", "armaan malik", "shreya ghoshal", "darshan raval"],
    "jubin nautiyal":    ["arijit singh", "armaan malik", "darshan raval", "pawandeep rajan"],
    "atif aslam":        ["arijit singh", "jubin nautiyal", "falak shabir", "rahat fateh ali"],
    "shreya ghoshal":    ["arijit singh", "neha kakkar", "lata mangeshkar", "alka yagnik"],
    "sidhu moosewala":   ["karan aujla", "shubh", "ap dhillon", "diljit dosanjh", "ammy virk"],
    "diljit dosanjh":    ["sidhu moosewala", "karan aujla", "ammy virk", "gurnazar"],
    "karan aujla":       ["sidhu moosewala", "ap dhillon", "shubh", "diljit dosanjh"],
    "ap dhillon":        ["karan aujla", "shubh", "gurinder gill", "diljit dosanjh"],
    "badshah":           ["yo yo honey singh", "neha kakkar", "guru randhawa"],
    "yo yo honey singh": ["badshah", "guru randhawa", "neha kakkar"],
    "neha kakkar":       ["shreya ghoshal", "badshah", "tony kakkar", "tulsi kumar"],
    "armaan malik":      ["arijit singh", "jubin nautiyal", "darshan raval"],
    "guru randhawa":     ["badshah", "yo yo honey singh", "neha kakkar"],
    "pawan singh":       ["khesari lal yadav", "pramod premi", "dinesh lal yadav"],
    "khesari lal yadav": ["pawan singh", "pramod premi", "dinesh lal yadav"],
}

LANG_DB = {
    "hindi":    ["hindi", "bollywood", "hindi song", "bollywood song", "filmi gaana"],
    "punjabi":  ["punjabi", "jatt", "pind", "punjabi song", "punjabi music"],
    "english":  ["english", "english song", "english version"],
    "bhojpuri": ["bhojpuri", "bhojpuri song", "bhojpuri music"],
    "haryanvi": ["haryanvi", "haryanvi song", "mewati"],
    "gujarati": ["gujarati", "garba", "gujarati song", "gujju"],
    "tamil":    ["tamil", "kollywood", "tamil song", "tamil cinema"],
    "telugu":   ["telugu", "tollywood", "telugu song", "telugu cinema"],
    "bengali":  ["bengali", "bangla", "bengali song"],
    "marathi":  ["marathi", "marathi song"],
    "urdu":     ["urdu", "urdu song", "ghazal"],
}

# Gaane ke title mein language ka naam kam hota hai -- artist se language pehchano
ARTIST_LANG = {
    "hindi": [
        "arijit singh", "jubin nautiyal", "atif aslam", "shreya ghoshal",
        "sonu nigam", "alka yagnik", "udit narayan", "kumar sanu",
        "lata mangeshkar", "kishore kumar", "mohammad rafi",
        "neha kakkar", "armaan malik", "darshan raval", "pawandeep rajan",
        "rahat fateh ali", "sunidhi chauhan", "shaan", "mohit chauhan",
        "vishal shekhar", "amit trivedi", "pritam", "shankar ehsaan loy",
    ],
    "punjabi": [
        "sidhu moosewala", "diljit dosanjh", "karan aujla", "ap dhillon",
        "ammy virk", "gurinder gill", "shubh", "guru randhawa",
        "badshah", "yo yo honey singh", "jasmine sandlas", "gurnazar",
        "b praak", "jaani", "hardy sandhu", "mankirt aulakh", "sukh e",
    ],
    "bhojpuri": [
        "pawan singh", "khesari lal yadav", "pramod premi", "dinesh lal yadav",
        "manoj tiwari", "ritesh pandey",
    ],
    "haryanvi": [
        "khasa aala chahar", "masoom sharma", "renuka panwar", "raj mawar",
        "sumit goswami", "raju punjabi",
    ],
    "tamil": ["anirudh ravichander", "sid sriram", "dhanush", "g v prakash"],
    "telugu": ["devi sri prasad", "ss thaman", "chinmayi"],
    "english": [
        "ed sheeran", "taylor swift", "justin bieber", "the weeknd",
        "drake", "eminem", "billie eilish", "ariana grande",
    ],
}

MOOD_DB = {
    "sad":        ["sad", "broken", "heart", "bewafa", "alone", "cry", "dard", "tanha", "rula", "sad song"],
    "love":       ["love", "romantic", "ishq", "pyaar", "mohabbat", "love song", "romantic song", "pyar", "ishq wala"],
    "party":      ["party", "dj", "dance", "club", "bhangra", "party song", "dj song", "dance song", "masala"],
    "wedding":    ["wedding", "shaadi", "marriage", "dulhan", "mehendi", "sangeet"],
    "devotional": ["devotional", "bhajan", "aarti", "mantra", "shiva", "krishna", "ram", "ganesha", "hanuman"],
    "oldschool":  ["old", "classic", "90s", "80s", "kishore", "lata", "rafi", "old song", "retro", "purana"],
    "punjabi":    ["punjabi", "sidhu", "diljit", "bhangra", "jatt", "punjabi song"],
    "sufi":       ["sufi", "qawwali", "nusrat", "kalam", "sufiana"],
}

ARTIST_DB = {
    "arijit singh":      ["arijit", "arijit singh", "arijit song", "arijit new"],
    "atif aslam":        ["atif", "atif aslam", "atif song"],
    "sidhu moosewala":   ["sidhu", "sidhu moosewala", "sidhu song"],
    "diljit dosanjh":    ["diljit", "diljit dosanjh", "diljit song"],
    "karan aujla":       ["karan aujla", "karan song"],
    "jubin nautiyal":    ["jubin", "jubin nautiyal", "jubin song"],
    "badshah":           ["badshah", "badshah song", "badshah new"],
    "yo yo honey singh": ["honey singh", "yo yo", "yo yo honey singh"],
    "neha kakkar":       ["neha kakkar", "neha song", "neha new"],
    "shreya ghoshal":    ["shreya", "shreya ghoshal", "shreya song"],
    "sonu nigam":        ["sonu", "sonu nigam", "sonu song"],
    "alka yagnik":       ["alka", "alka yagnik", "alka song"],
    "udit narayan":      ["udit", "udit narayan", "udit song"],
    "kumar sanu":        ["kumar sanu", "kumar song"],
    "lata mangeshkar":   ["lata", "lata mangeshkar", "lata song"],
    "kishore kumar":     ["kishore", "kishore kumar", "kishore song"],
    "mohammad rafi":     ["rafi", "mohammad rafi", "rafi song"],
    "ap dhillon":        ["ap dhillon", "dhillon", "ap song"],
    "gurinder gill":     ["gurinder gill", "gurinder song"],
    "pawan singh":       ["pawan singh", "pawan song"],
    "khesari lal yadav": ["khesari", "khesari lal yadav", "khesari song"],
}

MOVIE_DB = {
    "animal":                  ["animal", "animal song", "animal movie"],
    "kabir singh":             ["kabir singh", "kabir movie"],
    "aashiqui 2":              ["aashiqui", "aashiqui 2", "aashiqui song"],
    "shershaah":               ["shershaah", "shershaah song", "shershaah movie"],
    "pushpa":                  ["pushpa", "pushpa song", "pushpa movie", "srivali"],
    "kgf":                     ["kgf", "kgf song", "rocky bhai"],
    "pathaan":                 ["pathaan", "pathaan song"],
    "jawan":                   ["jawan", "jawan song", "jawan movie"],
    "dunki":                   ["dunki", "dunki song", "dunki movie"],
    "gadar 2":                 ["gadar", "gadar 2", "gadar song"],
    "rocky aur rani":          ["rocky aur rani"],
    "tu jhoothi main makkaar": ["tu jhoothi", "tjmm"],
    "bhool bhulaiyaa 2":       ["bhool bhulaiyaa", "bb2"],
    "brahmastra":              ["brahmastra"],
    "tanhaji":                 ["tanhaji", "tanhaji song"],
    "chhichhore":              ["chhichhore", "chhichhore song"],
}

BAD_WORDS = [
    "slowed", "reverb", "8d", "lofi", "live", "mix", "dj remix",
    "bass boosted", "cover", "karaoke", "instrumental", "sped up",
    # same gaane ke doosre "avatar" (alag awaaz / alag version)
    "version", "reprise", "unplugged", "acoustic", "mashup", "remake",
    "recreated", "tribute", "female", "rework", "refix", "remix",
]
SPAM_TITLE = ["lyrical", "lyrics video", "lyric video", "cover by", "remix by", "dj remix"]
SPAM_CHANNEL = ["lyrics", "lofi", "slowed", "reverb", "cover", "karaoke", "remix", "8d"]

_EPISODE_RE = re.compile(r"(?:ep(?:isode)?\s*\d+|s\d+e\d+|season\s+\d+)", re.IGNORECASE)

MIN_SEC, MAX_SEC = 2 * 60, 10 * 60      # 2 se 10 minute
MAX_RECENT = 60                          # last itne gaane yaad
KEEP_ALWAYS = 30                         # itne kabhi expire nahi
EXPIRE_SEC = 6 * 3600                    # baaki 6 ghante baad expire


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEXT HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _ascii(text: Optional[str]) -> str:
    t = text or ""
    return _unidecode(t) if _unidecode else t


def _norm(text: Optional[str]) -> str:
    """lower + Roman + sirf shabd (word-boundary matching ke liye)."""
    t = re.sub(r"[^\w\s]", " ", _ascii(text).lower())
    return re.sub(r"\s+", " ", t).strip()


def _has_any(keys: List[str], text: Optional[str]) -> bool:
    """Poore shabd ke roop mein match ("ram" ab "program" mein match nahi hoga)."""
    padded = f" {_norm(text)} "
    return any(f" {k} " in padded for k in keys)


def _vid(r: dict) -> str:
    return str(r.get("id") or r.get("vidid") or r.get("videoId") or "")


def _channel_name(r: dict) -> str:
    ch = r.get("channel")
    if isinstance(ch, dict):
        ch = ch.get("name")
    return (ch or "").lower() if isinstance(ch, str) else ""


def parse_duration(d) -> int:
    """Seconds / 'mm:ss' / 'h:mm:ss' -> seconds.  Pata na chale to 0 (unknown)."""
    if d is None or d == "":
        return 0
    if isinstance(d, (int, float)):
        return int(d) if d > 0 else 0
    try:
        sec = 0
        for p in str(d).strip().split(":"):
            sec = sec * 60 + int(p)
        return sec
    except ValueError:
        return 0


def _result_duration(r: dict) -> int:
    return parse_duration(r.get("duration_sec") or r.get("duration") or r.get("duration_min"))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DETECT  (language / mood / artist / movie)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_lang(title: str) -> str:
    """1) title mein language ka naam  2) artist ka naam  3) default hindi"""
    if not title:
        return "hindi"
    for lang, keys in LANG_DB.items():
        if _has_any(keys, title):
            return lang
    for lang, artists in ARTIST_LANG.items():
        if _has_any(artists, title):
            return lang
    return "hindi"


def detect_mood(title: str) -> str:
    if not title:
        return "normal"
    for mood, keys in MOOD_DB.items():
        if _has_any(keys, title):
            return mood
    return "normal"


_NOISE_IN_ARTIST = re.compile(
    r"\b(official|video|music|audio|lyrics|lyrical|full|hd|hq|4k|song|new|latest|ft|feat|vs)\b",
    re.IGNORECASE,
)


def extract_artist(title: str) -> str:
    """1) ARTIST_DB  2) separator ke baad ka naam  3) ARTIST_LANG scan"""
    if not title:
        return ""
    for artist, keys in ARTIST_DB.items():
        if _has_any(keys, title):
            return artist

    for sep in (" - ", " | ", " — "):
        if sep in title:
            for part in title.split(sep)[1:]:
                part = _NOISE_IN_ARTIST.sub("", part).strip(" .,|")
                if 2 < len(part) < 45:
                    pl = part.lower()
                    if any(w in pl for w in ("records", "films", "movies", "productions", "entertainment")):
                        continue
                    for lst in ARTIST_LANG.values():
                        for known in lst:
                            if known in pl:
                                return known
                    return pl
            break

    for lst in ARTIST_LANG.values():
        for known in lst:
            if _has_any([known], title):
                return known
    return ""


def detect_movie(title: str) -> str:
    if not title:
        return ""
    for movie, keys in MOVIE_DB.items():
        if _has_any(keys, title):
            return movie
    return ""


def _detect_title_lang(title_lower: str) -> str:
    for lang, kws in LANG_TITLE_INDICATORS.items():
        if _has_any(kws, title_lower):
            return lang
    return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TITLE NORMALIZER + SAME SONG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

_NOISE_WORDS = [
    "official", "video", "music", "audio", "lyrics", "lyrical", "lyric", "full",
    "hd", "hq", "4k", "song", "new", "latest", "visualizer", "teaser", "promo",
]
# Same gaane ke doosre version -- title se hata do taaki "Blue Eyes (Female Version)" == "Blue Eyes"
_VERSION_NOISE = [
    "version", "reprise", "unplugged", "acoustic", "remake", "recreated",
    "tribute", "female", "male", "remix", "cover", "mashup", "rework", "refix",
    "original",
]
_LABEL_TOKENS = {"records", "music", "films", "movies", "productions", "entertainment",
                 "company", "studios", "series", "label", "vevo", "topic"}

_SPLIT_RE = re.compile(r"\s[-|\u2013\u2014]\s|\s(?:ft|feat|featuring)\.?\s", re.IGNORECASE)
_ARTIST_SET_CACHE = (0, frozenset())


def _artist_names() -> frozenset:
    global _ARTIST_SET_CACHE
    n = len(ARTIST_DB)
    if _ARTIST_SET_CACHE[0] != n:
        names = set(ARTIST_DB) | set(SIMILAR_ARTISTS)
        for lst in ARTIST_LANG.values():
            names.update(lst)
        _ARTIST_SET_CACHE = (n, frozenset(_norm(x) for x in names))
    return _ARTIST_SET_CACHE[1]


def _clean_segment(seg: str) -> str:
    t = re.sub(r"[^\w\s]", " ", seg)
    for w in _NOISE_WORDS + _VERSION_NOISE:
        t = re.sub(rf"\b{w}\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def title_keys(title: str) -> List[str]:
    """Title ke saare 'gaane ke naam' wale hisse.

    "Yo Yo Honey Singh - Blue Eyes (Official Video)" -> ["blue eyes"]
    "Blue Eyes (Female Version) | Singer X"        -> ["blue eyes", "singer x"]
    Known artist / label wale hisse hata diye jaate hain, taaki "Artist - Song" aur
    "Song - Artist" dono layout mein asli gaane ka naam compare ho.
    """
    if not title:
        return []
    t = _ascii(title).lower()
    t = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", t)
    names = _artist_names()
    keys: List[str] = []
    for seg in _SPLIT_RE.split(t):
        k = _clean_segment(seg)
        if len(k) < 4 or k in names or (set(k.split()) & _LABEL_TOKENS):
            continue
        if k not in keys:
            keys.append(k)
    return keys


def normalize_title(title: str) -> str:
    """Purana API: gaane ka ek saaf naam (pehla key)."""
    keys = title_keys(title)
    return keys[0] if keys else ""


def _same_song(stored: str, candidate: str) -> bool:
    """Exact / prefix (tokens ke hisaab se) / spelling-similar / pehla lamba shabd same."""
    if not stored or not candidate or len(stored) < 4 or len(candidate) < 4:
        return False
    if stored == candidate:
        return True
    ta, tb = stored.split(), candidate.split()
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    sj = " ".join(short)
    if len(sj) >= 8 and long_[:len(short)] == short:
        return True
    if len(sj) >= 5 and difflib.SequenceMatcher(None, stored, candidate).ratio() >= 0.88:
        return True
    return short[0] == long_[0] and len(short[0]) >= 7


def _keys_match(a: List[str], b: List[str]) -> bool:
    return any(_same_song(x, y) for x in a for y in b)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PLAYED HISTORY  (Mongo mein save)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _prune(items: List[dict]) -> List[dict]:
    now = time.time()
    if len(items) > KEEP_ALWAYS:
        items = [
            i for i in items[:-KEEP_ALWAYS] if now - i.get("ts", 0) < EXPIRE_SEC
        ] + items[-KEEP_ALWAYS:]          # order: purana -> naya (items[-1] hamesha latest)
    return items[-MAX_RECENT:]


async def _load_recent(chat_id: int) -> List[dict]:
    if chat_id in _RECENT:
        return _RECENT[chat_id]
    items: List[dict] = []
    try:
        doc = await playeddb.find_one({"chat_id": chat_id}, {"_id": 0})
        items = (doc or {}).get("items", [])
    except Exception as err:
        LOGGER.warning("load played failed: %s", err)
    _RECENT[chat_id] = items
    return items


def _item_keys(i: dict) -> List[str]:
    return i.get("keys") or ([i["title"]] if i.get("title") else [])


def _repeat_in(items: List[dict], vidid: str, keys: List[str]) -> bool:
    for i in items:
        if vidid and i.get("id") == vidid:
            return True
        if keys and _keys_match(_item_keys(i), keys):
            return True
    return False


async def is_repeat(chat_id: int, vidid: str, title: str = "") -> bool:
    items = await _load_recent(int(chat_id))
    return _repeat_in(items, vidid, title_keys(title))


async def has_played(chat_id, vid, title=None, channel=None, duration=None) -> bool:
    """Purana naam / purani signature (channel, duration ignore hote hain)."""
    return await is_repeat(chat_id, str(vid or ""), title or "")


async def add_recent(chat_id: int, vidid: str, title: str = "", artist: str = "") -> None:
    if not vidid:
        return
    chat_id = int(chat_id)
    items = await _load_recent(chat_id)
    if items and items[-1].get("id") == vidid:      # reserve ho chuka -- dobara mat jodo
        return
    items.append({
        "id": vidid,
        "title": normalize_title(title),
        "keys": title_keys(title),
        "artist": (artist or "").lower(),
        "ts": time.time(),
    })
    _RECENT[chat_id] = items = _prune(items)
    try:
        await playeddb.update_one({"chat_id": chat_id}, {"$set": {"items": items}}, upsert=True)
    except Exception as err:
        LOGGER.warning("save played failed: %s", err)


async def clear_played(chat_id: int) -> None:
    chat_id = int(chat_id)
    _RECENT.pop(chat_id, None)
    await playeddb.delete_one({"chat_id": chat_id})


async def recent_artists(chat_id: int, n: int = 10) -> List[str]:
    items = await _load_recent(int(chat_id))
    return [i["artist"] for i in items[-n:] if i.get("artist")]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONTEXT DB
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _artist_from_channel(channel) -> str:
    if isinstance(channel, dict):
        channel = channel.get("name")
    ch = _norm(channel if isinstance(channel, str) else "")
    if not ch:
        return ""
    if ch.endswith(" topic"):                       # "Yo Yo Honey Singh - Topic"
        return ch[:-6].strip()
    for name in _artist_names():
        if name and _has_any([name], ch):
            return name
    return ""


def _resolve_artist(title: str, channel=None) -> str:
    """extract_artist ka ankaa kabhi gaane ka NAAM hota hai ("Singer - Blue Eyes" mein
    separator ke baad wala hissa).  Anjaan naam tabhi maano jab channel se confirm ho,
    warna autoplay usi gaane ko dobara search karta hai."""
    artist = extract_artist(title)
    if artist and artist not in _artist_names():
        ch = _norm(channel if isinstance(channel, str) else "")
        ch = ch[:-6].strip() if ch.endswith(" topic") else ch
        if not (ch and (artist in ch or ch in artist)):
            artist = ""
    return artist or _artist_from_channel(channel)


def _context_from_title(title: str, channel=None) -> dict:
    return {
        "title": title,
        "lang": detect_lang(title),
        "mood": detect_mood(title),
        "artist": _resolve_artist(title, channel),
        "movie": detect_movie(title),
    }


async def _save_context(chat_id: int, doc: dict) -> dict:
    doc["chat_id"] = chat_id
    doc["updated"] = int(time.time())
    await contextdb.update_one({"chat_id": chat_id}, {"$set": doc}, upsert=True)
    _CACHE[chat_id] = {**_CACHE.get(chat_id, {}), **doc}
    return _CACHE[chat_id]


async def set_context(chat_id: int, query: str) -> Optional[dict]:
    """User ne naya search kiya -> query se lang / mood / artist / movie nikalo."""
    chat_id = int(chat_id)
    query = (query or "").strip()
    if not query or re.search(r"https?://|www\.|youtu\.be|youtube\.com", query, re.I):
        await clear_context(chat_id)
        return None
    doc = {"query": query[:200], "seed_vid": ""}
    doc.update(_context_from_title(query))
    ctx = await _save_context(chat_id, doc)
    LOGGER.info("Autoplay context | chat_id=%s | %s", chat_id,
                {k: ctx.get(k) for k in ("lang", "mood", "artist", "movie")})
    return ctx


async def get_context(chat_id: int) -> Optional[dict]:
    chat_id = int(chat_id)
    if chat_id in _CACHE:
        return _CACHE[chat_id]
    doc = await contextdb.find_one({"chat_id": chat_id}, {"_id": 0})
    if doc:
        _CACHE[chat_id] = doc
    return doc


async def clear_context(chat_id: int) -> None:
    chat_id = int(chat_id)
    _CACHE.pop(chat_id, None)
    await contextdb.delete_one({"chat_id": chat_id})


async def set_language(chat_id: int, lang: Optional[str]) -> None:
    """Haath se language lock, jaise /lang bhojpuri.  None = hatao (title se detect)."""
    lg = (lang or "").strip().lower() or None
    if lg and lg not in LANG_DB:
        return
    await _save_context(int(chat_id), {"lang": lg or "hindi"})


async def note_played(
    chat_id: int, vid: Optional[str], title: Optional[str],
    channel: Optional[str] = None, autoplayed: bool = False, **_ignored,
) -> None:
    """Jab bhi gaana baje call karo.  Autoplay wala gaana sirf history mein jodta hai;
    user ka lagaya gaana naya 'seed' ban jata hai (lang / mood / artist / movie badal jaate hain)."""
    chat_id = int(chat_id)
    title = title or ""
    await add_recent(chat_id, str(vid or ""), title, _resolve_artist(title, channel))
    if autoplayed:
        return
    doc = _context_from_title(title, channel)
    doc["seed_vid"] = str(vid or "")
    await _save_context(chat_id, doc)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SMART QUERY BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

_MOOD_QUERIES = {
    "sad":        lambda lp: [f"sad {lp} songs", f"heartbreak {lp} songs", "bewafa songs"],
    "love":       lambda lp: [f"romantic {lp} songs", f"love {lp} songs", "ishq wala love song"],
    "party":      lambda lp: [f"party {lp} songs", f"dance {lp} songs"],
    "wedding":    lambda lp: [f"wedding {lp} songs", "shaadi sangeet songs"],
    "devotional": lambda lp: ["bhajan hindi", "aarti songs", "bhakti songs"],
    "oldschool":  lambda lp: [f"90s {lp} songs", f"old {lp} songs", "retro bollywood"],
    "sufi":       lambda lp: ["sufi hindi songs", "qawwali hindi"],
}

_LANG_FALLBACK = {
    "hindi":    ["latest bollywood official songs", "top hindi original songs"],
    "punjabi":  ["punjabi official songs", "latest punjabi hits"],
    "bhojpuri": ["bhojpuri official songs", "bhojpuri superhit songs"],
    "haryanvi": ["haryanvi official songs", "haryanvi superhit songs"],
    "gujarati": ["gujarati official songs", "garba songs new"],
    "tamil":    ["tamil official songs", "kollywood hits"],
    "telugu":   ["telugu official songs", "tollywood hits"],
    "bengali":  ["bangla official songs", "bengali new songs"],
    "marathi":  ["marathi official songs", "marathi new songs"],
    "urdu":     ["urdu official songs", "urdu romantic songs"],
}


def build_smart_queries(title, artist, movie, lang, mood, recent_artists_list=None) -> List[str]:
    queries: List[str] = []
    recent_artists_list = recent_artists_list or []

    # NOTE: yahan gaane ke apne title se query NAHI banti -- "<title> official song" search
    # karne par wahi gaana / uske cover (doosri awaaz) wapas aate the.

    if artist:
        if recent_artists_list.count(artist.lower()) >= 3:     # same artist bahut ho gaya
            for sim in SIMILAR_ARTISTS.get(artist.lower(), []):
                queries.append(f"{sim} {lang} official songs" if lang else f"{sim} official songs")
                queries.append(f"{sim} original songs")
        else:
            queries += [f"{artist} official songs", f"{artist} original song"]
            if lang:
                queries.append(f"{artist} {lang} official hits")

    if movie:
        queries += [f"{movie} official jukebox", f"{movie} all songs", f"{movie} original soundtrack"]

    lp = lang if lang in ("hindi", "punjabi", "bhojpuri", "haryanvi") else "hindi"
    if mood in _MOOD_QUERIES:
        queries += _MOOD_QUERIES[mood](lp)

    queries += _LANG_FALLBACK.get(lang, [f"best {lang} songs"])

    final: List[str] = []
    for q in queries:
        if any(b in q.lower() for b in BAD_WORDS):
            continue
        if q not in final and len(q) > 3:
            final.append(q)
    return final[:20]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BEST SONG PICKER  (filters + score)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def pick_next(chat_id: int, candidates: List[dict], ctx: Optional[dict] = None) -> Optional[dict]:
    """YouTube results mein se agla gaana (original result dict).  None = koi theek nahi.

    Hard filters : bad words, episode, same as last, duration 2-10 min, repeat,
                   devotional (jab mood devotional nahi), galat language, spam channel
    Score        : official / Topic channel, title overlap, artist, movie, language, mood,
                   same-artist penalty.   Official mile to sirf wahi; top-3 mein se random.
    """
    chat_id = int(chat_id)
    ctx = ctx or await get_context(chat_id) or {}
    last_title = ctx.get("title") or ctx.get("query") or ""
    last_vid = ctx.get("seed_vid") or ""
    artist, movie = ctx.get("artist") or "", ctx.get("movie") or ""
    mood, lang = ctx.get("mood") or "normal", ctx.get("lang") or "hindi"

    blocked = set(INCOMPATIBLE_LANGS.get(lang, []))
    recent_art = await recent_artists(chat_id)
    history = await _load_recent(chat_id)
    seed_keys = title_keys(last_title) + title_keys(ctx.get("query") or "")
    bad = [b for b in BAD_WORDS if not _has_any([b], last_title)]   # user ne khud maanga ho to allow

    scored = []
    for r in candidates or []:
        vid, raw = _vid(r), r.get("title") or ""
        tl = raw.lower()
        if not vid or vid == last_vid:
            continue
        if any(_has_any([b], tl) for b in bad) or _EPISODE_RE.search(tl):
            continue
        ckeys = title_keys(raw)
        if seed_keys and _keys_match(seed_keys, ckeys):      # seed gaana / uska koi bhi version
            continue
        sec = _result_duration(r)
        if sec and not (MIN_SEC <= sec <= MAX_SEC):
            continue
        if _repeat_in(history, vid, ckeys):
            continue
        if mood != "devotional" and _has_any(DEVOTIONAL_WORDS, tl):
            continue
        if blocked and _detect_title_lang(tl) in blocked:
            continue

        ch = _channel_name(r)
        if any(x in ch for x in SPAM_CHANNEL) or any(x in tl for x in SPAM_TITLE):
            continue

        score, official = 0, False
        if any(x in ch for x in ("vevo", "official", "records", "music")):
            official, score = True, score + 40
        if any(x in tl for x in ("official video", "official audio", "official music", "original song")):
            official, score = True, score + 35
        if ch.endswith(" - topic"):                     # YouTube ka auto original-track channel
            official, score = True, score + 60

        if artist and artist.lower() in tl:
            score += 50
            if tl.startswith(artist.lower()):
                score += 20
        if movie and movie.lower() in tl:
            score += 45
        if _has_any(LANG_DB.get(lang, []), tl):
            score += 20
        if mood != "normal" and _has_any(MOOD_DB.get(mood, []), tl):
            score += 15
        if artist and recent_art.count(artist.lower()) >= 3:
            score -= recent_art.count(artist.lower()) * 10

        scored.append((score, official, r))

    if not scored:
        return None
    pool = [s for s in scored if s[1]] or scored
    pool.sort(key=lambda x: x[0], reverse=True)
    return random.choice(pool[:3])[2]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AUTOPLAY  (naya search jab tak fresh gaana na mile)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def next_autoplay_song(
    chat_id: int, search_fn, max_queries: int = 12, batch: int = 3,
    reserve: bool = True, limit: int = 8,
    max_attempts: Optional[int] = None, use_mix: Optional[bool] = None,   # purane kwargs (ignore/alias)
) -> Optional[dict]:
    """Agla FRESH gaana.  search_fn: async def search_fn(query) -> [result dict]
    (result mein id, title, duration, channel).  Queries 3-3 ke batch mein chalti hain,
    batch ke saare results ek saath score hote hain (Vishal ki tarah).
    reserve=True: chuna gaana turant history mein (do autoplay ek saath => repeat nahi).
    None = fresh gaana nahi mila."""
    chat_id = int(chat_id)
    if max_attempts:
        max_queries = max_attempts
    lock = _LOCKS.setdefault(chat_id, asyncio.Lock())
    async with lock:
        ctx = await get_context(chat_id)
        if not ctx:
            return None
        queries = build_smart_queries(
            ctx.get("title") or ctx.get("query") or "latest hindi song",
            ctx.get("artist", ""), ctx.get("movie", ""), ctx.get("lang", "hindi"),
            ctx.get("mood", "normal"), await recent_artists(chat_id),
        )
        random.shuffle(queries)
        queries = queries[:max_queries]

        for i in range(0, len(queries), batch):
            pool: List[dict] = []
            for q in queries[i:i + batch]:
                try:
                    pool += (await search_fn(q) or [])[:limit]
                except Exception as err:
                    LOGGER.warning("autoplay search failed (%r): %s", q, err)
                await asyncio.sleep(0.15)
            song = await pick_next(chat_id, pool, ctx)
            if song:
                if reserve:
                    title = song.get("title") or ""
                    await add_recent(chat_id, _vid(song), title, extract_artist(title))
                LOGGER.info("Autoplay fresh | chat_id=%s | %r", chat_id, song.get("title"))
                return song
        LOGGER.warning("Autoplay: fresh gaana nahi mila | chat_id=%s", chat_id)
        return None


async def ensure_fresh(chat_id: int, song: dict, search_fn, **kw) -> Optional[dict]:
    """Bajane se theek pehle call karo: repeat ho to naya gaana, warna wahi."""
    if not await is_repeat(int(chat_id), _vid(song), song.get("title") or ""):
        return song
    return await next_autoplay_song(chat_id, search_fn, **kw)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  COMPATIBILITY  (Youtube.py / purane callers ke import na tootein)
#  Naam purane module wale, logic Vishal wala simple.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

STRICT_LANG = False        # Vishal ki tarah: sirf KNOWN galat language reject, anjaan pass
_EMOTION_MOODS = ("sad", "love", "party", "devotional", "wedding", "sufi")


def llm_enabled() -> bool:
    return False


def normalize_lang(x: Optional[str]) -> Optional[str]:
    """'Bhojpuri' / 'hindi/urdu' -> 'bhojpuri' / 'hindi'."""
    for w in _norm(x).split():
        if w in LANG_DB:
            return w
        if w in ("bangla",):
            return "bengali"
        if w in ("bollywood", "hinglish"):
            return "hindi"
    return None


def _lang_hint(title: Optional[str], channel: Optional[str] = None) -> Optional[str]:
    """Title/channel se language, pakki na ho to None (detect_lang jaisa, bina default hindi ke)."""
    text = f"{title or ''} {channel or ''}"
    for lang, keys in LANG_DB.items():
        if lang != "hindi" and _has_any(keys, text):
            return lang
    for lang, artists in ARTIST_LANG.items():
        if _has_any(artists, text):
            return lang
    return _detect_title_lang(_norm(text)) or ("hindi" if _has_any(LANG_DB["hindi"], text) else None)


def detect_language(title, channel=None, extra_text=None, use_channel_memory=True) -> Optional[str]:
    return _lang_hint(title, channel)


def language_match(lang: Optional[str], title, channel=None) -> int:
    """1 = wahi language, 0 = pata nahi, -1 = INCOMPATIBLE_LANGS wali galat language."""
    if not lang:
        return 1
    hint = _lang_hint(title, channel)
    if hint is None:
        return 0
    if hint == lang:
        return 1
    return -1 if hint in INCOMPATIBLE_LANGS.get(lang, []) else 0


def _moods_in(text: Optional[str]) -> set:
    return {m for m, keys in MOOD_DB.items() if _has_any(keys, text)}


def dominant_mood(text: Optional[str], soft: bool = False) -> Optional[str]:
    m = detect_mood(text or "")
    return None if m == "normal" else m


def mood_ok(mood, title, channel=None) -> bool:
    """Doosre emotion ka gaana reject (sad seed par party/love nahi). Mood na ho to sab pass."""
    if not mood or mood == "normal":
        return True
    found = _moods_in(f"{title or ''} {channel or ''}") & set(_EMOTION_MOODS)
    return not found or mood in found


def mood_hit(mood, title, channel=None) -> bool:
    return bool(mood) and mood != "normal" and mood in _moods_in(f"{title or ''} {channel or ''}")


def matches_core(core: str, title, channel=None, aliases=None) -> bool:
    """Title/channel mein artist ka naam (ya alias) hai?"""
    if not core:
        return True
    hay = _norm(f"{title or ''} {channel or ''}")
    return any(c and _has_any([_norm(c)], hay) for c in [core] + list(aliases or []))


def matches_topic(ctx: dict, title, channel=None) -> bool:
    hay = _norm(f"{title or ''} {channel or ''}")
    if any(ex and ex in hay for ex in (ctx or {}).get("exclude") or []):
        return False
    req = (ctx or {}).get("require_any") or []
    return not req or any(r in hay for r in req)


def looks_like_artist(core: str, results: list, durations: list) -> bool:
    return False            # Vishal mein artist/topic mode nahi -- hamesha song mode


async def learn_artist(core: str) -> None:
    return None             # Vishal ke dicts fixed hain; kuch seekhna nahi


async def add_artist(name: str, aliases=None, learned: bool = False) -> None:
    n = _norm(name)
    if n and n not in ARTIST_DB:
        ARTIST_DB[n] = [n] + [_norm(a) for a in (aliases or []) if _norm(a)]


async def add_artists_bulk(names: List[str]) -> int:
    c = 0
    for nm in names:
        if _norm(nm) and _norm(nm) not in ARTIST_DB:
            await add_artist(nm)
            c += 1
    return c


async def load_learned_artists() -> int:
    return 0


def artist_count() -> int:
    return len(ARTIST_DB)


async def classify_song(*_a, **_k):
    return None


async def verify_language(*_a, **_k):
    return None


async def learn_channel_language(*_a, **_k) -> None:
    return None


async def warm_channel_langs() -> None:
    return None


async def set_context_kind(chat_id: int, kind: str) -> None:
    await _save_context(int(chat_id), {"kind": kind})


async def autoplay_query(chat_id: int, ctx: Optional[dict] = None, attempt: int = 0) -> Optional[str]:
    """Purana API: attempt badhao to har baar alag query."""
    ctx = ctx or await get_context(int(chat_id))
    if not ctx:
        return None
    qs = build_smart_queries(
        ctx.get("title") or ctx.get("query") or "", ctx.get("artist", ""), ctx.get("movie", ""),
        ctx.get("lang", "hindi"), ctx.get("mood", "normal"), await recent_artists(int(chat_id)),
    )
    return qs[attempt % len(qs)] if qs else None


async def fetch_mix(vid: str, limit: int = 30) -> List[dict]:
    return []               # Vishal mein YouTube Mix nahi
