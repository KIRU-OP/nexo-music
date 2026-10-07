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

v2.5: LANGUAGE LOCK PAKKA -- Bhojpuri seed par jis gaane ki language pakki na ho wo bhi REJECT
  (pehle sirf "pehchani hui doosri language" rejected thi, anjaan Hindi/English nikal jaate the).
  Claude key ho to anjaan gaane verify hote hain; channel ki language yaad rehti hai; English pehchan.

v2.4: AUTO RE-SEARCH -- gaana repeat nikla to khud naya search karta hai jab tak fresh gaana na mile
  (next_autoplay_song / ensure_fresh). Race (do autoplay ek saath) se bhi repeat nahi hota.

v2.3: LANGUAGE LOCK -- Bhojpuri lagaya to Bhojpuri hi, Hindi to Hindi, Marathi to Marathi...
  Doosri language ka gaana kabhi nahi (dekho detect_language / language_match / pick_next).

v2.2: HAR gaane ka type (mood + language + genre) Claude se pehchana jata hai
  (ANTHROPIC_API_KEY env chahiye; na ho to keyword wala fallback chalta hai).
  Autoplay usi type ke gaane chunta hai -- kisi bhi gaane ke liye, sirf examples ke liye nahi.

v2.1 mein naya:
  * MOOD: user "sad song" ya koi sad gaana lagaye to autoplay sad hi rahega
    (romantic lagaye to romantic). Doosre mood ka gaana filter ho jata hai.
  * NO REPEAT: har chat ka played-history (DB mein) -- same gaana (ya uska
    lyrics / official video / remix version) dobara autoplay nahi hoga.

Isko `nexo/utils/autoplay_context_db.py` naam se rakho
(saath mein `nexo/utils/autoplay_data.py`).

Collections:
  autoplay_context : {"chat_id", "query", "kind", "core", "aliases", "ignore",
                      "search", "require_any", "exclude", "topics", "updated"}
  autoplay_artists : {"name", "aliases", "learned": True, "ts"}   (seekhe hue artists)
  autoplay_played  : {"chat_id", "items": [{"id", "key", "ts"}]}  (kya kya baj chuka)

  autoplay_song_types : {"key", "mood", "language", "genre", "queries", "ts"}  (classify cache)

Context doc mein ye naye fields bhi hain: "mood", "query_mood", "seed_vid", "seed_title",
"song_type", "type_queries", "lang", "query_lang".
"""

import asyncio
import json
import logging
import os
import re
import time
from difflib import SequenceMatcher, get_close_matches
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
playeddb = mongodb.autoplay_played
typesdb = mongodb.autoplay_song_types
chanlangdb = mongodb.autoplay_channel_langs

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
_ARTIST_LANG: Dict[str, str] = {}   # canonical artist -> language (ARTISTS ki key se)
_NAMESAKES: Dict[str, List[str]] = {}  # "aarti" -> ["aarti tabiyar", ...]
_LEARNED_LOADED = False


_LANG_KEYS = {
    "bhojpuri": "bhojpuri", "marathi": "marathi", "punjabi": "punjabi", "haryanvi": "haryanvi",
    "rajasthani": "rajasthani", "gujarati": "gujarati", "tamil": "tamil", "telugu": "telugu",
    "kannada": "kannada", "malayalam": "malayalam", "bengali": "bengali", "bangla": "bengali",
    "odia": "odia", "oriya": "odia", "assamese": "assamese", "urdu": "urdu", "english": "english",
    "hindi": "hindi", "bollywood": "hindi", "hinglish": "hindi", "nepali": "nepali",
    "maithili": "maithili", "magahi": "magahi", "garhwali": "garhwali", "pahari": "pahari",
    "sindhi": "sindhi", "kashmiri": "kashmiri", "konkani": "konkani", "pakistani": "urdu",
}


def _lang_from_key(key: str) -> Optional[str]:
    for w in re.split(r"[^a-z]+", (key or "").lower()):
        if w in _LANG_KEYS:
            return _LANG_KEYS[w]
    return None


def _register(name: str, aliases: Optional[List[str]] = None, lang: Optional[str] = None) -> None:
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
    if lang:
        _ARTIST_LANG.setdefault(canon, lang)
    for a in [canon] + [x for x in (aliases or [])]:
        n = _norm(a)
        if not n:
            continue
        group.add(n)
        _LOOKUP[n] = canon
        _NOSPACE[n.replace(" ", "")] = canon


def _build_index() -> None:
    for _lang, blob in ARTISTS.items():
        _lk = _lang_from_key(_lang)
        for raw in blob.split(","):
            _register(raw, lang=_lk)
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


def _parse_query_core(query: str) -> Optional[dict]:
    """Query se context nikalo (mood ke bina). None = URL / khali."""
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
# MOOD  (sad -> sad, romantic -> romantic)
# =====================================================================
MOOD_PRIORITY = ["sad", "romantic", "party", "devotional", "chill", "motivational"]

MOOD_WORDS: Dict[str, List[str]] = {
    "sad": [
        "sad", "dard", "dukh", "judai", "judaai", "bewafa", "bewafai", "bewafaa", "tanha",
        "tanhai", "aansu", "rona", "broken", "heartbreak", "heartbroken", "breakup", "gham",
        "udaas", "udas", "cry", "crying", "lonely", "alone", "alvida", "bichad", "bichhad",
        "dil toota", "toota", "pain", "sadness", "emotional",
        "सैड", "दर्द", "जुदाई", "बेवफा", "उदास", "आंसू", "ग़म", "गम",
    ],
    "romantic": [
        "romantic", "romance", "love", "pyar", "pyaar", "ishq", "ishk", "mohabbat",
        "muhabbat", "prem", "valentine", "couple", "love story",
        "रोमांटिक", "प्यार", "इश्क", "इश्क़", "मोहब्बत", "प्रेम",
    ],
    "party": ["party", "dance", "dj", "club", "nachne", "dhamaka", "item song", "पार्टी", "डांस"],
    "devotional": ["bhajan", "aarti", "bhakti", "devotional", "mantra", "chalisa", "भजन", "आरती", "भक्ति"],
    "chill": ["lofi", "lo fi", "chill", "relax", "relaxing", "sleep", "calm"],
    "motivational": ["motivational", "motivation", "inspirational", "workout", "gym"],
}

# Autoplay search ke variants (har baar alag query -> alag results -> kam repeat)
MOOD_SEARCH: Dict[str, List[str]] = {
    "sad": ["sad songs", "sad hindi songs", "dard bhare gaane", "heartbreak songs", "sad love songs", "bewafa songs"],
    "romantic": ["romantic songs", "romantic hindi songs", "love songs", "best love songs", "pyar ke gaane", "ishq songs"],
    "party": ["party songs", "dance songs", "dj party songs", "club songs"],
    "devotional": ["bhajan", "devotional songs", "bhakti songs", "aarti"],
    "chill": ["lofi songs", "chill songs", "relaxing songs", "lofi hindi"],
    "motivational": ["motivational songs", "workout songs", "inspirational songs"],
}

# Halke (soft) shabd: akele pakke nahi, par gaane ke title mein hon to bhaav batate hain.
# Sirf USER ke lagaye gaane (seed) ka mood nikalne mein use hote hain,
# autoplay results ko reject karne mein nahi.  "tu hai kahan" -> longing/sad
MOOD_SOFT: Dict[str, List[str]] = {
    "sad": [
        "kahan", "kidhar", "intezaar", "intezar", "intazaar", "yaad", "yaadein", "yaadon",
        "tere bina", "wapas", "laut aa", "lautaa", "kab aaoge", "dhundh", "dhoondh", "dhoondhta",
        "talash", "talaash", "tadap", "tadpa", "bekarar", "kho gaya", "khoya", "door", "dur",
        "alag", "chhod", "chod", "bhula", "bhoola", "rulaya", "rula", "zakhm", "ashq", "viraan",
    ],
    "romantic": [
        "sanam", "jaan", "dilbar", "mehboob", "humsafar", "tum hi ho", "mera tu", "tera mera",
        "hamesha", "saath", "sajna", "saajna", "piya", "balam", "tere naam", "kasam",
    ],
}

_MOOD_PHRASES: List[Tuple[str, str]] = sorted(
    [(_norm(w), m) for m, ws in MOOD_WORDS.items() for w in ws if _norm(w)],
    key=lambda x: -len(x[0]),
)
_SOFT_PHRASES: List[Tuple[str, str]] = sorted(
    [(_norm(w), m) for m, ws in MOOD_SOFT.items() for w in ws if _norm(w)],
    key=lambda x: -len(x[0]),
)


def detect_moods(text: Optional[str], soft: bool = False) -> Dict[str, float]:
    """Text mein kaun kaun se mood ke shabd hain -> {mood: score}.
    soft=True: halke bhaav-shabd bhi gino (0.5 each)."""
    padded = f" {_norm(text)} "
    scores: Dict[str, float] = {}
    for phrase, mood in _MOOD_PHRASES:
        if f" {phrase} " in padded:
            scores[mood] = scores.get(mood, 0) + 1
    if soft:
        for phrase, mood in _SOFT_PHRASES:
            if f" {phrase} " in padded:
                scores[mood] = scores.get(mood, 0) + 0.5
    return scores


def dominant_mood(text: Optional[str], soft: bool = False) -> Optional[str]:
    scores = detect_moods(text, soft=soft)
    if not scores:
        return None
    best = max(scores.values())
    for m in MOOD_PRIORITY:  # tie ho to priority order (sad > romantic > ...)
        if scores.get(m) == best:
            return m
    return None


def mood_ok(mood: Optional[str], title: Optional[str], channel: Optional[str] = None) -> bool:
    """Result doosre mood ka to nahi? Jisme koi mood shabd nahi wo pass hota hai."""
    if not mood:
        return True
    scores = detect_moods(_hay(title, channel))
    return not scores or mood in scores


def mood_hit(mood: Optional[str], title: Optional[str], channel: Optional[str] = None) -> bool:
    """Title/channel mein sach mein wahi mood likha hai? (best match)"""
    return bool(mood) and mood in detect_moods(_hay(title, channel))


# =====================================================================
# LANGUAGE LOCK  (Bhojpuri -> Bhojpuri, Hindi -> Hindi, Marathi -> Marathi ...)
# =====================================================================
LANG_NAMES = _LANG_KEYS
STRICT_LANG = os.getenv("AUTOPLAY_STRICT_LANG", "1") == "1"   # 1 (default) = non-Hindi seed par anjaan-language gaana REJECT

_SCRIPTS: List[Tuple["re.Pattern", str]] = [
    (re.compile(r"[\u0B80-\u0BFF]"), "tamil"),
    (re.compile(r"[\u0C00-\u0C7F]"), "telugu"),
    (re.compile(r"[\u0C80-\u0CFF]"), "kannada"),
    (re.compile(r"[\u0D00-\u0D7F]"), "malayalam"),
    (re.compile(r"[\u0980-\u09FF]"), "bengali"),
    (re.compile(r"[\u0A00-\u0A7F]"), "punjabi"),
    (re.compile(r"[\u0A80-\u0AFF]"), "gujarati"),
    (re.compile(r"[\u0B00-\u0B7F]"), "odia"),
    (re.compile(r"[\u0600-\u06FF]"), "urdu"),
]

# Us language ke khaas shabd (doosri languages se alag). Hindi ke liye koi nahi:
# Hindi wo hai jo baaki sab nahi (ya jab naam/artist/Claude bataye).
_LANG_MARKERS: Dict[str, set] = {
    "bhojpuri": {"hamar", "hamaar", "hamra", "tohar", "tohaar", "tohra", "tohre", "bhauji", "bhatar",
                 "bhatara", "lagelu", "lagela", "kailu", "kaile", "raua", "rauwa", "piyawa", "piyava",
                 "sajanwa", "balamua", "rajaji", "lagaiba", "hamse", "tohse", "lagelee", "bhojpuriya",
                 "हमार", "तोहार", "तोहरा", "भउजी", "भतार", "लागेला", "रउवा"},
    "marathi": {"ahe", "aahe", "majhi", "majhya", "mazi", "mazya", "tujhi", "tujhya", "tuzi", "tuzya",
                "tula", "aamhi", "amhi", "zingaat", "zingat", "lavani", "lavni", "mauli", "aaicha",
                "आहे", "माझी", "माझ्या", "तुझी", "तुझ्या", "तुला", "आम्ही", "लावणी", "माऊली"},
    "punjabi": {"kudi", "kudiye", "munda", "jatt", "jatti", "gabru", "tenu", "kithe", "pind", "bhangra",
                "sohni", "mahiya"},
    "haryanvi": {"haryanvi", "haryana", "chhori", "jaatni", "jatni"},
    "rajasthani": {"rajasthani", "padharo", "mhare", "mhari", "thare", "ghoomar"},
    "gujarati": {"garba", "gujarati"},
}


# English gaano ke title mein aam shabd (Hinglish titles mein kam aate hain). 2+ mile to English.
_EN_WORDS = {
    "the", "you", "your", "are", "was", "with", "and", "for", "this", "that", "not", "all", "just",
    "feel", "know", "want", "dont", "cant", "wanna", "gonna", "girl", "night", "sorry", "never",
    "ever", "after", "before", "without", "better", "world", "life", "heart", "dancing", "remember",
    "again", "forever", "always", "story", "somebody", "something", "nobody", "stay", "home",
}

# ---- channel ki language yaad rakho (Wave Music jaise multi-language channel ke liye share dekhta hai)
_CHAN_STATS: Dict[str, Dict[str, int]] = {}
_CHAN_LOADED = False


def _chan_key(channel: Optional[str]) -> str:
    return _norm(_roman(channel))


def _chan_lang(channel: Optional[str]) -> Optional[str]:
    st = _CHAN_STATS.get(_chan_key(channel))
    if not st:
        return None
    total = sum(st.values())
    lg, n = max(st.items(), key=lambda kv: kv[1])
    return lg if total >= 2 and n / total >= 0.8 else None


async def warm_channel_langs() -> None:
    """Ek baar DB se channel->language yaadasht memory mein lao (idempotent)."""
    global _CHAN_LOADED
    if _CHAN_LOADED:
        return
    _CHAN_LOADED = True
    try:
        async for doc in chanlangdb.find({}):
            if doc.get("key") and doc.get("counts"):
                _CHAN_STATS[doc["key"]] = dict(doc["counts"])
    except Exception as err:
        LOGGER.warning("warm_channel_langs failed: %s", err)


async def learn_channel_language(channel: Optional[str], lang: Optional[str]) -> None:
    """Pakki language wale gaane ka channel yaad rakho -> uske aage ke gaane pehchane jaayenge."""
    key = _chan_key(channel)
    lg = normalize_lang(lang)
    if not key or not lg:
        return
    st = _CHAN_STATS.setdefault(key, {})
    st[lg] = st.get(lg, 0) + 1
    try:
        await chanlangdb.update_one({"key": key}, {"$set": {"key": key, "counts": st}}, upsert=True)
    except Exception as err:
        LOGGER.warning("learn_channel_language failed: %s", err)


def normalize_lang(x: Optional[str]) -> Optional[str]:
    """'Bhojpuri' / 'hindi/urdu' / 'Hinglish' -> 'bhojpuri' / 'hindi' / 'hindi'."""
    for w in _norm(x).split():
        if w in LANG_NAMES:
            return LANG_NAMES[w]
    return None


def explicit_language(text: Optional[str]) -> Optional[str]:
    """Query / title mein sirf language ka NAAM likha ho to wahi ("bhojpuri sad songs")."""
    found = {LANG_NAMES[t] for t in _norm(text).split() if t in LANG_NAMES}
    return next(iter(found)) if len(found) == 1 else None


def detect_language(
    title: Optional[str],
    channel: Optional[str] = None,
    extra_text: Optional[str] = None,
    use_channel_memory: bool = True,
) -> Optional[str]:
    """Gaane ki language (bina Claude ke). Signals: language ka naam > script > artist > khaas shabd.
    Pakka na ho to None (zabardasti Hindi nahi maante)."""
    scores: Dict[str, float] = {}

    def add(lg: Optional[str], w: float) -> None:
        if lg:
            scores[lg] = scores.get(lg, 0) + w

    t_raw, c_raw, x_raw = title or "", channel or "", (extra_text or "")[:600]
    for raw, w in ((t_raw, 3), (c_raw, 2), (x_raw, 1)):
        for lg in {LANG_NAMES[t] for t in _norm(raw).split() if t in LANG_NAMES}:
            add(lg, w)
    for rx, lg in _SCRIPTS:
        if rx.search(t_raw) or rx.search(c_raw):
            add(lg, 4)

    roman = _norm(f"{_roman(t_raw)} {_roman(c_raw)}").split()
    raw_toks = set(_norm(f"{t_raw} {c_raw}").split()) | set(roman)
    try:
        names, _ = find_artists(roman)
        for nm in names:
            add(_ARTIST_LANG.get(nm), 2)
    except Exception:
        pass
    for lg, marks in _LANG_MARKERS.items():
        add(lg, min(len(raw_toks & marks), 3))
    if len(set(_norm(_roman(t_raw)).split()) & _EN_WORDS) >= 2 and not any(
        rx.search(t_raw) for rx, _ in _SCRIPTS
    ):
        add("english", 3)
    if use_channel_memory:
        add(_chan_lang(channel), 3)

    if not scores:
        return None
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    if ranked[0][1] < 2:
        return None
    if len(ranked) > 1 and ranked[1][1] == ranked[0][1]:
        return None
    return ranked[0][0]


def language_match(
    lang: Optional[str], title: Optional[str], channel: Optional[str] = None
) -> int:
    """1 = wahi language, 0 = pata nahi chala, -1 = doosri language (reject)."""
    if not lang:
        return 1
    cl = detect_language(title, channel)
    if cl is None:
        return 0
    return 1 if cl == lang else -1


async def set_language(chat_id: int, lang: Optional[str]) -> None:
    """Haath se language lock (ya None = hatao). Jaise /lang bhojpuri."""
    chat_id = int(chat_id)
    lg = normalize_lang(lang)
    await contextdb.update_one({"chat_id": chat_id}, {"$set": {"lang": lg}})
    if chat_id in _CACHE:
        _CACHE[chat_id]["lang"] = lg


def parse_query(query: str) -> Optional[dict]:
    """_parse_query_core + mood ("sad songs" -> mood=sad)."""
    parsed = _parse_query_core(query)
    if not parsed:
        return None
    qm = dominant_mood(_norm(query))
    parsed["query_mood"] = qm
    parsed["mood"] = qm
    ql = explicit_language(query)                  # "bhojpuri sad songs" -> bhojpuri
    parsed["query_lang"] = ql
    parsed["lang"] = ql if parsed.get("kind") != "artist" else None
    return parsed


# =====================================================================
# PLAYED HISTORY  (no repeat)
# =====================================================================
MAX_PLAYED = 200          # har chat ke last itne gaane yaad rakho
_SIMILAR = 0.86           # itna similar title = same gaana (lyrics / official video / remix)
_PLAYED: Dict[int, List[dict]] = {}

_TITLE_NOISE = re.compile(
    r"\b(official|video|videos|audio|lyrics?|lyrical|full|hd|hq|4k|1080p|song|songs|new|latest|"
    r"version|status|jukebox|ft|feat|featuring|remix|slowed|reverb|lofi|with|hindi|punjabi|"
    r"bhojpuri|tamil|telugu|english|movie|film|from|the|female|male|cover|unplugged|acoustic|"
    r"reprise|original|music|vevo|ost|soundtrack|bass|boosted|8d|3d|nightcore|studio|"
    r"visualizer|teaser|promo|out|now|hit|hits|best|top|20\d\d)\b"
)


# ---- Devanagari -> Roman (taaki "तू है कहाँ" aur "Tu Hai Kahan" same gaana mane jaayein)
_DEVA = re.compile(r"[\u0900-\u097F]")
_DEV_V = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri", "ए": "e",
          "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o", "ऍ": "e"}
_DEV_M = {"ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri", "े": "e", "ै": "ai",
          "ो": "o", "ौ": "au", "ॉ": "o", "ॅ": "e"}
_DEV_C = {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j",
          "झ": "jh", "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t",
          "थ": "th", "द": "d", "ध": "dh", "न": "n", "प": "p", "फ": "f", "ब": "b", "भ": "bh",
          "म": "m", "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s",
          "ह": "h", "ळ": "l", "क़": "q", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "r", "ढ़": "rh",
          "फ़": "f", "य़": "y"}


def _roman(text: Optional[str]) -> str:
    """Devanagari -> Roman (mota-mota). Roman text jaisa hai waisa."""
    text = text or ""
    if not _DEVA.search(text):
        return text
    out: List[str] = []
    n, i = len(text), 0
    while i < n:
        ch = text[i]
        if ch in _DEV_C:
            out.append(_DEV_C[ch])
            j = i + 1
            if j < n and text[j] == "\u093c":      # nukta
                j += 1
            nxt = text[j] if j < n else ""
            if nxt == "\u094d":                     # halant
                i = j + 1
                continue
            if nxt in _DEV_M:
                out.append(_DEV_M[nxt])
                i = j + 1
                continue
            if nxt and _DEVA.match(nxt):            # shabd ke beech mein -> 'a'
                out.append("a")
            i = j
            continue
        if ch in _DEV_V:
            out.append(_DEV_V[ch])
        elif ch in "\u0902\u0901":
            out.append("n")
        elif ch == "\u0903":
            out.append("h")
        elif ch in _DEV_M:
            out.append(_DEV_M[ch])
        elif ch in "\u093c\u094d":
            pass
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _phon(w: str) -> str:
    """Spelling ka farq mita do: kahan/kahaan/kaha, pyar/pyaar, ishq/ishk, mohabbat/muhabbat."""
    w = w.lower()
    for a, b in (("aa", "a"), ("ee", "i"), ("oo", "u"), ("ii", "i"), ("uu", "u"), ("ph", "f"),
                 ("ck", "k"), ("q", "k"), ("w", "v"), ("z", "j"), ("ai", "e"), ("ay", "e"),
                 ("o", "u")):
        w = w.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", w)


def _tok_eq(a: str, b: str) -> bool:
    if a == b:
        return True
    return len(a) >= 4 and len(b) >= 4 and SequenceMatcher(None, a, b).ratio() >= 0.84


def _fuzzy_overlap(small: set, big: set) -> int:
    """small ke kitne shabd big mein (spelling ka thoda farq chhodke) mil gaye."""
    ps = {_phon(w) for w in small}
    pb = {_phon(w) for w in big}
    return sum(1 for w in ps if any(_tok_eq(w, x) for x in pb))



def title_key(title: Optional[str]) -> str:
    """Title ko saaf karke key banao: bracket, 'official video' jaise shabd hata do."""
    t = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", _roman(title).lower())
    t = _norm(t)
    t = _TITLE_NOISE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def core_tokens(title: Optional[str], channel: Optional[str] = None) -> List[str]:
    """Sirf GAANE ke naam ke shabd: noise, channel ka naam aur artist ke naam hata ke.
    "Tu Hai Kahan - Raftaar (Official)" aur "Tu Hai Kahan | AUR Lyrics" -> dono ["tu","hai","kahan"]"""
    t = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", _roman(title).lower())
    toks = [w for w in _TITLE_NOISE.sub(" ", _norm(t)).split() if w]
    if not toks:
        return []
    drop = set(_norm(_roman(channel)).split()) if channel else set()
    try:
        _, used = find_artists(toks)          # known artists ke naam hata do
        toks = [w for w, u in zip(toks, used) if not u]
    except Exception:
        pass
    left = [w for w in toks if w not in drop]
    return left or toks


def parse_duration(d) -> Optional[int]:
    """Seconds / 'mm:ss' / 'h:mm:ss' -> int seconds (samajh na aaye to None)."""
    if d is None or d == "":
        return None
    if isinstance(d, (int, float)):
        return int(d) if d > 0 else None
    parts = str(d).strip().split(":")
    try:
        nums = [int(x) for x in parts]
    except ValueError:
        return None
    sec = 0
    for n in nums:
        sec = sec * 60 + n
    return sec or None


def _result_duration(r: dict) -> Optional[int]:
    return parse_duration(r.get("duration_sec") or r.get("duration") or r.get("duration_min"))


async def _load_played(chat_id: int) -> List[dict]:
    if chat_id in _PLAYED:
        return _PLAYED[chat_id]
    items: List[dict] = []
    try:
        doc = await playeddb.find_one({"chat_id": chat_id}, {"_id": 0})
        items = (doc or {}).get("items", [])
    except Exception as err:
        LOGGER.warning("load played failed: %s", err)
    _PLAYED[chat_id] = items
    return items


def _same_song(it: dict, vid: Optional[str], key: str, toks: set, dur: Optional[int]) -> bool:
    """Kya ye played item wahi gaana hai? (re-upload, doosra thumbnail, alag title wording bhi)"""
    if vid and it.get("id") == vid:
        return True
    k = it.get("key") or ""
    if key and k and (key == k or SequenceMatcher(None, key, k).ratio() >= _SIMILAR):
        return True
    t2 = set(it.get("toks") or [])
    if toks and t2:
        small, big = (toks, t2) if len(toks) <= len(t2) else (t2, toks)
        m = _fuzzy_overlap(small, big)       # spelling ke chhote farq maaf
        n = len(small)
        # chhote title ke saare shabd bade mein hain ("tum hi ho" in "tum hi ho aashiqui 2")
        if m == n and (n >= 3 or sum(len(w) for w in small) >= 10):
            return True
        # 3+ shabd milte aur 75%+ title same: baaki sirf extra (prod by, singer, label...)
        if m >= 3 and m / n >= 0.75:
            return True
        # duration lagbhag same + title ke aadhe shabd milte -> wahi gaana, doosri upload
        d2 = it.get("dur")
        if dur and d2 and abs(dur - d2) <= 4 and m >= 1 and m / n >= 0.5:
            return True
    return False


def _is_played(
    items: List[dict],
    vid: Optional[str],
    title: Optional[str],
    channel: Optional[str] = None,
    dur: Optional[int] = None,
) -> bool:
    key = title_key(title)
    toks = set(core_tokens(title, channel))
    return any(_same_song(it, vid, key, toks, dur) for it in items)


def _vid(r: dict) -> str:
    return str(r.get("id") or r.get("vidid") or r.get("videoId") or r.get("link") or "")


def _channel_name(r: dict) -> Optional[str]:
    ch = r.get("channel")
    if isinstance(ch, dict):
        return ch.get("name")
    return ch if isinstance(ch, str) else None


async def has_played(
    chat_id: int, vid: Optional[str], title: Optional[str],
    channel: Optional[str] = None, duration=None,
) -> bool:
    return _is_played(await _load_played(int(chat_id)), vid, title, channel, parse_duration(duration))


async def clear_played(chat_id: int) -> None:
    """Played history saaf (chahe to /stop ya 'end' par call karo)."""
    chat_id = int(chat_id)
    _PLAYED.pop(chat_id, None)
    await playeddb.delete_one({"chat_id": chat_id})


async def note_played(
    chat_id: int,
    vid: Optional[str],
    title: Optional[str],
    channel: Optional[str] = None,
    autoplayed: bool = False,
    extra_text: Optional[str] = None,
    duration=None,
) -> None:
    """Jab bhi koi gaana BAJE (user ka lagaya ya autoplay) ye call karo.

    * gaana history mein jud jata hai (dobara autoplay nahi hoga)
    * autoplayed=False (user ne khud lagaya) -> ye gaana "seed" ban jata hai:
        - seed_vid / seed_title save hote hain (related gaane isi se dhundhe jaate hain)
        - kind song/pending ho to mood nikala jata hai, is order mein:
            1. title ke pakke shabd ("sad", "pyar", ...)
            2. extra_text (YouTube tags / description, agar pass karo)
            3. title ke halke bhaav-shabd ("kahan", "yaad", "intezaar", ...)
    """
    chat_id = int(chat_id)
    items = await _load_played(chat_id)
    if not (vid and items and items[-1].get("id") == str(vid)):   # reserve ho chuka ho to dobara mat jodo
        items.append({
            "id": str(vid or ""),
            "key": title_key(title),
            "toks": core_tokens(title, channel),
            "title": (title or "")[:120],
            "dur": parse_duration(duration),
            "ts": int(time.time()),
        })
    del items[:-MAX_PLAYED]
    try:
        await playeddb.update_one({"chat_id": chat_id}, {"$set": {"items": items}}, upsert=True)
    except Exception as err:
        LOGGER.warning("save played failed: %s", err)

    if autoplayed:
        return  # autoplay se seed / mood kabhi nahi badalta (drift nahi hoga)
    _QSTART.pop(chat_id, None)   # naya seed -> search wapas shuru se
    ctx = await get_context(chat_id)
    if not ctx:
        return
    upd: dict = {"seed_vid": str(vid or ""), "seed_title": title_key(title)}
    if ctx.get("kind") in ("song", "pending"):
        upd["mood"] = (
            dominant_mood(title)
            or dominant_mood(extra_text)
            or dominant_mood(title, soft=True)
            or ctx.get("query_mood")
        )
        # seed ki language -- aage ka sara autoplay isi language mein
        # kuch na pata chale to Hindi maano (Claude key ho to wo baad mein sahi kar deta hai).
        # Isse Hindi seed par Bhojpuri/Marathi/Punjabi ke pakke-pehchane gaane nahi aate.
        upd["lang"] = (
            detect_language(title, channel, extra_text) or ctx.get("query_lang") or "hindi"
        )
    ctx.update(upd)
    ctx.pop("song_type", None)      # purane gaane ka type hata do
    ctx.pop("type_queries", None)
    _CACHE[chat_id] = ctx
    await contextdb.update_one(
        {"chat_id": chat_id},
        {"$set": upd, "$unset": {"song_type": "", "type_queries": ""}},
    )
    LOGGER.info("Autoplay seed | chat_id=%s | title=%r | mood=%s", chat_id, title, upd.get("mood"))

    # asli type (mood + language + genre) Claude se -- background mein, play ko rokta nahi
    if llm_enabled() and ctx.get("kind") in ("song", "pending"):
        task = asyncio.create_task(_apply_song_type(chat_id, str(vid or ""), title, channel, extra_text))
        _BG_TASKS.add(task)
        task.add_done_callback(_BG_TASKS.discard)


# =====================================================================
# SONG TYPE CLASSIFIER  (kisi bhi gaane ka mood + language + genre)
# =====================================================================
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLASSIFIER_MODEL = os.getenv("AUTOPLAY_CLASSIFIER_MODEL", "claude-haiku-4-5-20251001")
ALLOWED_MOODS = MOOD_PRIORITY + ["happy", "patriotic", "nostalgic"]
_TYPE_CACHE: Dict[str, dict] = {}
_BG_TASKS: set = set()


def llm_enabled() -> bool:
    return bool(ANTHROPIC_API_KEY)


async def _call_llm(system: str, user: str, max_tokens: int = 400) -> Optional[str]:
    """Claude ko ek chhota call. Fail / key nahi -> None."""
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import aiohttp

        payload = {
            "model": CLASSIFIER_MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers) as resp:
                data = await resp.json()
        if resp.status != 200:
            LOGGER.warning("LLM error %s: %s", resp.status, str(data)[:200])
            return None
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    except Exception as err:
        LOGGER.warning("LLM call failed: %s", err)
        return None


def _json_from(text: Optional[str], open_ch: str = "{", close_ch: str = "}"):
    if not text:
        return None
    a, b = text.find(open_ch), text.rfind(close_ch)
    if a < 0 or b <= a:
        return None
    try:
        return json.loads(text[a : b + 1])
    except Exception:
        return None


_CLASSIFY_SYSTEM = (
    "You classify songs for a music bot's autoplay. You know Hindi/Bollywood, Bhojpuri, Punjabi, "
    "Haryanvi, South Indian, Pakistani, English and other songs. Reply with ONLY compact JSON."
)


async def classify_song(
    title: Optional[str], channel: Optional[str] = None, extra_text: Optional[str] = None
) -> Optional[dict]:
    """Gaane ka type: {"mood","language","genre","queries":[...]}.  Cache hota hai."""
    key = title_key(title)
    if not key:
        return None
    if key in _TYPE_CACHE:
        return _TYPE_CACHE[key]
    try:
        doc = await typesdb.find_one({"key": key}, {"_id": 0})
        if doc:
            _TYPE_CACHE[key] = doc
            return doc
    except Exception:
        pass

    user = (
        f"Song title: {title}\nChannel: {channel or '-'}\nTags/description: {(extra_text or '-')[:400]}\n\n"
        f"Return JSON with keys:\n"
        f'  "mood": one of {ALLOWED_MOODS} (the emotional feel of the song, e.g. a song about searching '
        f"for / missing someone = sad)\n"
        f'  "language": e.g. hindi, bhojpuri, punjabi, haryanvi, tamil, telugu, english, ...\n'
        f'  "genre": e.g. bollywood, indie, folk, rap, ghazal, bhajan, dj remix, lofi ...\n'
        f'  "queries": 4 different YouTube search queries (max 6 words each) that would find OTHER songs '
        f"with the same mood, language and genre. Do NOT include this song's title."
    )
    info = _json_from(await _call_llm(_CLASSIFY_SYSTEM, user, 300))
    if not isinstance(info, dict) or info.get("mood") not in ALLOWED_MOODS:
        return None
    out = {
        "key": key,
        "mood": info["mood"],
        "language": str(info.get("language") or "").lower()[:30],
        "genre": str(info.get("genre") or "").lower()[:40],
        "queries": [str(q)[:80] for q in (info.get("queries") or []) if str(q).strip()][:5],
        "ts": int(time.time()),
    }
    _TYPE_CACHE[key] = out
    try:
        await typesdb.update_one({"key": key}, {"$set": out}, upsert=True)
    except Exception as err:
        LOGGER.warning("save song type failed: %s", err)
    return out


async def _apply_song_type(chat_id: int, vid: str, title, channel, extra_text) -> None:
    """Background: gaane ka type pehchano aur context mein daal do."""
    info = await classify_song(title, channel, extra_text)
    if not info:
        return
    ctx = await get_context(chat_id)
    if not ctx or ctx.get("seed_vid") != vid or ctx.get("kind") not in ("song", "pending"):
        return  # tab tak user ne doosra gaana laga diya
    llm_lang = normalize_lang(info.get("language"))
    upd = {
        "mood": info["mood"],
        "song_type": {"mood": info["mood"], "language": info["language"], "genre": info["genre"]},
        "type_queries": info.get("queries", []),
    }
    if llm_lang:
        upd["lang"] = llm_lang                    # Claude ki pehchaan local guess se behtar
    ctx.update(upd)
    _CACHE[chat_id] = ctx
    await contextdb.update_one({"chat_id": chat_id}, {"$set": upd})
    LOGGER.info("Song type | chat_id=%s | %r -> %s", chat_id, title, upd["song_type"])


_LANGV_CACHE: Dict[Tuple[str, str], bool] = {}


async def verify_language(lang: Optional[str], cands: List[dict]) -> Optional[set]:
    """Claude se: in gaano mein se kaun SACH MEIN `lang` language ke hain.
    Return: pass hue indices ka set; None = Claude available nahi / fail (caller reject kare)."""
    if not lang or not cands or not llm_enabled():
        return None
    ok: set = set()
    todo: List[int] = []
    for i, c in enumerate(cands):
        k = (title_key(c.get("title")), lang)
        if k in _LANGV_CACHE:
            if _LANGV_CACHE[k]:
                ok.add(i)
        else:
            todo.append(i)
    if todo:
        lines = "\n".join(f"{i}. {cands[i].get('title')} | {_channel_name(cands[i]) or '-'}" for i in todo)
        user = (
            f"Which of these songs are sung in the {lang.title()} language? Judge by title, channel and your "
            f"knowledge of the song. If a song is Hindi, English, Marathi, Punjabi, Haryanvi, or any language other "
            f"than {lang.title()}, or you are unsure, EXCLUDE it.\n\n{lines}\n\n"
            f"Return ONLY a JSON array of the numbers that are {lang.title()}."
        )
        arr = _json_from(await _call_llm(_CLASSIFY_SYSTEM, user, 150), "[", "]")
        if not isinstance(arr, list):
            return None
        good = {i for i in arr if isinstance(i, int)}
        for i in todo:
            _LANGV_CACHE[(title_key(cands[i].get("title")), lang)] = i in good
            if i in good:
                ok.add(i)
    return ok


async def _verify_candidates(
    ctx: dict, cands: List[dict], recent: List[str]
) -> Optional[List[int]]:
    """Claude se pucho: kaun se candidates theek hain?
      * pehle baj chuke gaane ka koi bhi re-upload / version / alag title wording NAHI
      * song mode mein: seed jaisa type (mood + language + vibe)
    Return: indices best-first ([] = koi nahi), None = LLM available nahi / fail."""
    st = ctx.get("song_type")
    if not cands or not llm_enabled() or not (st or recent):
        return None
    lines = "\n".join(
        f"{i}. {c.get('title')} | {_channel_name(c) or '-'} | {_result_duration(c) or '?'}s"
        for i, c in enumerate(cands)
    )
    rules = []
    user = ""
    if recent:
        user += "Recently played songs (already heard):\n" + "\n".join(f"- {t}" for t in recent) + "\n\n"
        rules.append(
            "EXCLUDE any candidate that is the SAME SONG as a recently played one, even if it is a "
            "different upload, channel, thumbnail, title wording, lyrics/audio/video/remix/slowed label"
        )
    if st:
        user += (
            f"Seed song: {ctx.get('seed_title')}\n"
            f"Seed type: mood={st.get('mood')}, language={st.get('language')}, genre={st.get('genre')}\n\n"
        )
        rules.append(
            "KEEP only candidates of the SAME type as the seed (same mood, similar vibe). "
            "LANGUAGE IS A HARD LOCK: only songs in the seed's exact language "
            f"({st.get('language')}); e.g. a Bhojpuri seed must never get Hindi, Marathi, Punjabi or any "
            "other language, and a Hindi seed must never get Bhojpuri etc. "
            "Exclude compilations/jukeboxes and songs of a different mood or language"
        )
    user += f"Candidates:\n{lines}\n\n"
    user += (
        "Return ONLY a JSON array of acceptable candidate numbers, best match first, [] if none. Rules: "
        + "; ".join(rules) + "."
    )
    arr = _json_from(await _call_llm(_CLASSIFY_SYSTEM, user, 120), "[", "]")
    if not isinstance(arr, list):
        return None
    return [i for i in arr if isinstance(i, int) and 0 <= i < len(cands)]


# =====================================================================
# AUTOPLAY PICKER
# =====================================================================
def mix_url(vid: str) -> str:
    """YouTube Mix (RD playlist): gaane ke bilkul related gaane, YouTube khud chunta hai."""
    return f"https://www.youtube.com/watch?v={vid}&list=RD{vid}"


async def fetch_mix(vid: str, limit: int = 30) -> List[dict]:
    """Seed gaane ka YouTube Mix -> [{"id","title","channel"}]. yt-dlp chahiye;
    na ho ya fail ho to [] (tab autoplay_query wala search chalega)."""
    if not vid:
        return []
    try:
        import asyncio
        import yt_dlp
    except Exception:
        return []

    def _run() -> List[dict]:
        opts = {"quiet": True, "no_warnings": True, "extract_flat": True,
                "skip_download": True, "playlistend": limit}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(mix_url(vid), download=False) or {}
        out = []
        for e in info.get("entries") or []:
            if e and e.get("id"):
                out.append({"id": e["id"], "title": e.get("title"),
                            "duration": e.get("duration"),
                            "channel": {"name": e.get("channel") or e.get("uploader")}})
        return out

    try:
        return await asyncio.get_running_loop().run_in_executor(None, _run)
    except Exception as err:
        LOGGER.warning("fetch_mix failed: %s", err)
        return []


_QUERY_SUFFIX = ["", "new", "old", "hits", "top", "latest", "best", "superhit", "2024", "2023", "2022"]


async def autoplay_query(chat_id: int, ctx: Optional[dict] = None, attempt: int = 0) -> Optional[str]:
    """Autoplay ke liye YouTube search query. attempt badhao (0,1,2...) -- har attempt
    par HAMESHA alag query aati hai (variants khatam hon to 'new/old/hits/2024...' jodta hai).

    Song mode: pehle Claude ki type-queries / seed ke related, phir mood wale variants."""
    chat_id = int(chat_id)
    ctx = ctx or await get_context(chat_id)
    if not ctx:
        return None
    mood = ctx.get("mood")
    kind = ctx.get("kind")
    lg = ctx.get("lang")

    variants: List[str] = []
    if kind in ("song", "pending"):
        seed = (ctx.get("seed_title") or ctx.get("core") or "").strip()
        variants = list(ctx.get("type_queries") or [])   # Claude ke banaye, gaane ke type wale
        if seed:
            variants += [f"{seed} similar songs", f"songs like {seed}", f"{seed} jaise gaane"]
        if mood:
            variants += MOOD_SEARCH.get(mood) or [f"{mood} songs"]
    if not variants:
        base = ctx.get("search") or ""
        if not base:
            return None
        if mood and mood not in base:
            base = f"{mood} {base}"
        variants = [base]
    if lg:   # har query mein usi language ka naam (doosri language ka shabd hata ke)
        fixed: List[str] = []
        for v in variants:
            v = " ".join(w for w in v.split() if LANG_NAMES.get(w.lower(), lg) == lg)
            v = v if lg in v.lower() else f"{lg} {v}"
            if v not in fixed:
                fixed.append(v)
        variants = fixed

    n = len(variants)
    rnd = attempt // n                       # kitni baar poori list ghoom chuki
    q = variants[attempt % n]
    suf = _QUERY_SUFFIX[rnd % len(_QUERY_SUFFIX)]
    return f"{q} {suf}".strip()


async def pick_next(chat_id: int, candidates: List[dict]) -> Optional[dict]:
    """YouTube results mein se agla gaana chuno.

    Rules (is order mein):
      1. pehle bajaa hua gaana (ya uska lyrics/official/remix version) NAHI
      2. artist mode -> usi artist ka; topic mode -> usi topic ka
      3. mood set hai to doosre mood ka NAHI (sad -> sad, romantic -> romantic)
      4. ANTHROPIC_API_KEY ho to Claude: re-upload wale repeat hataata hai, aur song mode mein
         check karta hai ki candidate seed jaisa
         (mood + language + vibe) hai -- isse kisi bhi gaane ke liye same type chalta hai
    Kuch na mile to None -> autoplay_query(..., attempt+1) se dobara search karo.
    """
    chat_id = int(chat_id)
    ctx = await get_context(chat_id) or {}
    kind = ctx.get("kind")
    mood = ctx.get("mood")
    played = await _load_played(chat_id)

    lang = ctx.get("lang") if kind in ("song", "pending", "topic") else None
    tiers: List[List[dict]] = [[], [], [], []]   # lang+mood, lang, mood, baaki
    unknown: List[dict] = []                      # language pata nahi -> Claude verify (strict mode)
    repeats = 0
    for r in candidates or []:
        title, ch, vid = r.get("title"), _channel_name(r), _vid(r)
        if _is_played(played, vid, title, ch, _result_duration(r)):
            repeats += 1
            continue
        if kind == "artist" and not matches_core(ctx.get("core", ""), title, ch, ctx.get("aliases")):
            continue
        if kind == "topic" and not matches_topic(ctx, title, ch):
            continue
        if not mood_ok(mood, title, ch):
            continue
        lm = language_match(lang, title, ch)
        if lm < 0:
            continue                      # doosri language -- kabhi nahi
        if lang and lm == 0 and STRICT_LANG and lang != "hindi":
            unknown.append(r)             # pakka nahi -> bina verify ke nahi chalega
            continue
        mh = bool(mood and mood_hit(mood, title, ch))
        lh = bool(lang and lm == 1)
        tiers[0 if (lh and mh) else 1 if lh else 2 if mh else 3].append(r)

    if unknown and lang:
        okset = await verify_language(lang, unknown[:15])
        for i in sorted(okset or []):
            r = unknown[i]
            mh = bool(mood and mood_hit(mood, r.get("title"), _channel_name(r)))
            tiers[0 if mh else 1].append(r)
            await learn_channel_language(_channel_name(r), lang)   # LLM ne confirm kiya -> channel yaad
    if repeats:
        LOGGER.info("Autoplay repeat skipped | chat_id=%s | %d/%d candidates", chat_id, repeats, len(candidates or []))
    ordered = [r for t in tiers for r in t]   # pakki language + mood wale pehle
    if not ordered:
        return None

    # Claude ka final check: repeat (re-upload bhi) + song mode mein same type
    recent = [it.get("title") for it in played[-15:] if it.get("title")]
    if kind not in ("song", "pending"):
        ctx = {**ctx, "song_type": None}   # artist/topic mode mein sirf repeat check
    idxs = await _verify_candidates(ctx, ordered[:10], recent)
    if idxs is not None:                   # Claude ne jawab diya
        return ordered[idxs[0]] if idxs else None
    return ordered[0]


# =====================================================================
# AUTO RE-SEARCH  (repeat mila to khud naya search -- jab tak fresh gaana na mile)
# =====================================================================
_QSTART: Dict[int, int] = {}              # chat -> kis query attempt se shuru karein (purani queries khatam)
_LOCKS: Dict[int, "asyncio.Lock"] = {}    # ek chat mein ek waqt par ek hi autoplay pick


async def _reserve(chat_id: int, song: dict) -> None:
    """Chuna hua gaana turant history mein daal do -- doosra autoplay ek saath chale to
    wahi gaana dobara na chune. (Seed/mood nahi badalta.)"""
    await note_played(
        chat_id, _vid(song), song.get("title"), _channel_name(song),
        autoplayed=True, duration=_result_duration(song),
    )


async def next_autoplay_song(
    chat_id: int,
    search_fn,
    max_attempts: int = 12,
    use_mix: bool = True,
    reserve: bool = True,
) -> Optional[dict]:
    """Agla FRESH gaana. Repeat ya galat language/mood mila to apne aap naya search karta hai.

    search_fn: async def search_fn(query: str) -> List[dict]   (aapka YouTube search;
               har dict mein id, title, channel, duration)
    Flow:  YouTube Mix -> query attempt 0 -> 1 -> 2 ... (har baar alag query)
    reserve=True: chuna hua gaana turant history mein; baad mein
                  note_played(..., autoplayed=True) call karna zaroori nahi.
    None = max_attempts mein bhi fresh gaana nahi mila (caller autoplay band kare / bataye).
    """
    chat_id = int(chat_id)
    lock = _LOCKS.setdefault(chat_id, asyncio.Lock())
    async with lock:
        ctx = await get_context(chat_id)
        if not ctx:
            return None

        async def _done(song: dict, attempt: int) -> dict:
            _QSTART[chat_id] = attempt
            if reserve:
                await _reserve(chat_id, song)
            return song

        if use_mix and ctx.get("kind") in ("song", "pending") and ctx.get("seed_vid"):
            song = await pick_next(chat_id, await fetch_mix(ctx["seed_vid"]))
            if song:
                return await _done(song, _QSTART.get(chat_id, 0))

        start = _QSTART.get(chat_id, 0)
        tried: set = set()
        for k in range(max_attempts):
            attempt = start + k
            q = await autoplay_query(chat_id, ctx, attempt)
            if not q or q in tried:
                continue
            tried.add(q)
            try:
                results = await search_fn(q)
            except Exception as err:
                LOGGER.warning("autoplay search failed (%r): %s", q, err)
                continue
            song = await pick_next(chat_id, results or [])
            if song:
                LOGGER.info("Autoplay fresh | chat_id=%s | attempt=%d | q=%r | %r",
                            chat_id, attempt, q, song.get("title"))
                return await _done(song, attempt)
            LOGGER.info("Autoplay re-search | chat_id=%s | q=%r -> repeat/mismatch, naya search", chat_id, q)
        LOGGER.warning("Autoplay: %d attempts mein fresh gaana nahi mila | chat_id=%s", max_attempts, chat_id)
        return None


async def ensure_fresh(chat_id: int, song: dict, search_fn, **kw) -> Optional[dict]:
    """Aakhri safety net: bajane se THEEK PEHLE call karo, kisi bhi raaste se gaana aaya ho.
    Repeat nikla to apne aap naya search karke fresh gaana deta hai; fresh hai to wahi lauta deta hai."""
    chat_id = int(chat_id)
    played = await _load_played(chat_id)
    if not _is_played(played, _vid(song), song.get("title"), _channel_name(song), _result_duration(song)):
        return song
    LOGGER.info("Autoplay repeat pakda (ensure_fresh) | chat_id=%s | %r -> naya search", chat_id, song.get("title"))
    return await next_autoplay_song(chat_id, search_fn, **kw)


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
    upd: dict = {"kind": kind}
    ctx = await get_context(chat_id)
    if ctx and kind in ("artist", "topic"):
        # pending ke time pehle gaane se jo mood aaya tha wo artist/topic par lagu nahi
        upd["mood"] = ctx.get("query_mood")
        upd["lang"] = ctx.get("query_lang") if kind == "topic" else None
    await contextdb.update_one({"chat_id": chat_id}, {"$set": upd})
    if chat_id in _CACHE:
        _CACHE[chat_id].update(upd)


async def clear_context(chat_id: int) -> None:
    chat_id = int(chat_id)
    _CACHE.pop(chat_id, None)
    await contextdb.delete_one({"chat_id": chat_id})
