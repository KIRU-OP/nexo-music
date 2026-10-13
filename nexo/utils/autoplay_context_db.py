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
_QUERY_USED: Dict[int, List[str]] = {}  # chat_id -> chal chuke queries (rotation ke liye)


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
    "tuntun yadav":      ["khesari lal yadav", "pawan singh", "pramod premi", "dinesh lal yadav"],
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
        "manoj tiwari", "ritesh pandey", "tuntun yadav", "shilpi raj",
        "neelkamal singh", "samar singh", "arvind akela kallu", "ankush raja",
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
    "tuntun yadav":      ["tuntun", "tuntun yadav", "tun tun yadav", "tuntun song"],
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
# Remix / DJ / lofi family: seed gaana khud remix ya DJ ho tab bhi autoplay mein ye NAHI aayenge.
# (Pehle seed mein "remix"/"dj" hota tha to ye filter hat jata tha -> remix ke baad remix chalta tha.)
REMIX_FAMILY = [
    "remix", "dj remix", "dj", "mix", "lofi", "slowed", "reverb", "8d", "bass boosted",
    "sped up", "mashup", "hard bass", "jhan jhan bass", "vibration", "jbl", "dholki mix",
]
BAD_WORDS += [w for w in REMIX_FAMILY if w not in BAD_WORDS]
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
    t = re.sub(r"[^\w\s]|_", " ", _ascii(text).lower())     # "#Tuntun_Yadav" -> "tuntun yadav"
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


def _pad(text: Optional[str]) -> str:
    """Ek baar normalize karke ' text ' -- bade loops mein har key par dobara _norm na ho."""
    return f" {_norm(text)} "


def _in_pad(keys: List[str], padded: str) -> bool:
    return any(f" {k} " in padded for k in keys)


def _chan_str(channel) -> str:
    if isinstance(channel, dict):
        channel = channel.get("name")
    return channel if isinstance(channel, str) else ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  EXTENDED ARTIST DATABASE
#  (upar ke dicts ke saath merge hota hai; nexo/utils/autoplay_data.py ho to wo bhi)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

_EXTRA_ARTIST_LANG = {
    "hindi": [
        "asha bhosle", "mukesh", "manna dey", "hemant kumar", "talat mahmood", "mahendra kapoor",
        "kk", "kunal ganjawala", "sukhwinder singh", "abhijeet bhattacharya", "babul supriyo",
        "mithoon", "vishal mishra", "stebin ben", "ankit tiwari", "tulsi kumar", "tony kakkar",
        "payal dev", "palak muchhal", "monali thakur", "shalmali kholgade", "kanika kapoor",
        "nikhita gandhi", "asees kaur", "dhvani bhanushali", "jonita gandhi", "harshdeep kaur",
        "rekha bhardwaj", "vishal dadlani", "benny dayal", "papon", "javed ali", "ash king",
        "mika singh", "daler mehndi", "himesh reshammiya", "sachet tandon", "parampara thakur",
        "jasleen royal", "anuv jain", "yasser desai", "rochak kohli", "tanishk bagchi",
        "sajid wajid", "anu malik", "nadeem shravan", "jatin lalit", "anand milind",
        "laxmikant pyarelal", "rd burman", "sd burman", "bappi lahiri", "kailash kher",
        "mohammed irfan", "anuradha paudwal", "sadhana sargam", "kavita krishnamurthy",
        "jagjit singh", "pankaj udhas", "salim sulaiman", "sanam puri", "gajendra verma",
        "amaal mallik", "meet bros", "arko", "akhil sachdeva", "prateek kuhad", "raftaar",
        "emiway bantai", "mc stan", "sonu kakkar", "shahid mallya",
    ],
    "punjabi": [
        "gippy grewal", "jazzy b", "babbu maan", "gurdas maan", "surjit bindrakhia",
        "amrinder gill", "sharry mann", "kulwinder billa", "jassie gill", "jass manak",
        "parmish verma", "sunanda sharma", "nimrat khaira", "himmat sandhu", "bohemia",
        "kaka", "r nait", "babbal rai", "gur sidhu", "sunny malton", "miss pooja",
        "nachhatar gill", "harbhajan mann", "hans raj hans", "sukhshinder shinda",
        "satinder sartaaj", "tarsem jassar", "shree brar", "jordan sandhu", "harf cheema",
        "afsana khan", "inderjit nikku",
    ],
    "bhojpuri": [
        "ravi kishan", "awadhesh premi yadav", "gunjan singh", "antra singh priyanka",
        "priyanka singh", "kalpana patowary", "indu sonali", "khushboo uttam", "khushboo jain",
        "alka jha", "kavita yadav", "mohan rathore", "rakesh mishra", "vishal gagan",
        "bharat sharma vyas", "deepak dildar", "akshara singh", "amrapali dubey",
        "kajal raghwani", "yamini singh", "chandan chanchal", "sunil chhaila bihari",
        "pradeep pandey chintu", "golu gold", "raushan rohi", "rani chatterjee",
        "shivani singh", "anu dubey", "lado madheshiya", "ajit anand", "alok kumar",
    ],
    "haryanvi": [
        "vijay varma", "ajay hooda", "pranjal dahiya", "ruchika jangid", "sapna choudhary",
        "diler kharkiya", "gulzaar chhaniwala", "amit saini rohtakiya", "ak jatti",
        "sandeep surila", "ndee kundu", "anjali raghav", "manjeet panchal", "pardeep boora",
        "narender bhagana", "mohit sharma",
    ],
    "tamil": [
        "yuvan shankar raja", "harris jayaraj", "ilaiyaraaja", "santhosh narayanan",
        "hiphop tamizha", "d imman", "vijay antony", "haricharan",
    ],
    "telugu": [
        "mm keeravani", "anup rubens", "ram miryala", "mangli", "rahul sipligunj",
        "anurag kulkarni", "sunitha", "geetha madhuri", "kaala bhairava", "hemachandra",
    ],
    "bengali": [
        "anupam roy", "nachiketa chakraborty", "lopamudra mitra", "kabir suman",
        "hemanta mukherjee", "sandhya mukhopadhyay",
    ],
    "marathi": [
        "ajay atul", "adarsh shinde", "anand shinde", "avadhoot gupte", "vaishali samant",
        "swapnil bandodkar", "bela shende", "jasraj joshi", "ajay gogavale",
    ],
    "gujarati": [
        "kinjal dave", "geeta rabari", "kirtidan gadhvi", "jignesh kaviraj", "arvind barot",
        "aishwarya majmudar", "parthiv gohil", "osman mir", "rakesh barot", "vijay suvada",
        "falguni pathak", "atul purohit",
    ],
    "urdu": [
        "nusrat fateh ali khan", "abida parveen", "mehdi hassan", "ghulam ali",
    ],
    "english": [
        "dua lipa", "bruno mars", "coldplay", "imagine dragons", "maroon 5", "adele",
        "shawn mendes", "charlie puth", "selena gomez", "post malone", "harry styles",
        "olivia rodrigo", "sabrina carpenter", "lady gaga", "rihanna", "katy perry",
        "one direction", "linkin park", "alan walker", "marshmello", "martin garrix",
        "the chainsmokers", "david guetta", "calvin harris", "kygo", "avicii",
        "enrique iglesias", "shakira", "michael jackson", "sam smith", "lewis capaldi",
        "jason derulo", "camila cabello", "demi lovato", "miley cyrus", "ellie goulding",
        "zayn", "lana del rey", "doja cat", "travis scott", "kendrick lamar",
    ],
}

# Multi-language artists: ARTIST_DB mein rahenge, par language ka hint nahi denge
_NEUTRAL_ARTISTS = ["a r rahman", "hariharan", "shankar mahadevan"]

_EXTRA_ALIASES = {
    "dinesh lal yadav":  ["nirahua", "dinesh lal", "dinesh lal yadav nirahua"],
    "pramod premi":      ["pramod premi yadav"],
    "khesari lal yadav": ["khesari lal"],
    "arvind akela kallu": ["kallu ji", "arvind akela kallu ji"],
    "neelkamal singh":   ["neelkamal"],
    "pawan singh":       ["power star pawan singh"],
    "shilpi raj":        ["shilpi"],
    "a r rahman":        ["ar rahman"],
    "rahat fateh ali":   ["rahat fateh ali khan"],
}

_EXTRA_SIMILAR = {
    "samar singh":        ["pawan singh", "khesari lal yadav", "arvind akela kallu", "neelkamal singh"],
    "neelkamal singh":    ["samar singh", "pawan singh", "khesari lal yadav", "ritesh pandey"],
    "arvind akela kallu": ["pawan singh", "khesari lal yadav", "samar singh", "ritesh pandey"],
    "ritesh pandey":      ["pawan singh", "khesari lal yadav", "arvind akela kallu", "samar singh"],
    "shilpi raj":         ["antra singh priyanka", "kalpana patowary", "indu sonali", "khushboo uttam"],
    "dinesh lal yadav":   ["pawan singh", "khesari lal yadav", "pramod premi", "manoj tiwari"],
    "masoom sharma":      ["khasa aala chahar", "renuka panwar", "raj mawar", "sumit goswami"],
    "khasa aala chahar":  ["masoom sharma", "renuka panwar", "raj mawar", "sumit goswami"],
    "renuka panwar":      ["masoom sharma", "khasa aala chahar", "sapna choudhary"],
}


def _add_unique(lst: List[str], items) -> None:
    seen = set(lst)
    for it in items or []:
        n = _norm(str(it))
        if n and n not in seen:
            lst.append(n)
            seen.add(n)


def _extend_databases() -> None:
    taken = {n for lst in ARTIST_LANG.values() for n in lst}   # ek artist = ek language (pehli jeet)
    for lang, names in _EXTRA_ARTIST_LANG.items():
        bucket = ARTIST_LANG.setdefault(lang, [])
        _add_unique(bucket, [n for n in names if _norm(n) not in taken])
        taken.update(bucket)
    for lst in list(ARTIST_LANG.values()):
        for name in lst:
            ARTIST_DB.setdefault(name, [name, f"{name} song"])
    for name in _NEUTRAL_ARTISTS:
        ARTIST_DB.setdefault(name, [name, f"{name} song"])
    for name, aliases in _EXTRA_ALIASES.items():
        _add_unique(ARTIST_DB.setdefault(name, [name]), aliases)
    for name, sims in _EXTRA_SIMILAR.items():
        _add_unique(SIMILAR_ARTISTS.setdefault(name, []), sims)


# nexo/utils/autoplay_data.py ke ARTISTS ke categories -> language
_CAT_LANG = {
    "bhojpuri": "bhojpuri", "hindi_male": "hindi", "hindi_female": "hindi", "punjabi": "punjabi",
    "tamil": "tamil", "telugu": "telugu", "pakistani_urdu": "urdu", "english": "english",
}
# Ek category mein kai languages: (pehli language, [(is naam se aage ki language, None = koi lock nahi)])
_CAT_SPLIT = {
    "haryanvi_rajasthani":   ("haryanvi",  [("Seema Mishra", None)]),
    "gujarati_marathi":      ("gujarati",  [("Ajay Atul", "marathi")]),
    "bengali_assamese_odia": ("bengali",   [("Angarag Mahanta Papon", None)]),
    "malayalam_kannada":     ("malayalam", [("Ravi Basrur", "kannada")]),
}
_CAT_NEUTRAL = {"devotional", "kpop_world"}      # artist pehchano, par language lock mat lagao
_CAT_LABELS = {"channels"}                       # label/channel hain, artist nahi
_INDIAN_CATS = {"bhojpuri", "haryanvi_rajasthani", "hindi_male", "hindi_female", "punjabi",
                "gujarati_marathi", "bengali_assamese_odia", "tamil", "telugu",
                "malayalam_kannada", "devotional", "pakistani_urdu"}

# Aam shabd jo kisi artist ka naam bhi hain -- akele token ko artist/language hint mat maano
_COMMON_NAME_STOP = {
    "king", "divine", "vayu", "ninja", "strings", "junoon", "overload", "jojo", "queen",
    "future", "prince", "passenger", "oasis", "logic", "sting", "eagles", "muse", "twice",
    "rose", "cher", "nirvana", "keane", "usher", "lisa", "suga", "enya", "santana", "passenger",
}
_NAME_SUFFIX_NOISE = {
    "english", "kannada", "marathi", "odia", "assamese", "bengali", "bhajan", "bhakti", "songs",
    "pakistan", "qawwali", "ghazal", "gujarati", "punjabi", "hindi", "tamil", "telugu",
    "malayalam", "japanese", "spanish", "studio",
}
_EXT_LABELS: List[str] = []


def _split_names(block) -> List[str]:
    return [n.strip() for n in str(block).replace("\n", " ").split(",") if n.strip()]


def _clean_ext_name(raw: str, indian: bool) -> str:
    if re.search(r"[^\w\s.\-']", raw, re.UNICODE):          # "Kr$na" jaise naam chhod do
        return ""
    n = _norm(raw)
    toks = n.split()
    if not toks or len(n) < 2:
        return ""
    if len(toks) == 1:
        if n in _COMMON_NAME_STOP or (not indian and len(n) < 6):
            return ""
    elif toks[-1] in _NAME_SUFFIX_NOISE:                      # "arijit singh english" -> base naam kaafi hai
        return ""
    return n


def _merge_artists_block(artists: dict, aliases: dict) -> None:
    existing = {n for lst in ARTIST_LANG.values() for n in lst} | set(ARTIST_DB)
    ext_norm = {_norm(n) for blk in artists.values() for n in _split_names(blk)}

    # Alias groups: ek hi artist ke do naam (jaise "Pramod Premi" / "Pramod Premi Yadav") ek karo
    redirect: Dict[str, str] = {}
    groups: Dict[str, List[str]] = {}
    for canon, als in (aliases or {}).items():
        c = _norm(canon)
        al = [_norm(a) for a in (als or []) if _norm(a)]
        members = [m for m in [c] + al if m in existing or m in ext_norm]
        target = next((m for m in members if m in existing), c)
        for m in members:
            if m != target:
                redirect[m] = target
        groups[target] = [c] + al

    neutral = set(_NEUTRAL_ARTISTS) | {"ar rahman"}
    taken = {n for lst in ARTIST_LANG.values() for n in lst}

    for cat, block in artists.items():
        names = _split_names(block)
        if cat in _CAT_LABELS:
            _EXT_LABELS.extend(_norm(n) for n in names if _norm(n))
            continue
        indian = cat in _INDIAN_CATS
        if cat in _CAT_SPLIT:
            lang, switches = _CAT_SPLIT[cat][0], dict((_norm(a), b) for a, b in _CAT_SPLIT[cat][1])
        else:
            lang, switches = _CAT_LANG.get(cat), {}
        for raw in names:
            if _norm(raw) in switches:
                lang = switches[_norm(raw)]
            n = _clean_ext_name(raw, indian)
            if not n or redirect.get(n, n) != n:
                continue
            if cat in _CAT_NEUTRAL or n in neutral or not lang:
                ARTIST_DB.setdefault(n, [n, f"{n} song"])
            elif n not in taken:
                _add_unique(ARTIST_LANG.setdefault(lang, []), [n])
                taken.add(n)

    for target, members in groups.items():
        if target in _EXT_LABELS or any(m in _EXT_LABELS for m in members):
            _EXT_LABELS.extend(members)
            continue
        good = [m for m in members if m != target and
                (" " in m or (len(m) >= 6 and m not in _COMMON_NAME_STOP))]
        if good or target in ARTIST_DB or target in taken or target in ext_norm:
            _add_unique(ARTIST_DB.setdefault(target, [target, f"{target} song"]), good)


def _merge_external(ext) -> None:
    """nexo/utils/autoplay_data.py ko merge karo.
    1) ARTISTS (category -> "naam, naam, ...") + ALIASES (canonical -> [alias])  -- aapki file ka format
    2) simple dict-of-lists (ARTIST_LANG / ARTIST_DB / LANG_DB / MOOD_DB ... agar ho)"""
    targets = {
        "ARTIST_LANG": ARTIST_LANG, "ARTIST_DB": ARTIST_DB, "LANG_DB": LANG_DB,
        "MOOD_DB": MOOD_DB, "MOVIE_DB": MOVIE_DB, "SIMILAR_ARTISTS": SIMILAR_ARTISTS,
        "LANG_TITLE_INDICATORS": LANG_TITLE_INDICATORS,
    }
    for name, target in targets.items():
        src = getattr(ext, name, None)
        if not isinstance(src, dict):
            continue
        for k, v in src.items():
            if isinstance(v, (list, tuple, set)):
                _add_unique(target.setdefault(_norm(str(k)), []), v)
    artists, aliases = getattr(ext, "ARTISTS", None), getattr(ext, "ALIASES", None)
    if isinstance(artists, dict):
        _merge_artists_block(artists, aliases if isinstance(aliases, dict) else {})


# Malayalam / Kannada ab alag languages (autoplay_data.py mein inke artists hain)
LANG_DB.setdefault("malayalam", ["malayalam", "malayalam song", "mollywood"])
LANG_DB.setdefault("kannada", ["kannada", "kannada song", "sandalwood"])
LANG_DB.setdefault("assamese", ["assamese"])
LANG_DB.setdefault("odia", ["odia", "oriya"])


try:
    from nexo.utils import autoplay_data as _EXT_DATA
    _merge_external(_EXT_DATA)
except Exception as _err:           # file na ho / alag format ho -- koi baat nahi
    LOGGER.info("autoplay_data merge skipped: %s", _err)
_extend_databases()


def _artist_lang(artist: Optional[str]) -> str:
    a = _norm(artist)
    if not a:
        return ""
    for lang, names in ARTIST_LANG.items():
        if a in names:
            return lang
    return ""


def _best_artist_match(padded: str):
    """ARTIST_DB ke saare aliases mein sabse LAMBA match -> (artist, alias_len).
    "Mukesh Premi" par "mukesh" nahi, poora "mukesh premi" jeetega."""
    best, blen = "", 0
    for artist, keys in ARTIST_DB.items():
        for k in keys:
            if len(k) > blen and f" {k} " in padded:
                best, blen = artist, len(k)
    return best, blen


def is_remix(title: Optional[str], channel=None) -> bool:
    return _has_any(REMIX_FAMILY, f"{title or ''} {_chan_str(channel)}")


def _strip_remix(text: Optional[str]) -> str:
    padded = _pad(text)
    for _ in range(2):
        for w in sorted(REMIX_FAMILY, key=len, reverse=True):
            padded = padded.replace(f" {w} ", " ")
    return padded.strip()


def _is_remixer(name: Optional[str]) -> bool:
    n = _norm(name)
    return bool(n) and (n == "dj" or n.startswith("dj ") or _has_any(REMIX_FAMILY, n))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DETECT  (language / mood / artist / movie)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_lang(title: str) -> str:
    """1) title mein language ka naam  2) artist ka naam  3) default hindi"""
    if not title:
        return "hindi"
    padded = _pad(title)
    for lang, keys in LANG_DB.items():
        if _in_pad(keys, padded):
            return lang
    for lang, artists in ARTIST_LANG.items():
        if _in_pad(artists, padded):
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
    padded = _pad(title)
    found, _n = _best_artist_match(padded)
    if found:
        return found

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
            if f" {known} " in padded:
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

# Channel ka naam inme se ho to usse ARTIST mat samjho (label / company hai)
_LABEL_NAMES = {
    "t series", "tseries", "saregama", "zee", "sony", "tips", "venus", "yrf",
    "yash raj", "speed", "shemaroo", "goldmines", "lahari", "eros", "times",
    "t-series", "aditya", "jjust", "worldwide", "wave", "think", "desi",
}

# "X | Artist | Bhojpuri Song" mein "bhojpuri" gaane ka naam nahi -- warna har gaana repeat lagta hai
_GENERIC_KEYS = {_norm(x) for ks in LANG_DB.values() for x in ks} | set(LANG_DB) | {
    "bhajpuri", "new", "latest", "hit", "hits", "superhit", "jukebox", "full song",
}

_SPLIT_RE = re.compile(r"\s[-|\u2013\u2014]\s|\s(?:ft|feat|featuring)\.?\s", re.IGNORECASE)
_ARTIST_SET_CACHE = (0, frozenset())


def _artist_names() -> frozenset:
    global _ARTIST_SET_CACHE
    n = len(ARTIST_DB)
    if _ARTIST_SET_CACHE[0] != n:
        names = set(ARTIST_DB) | set(SIMILAR_ARTISTS)
        for _keys in ARTIST_DB.values():       # "tuntun" jaise alias bhi gaane ka naam nahi
            names.update(_keys)
        for lst in ARTIST_LANG.values():
            names.update(lst)
        _ARTIST_SET_CACHE = (n, frozenset(_norm(x) for x in names))
    return _ARTIST_SET_CACHE[1]


_GENERIC_TOKENS = set(_NOISE_WORDS) | set(_VERSION_NOISE) | {
    "bhojpuri", "bhajpuri", "haryanvi", "punjabi", "hindi", "bollywood", "gujarati",
    "tamil", "telugu", "bengali", "marathi", "urdu", "english", "songs", "hit", "hits",
    "superhit", "jukebox", "from", "feat", "ft", "featuring", "vs", "movie", "film",
    "dj", "mix", "lofi", "slowed", "reverb", "bass", "boosted", "jbl", "vibration", "hard", "jhan",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PHRASE_CACHE = (0, frozenset())


def _name_variants(name: str) -> set:
    """"khesari lal yadav" -> {"khesari lal yadav", "khesari lal", "khesari"}.
    Title mein aksar adhoora naam hota hai (#Khesari Lal) -- wo bhi artist hi hai."""
    toks = name.split()
    if not toks:
        return set()
    out = {name}
    if len(toks) >= 2:
        out.add(" ".join(toks[:2]))
        if len(toks[0]) >= 5:
            out.add(toks[0])
    return out


def _artist_phrases() -> frozenset:
    global _PHRASE_CACHE
    n = len(ARTIST_DB)
    if _PHRASE_CACHE[0] != n:
        phrases: set = set()
        for name in _artist_names():
            phrases |= _name_variants(name)
        phrases.discard("")
        _PHRASE_CACHE = (n, frozenset(phrases))
    return _PHRASE_CACHE[1]


def _strip_phrases(tokens: List[str], phrases) -> List[str]:
    """Tokens mein se artist ke naam (poore ya adhoore) nikaal do."""
    out: List[str] = []
    i = 0
    while i < len(tokens):
        for n in range(min(5, len(tokens) - i), 0, -1):
            if " ".join(tokens[i:i + n]) in phrases:
                i += n
                break
        else:
            out.append(tokens[i])
            i += 1
    return out


def title_keys(title: str, artist: str = "") -> List[str]:
    """Title ke saare 'gaane ke naam' wale hisse -- artist / hashtag / label / movie hata kar.

    "#Video #Khesari Lal #Aa Gaiel Palang Sagwan Ke"   -> ["aa gaiel palang sagwan ke"]
    'Palang Sagwan Ke (From "Pyaar Ka Rang")'          -> ["palang sagwan ke"]
    "Yo Yo Honey Singh - Blue Eyes (Official Video)"   -> ["blue eyes"]

    artist: ctx wala artist (ARTIST_DB mein na ho tab bhi) -- uska naam bhi hata diya jata hai.
    """
    if not title:
        return []
    t = _ascii(title).lower()
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", t)
    a = _norm(artist)
    phrases = _artist_phrases() | _name_variants(a) if a else _artist_phrases()
    names = _artist_names()
    keys: List[str] = []
    for seg in _SPLIT_RE.split(t):
        toks = _TOKEN_RE.findall(seg)
        if toks and toks[0] == "from":          # "- From Movie X": gaane ka naam nahi
            continue
        toks = [w for w in _strip_phrases(toks, phrases) if w not in _GENERIC_TOKENS]
        k = " ".join(toks)
        if len(k) < 4 or k in names or (set(toks) & _LABEL_TOKENS):
            continue
        if k not in keys:
            keys.append(k)
    return keys


def normalize_title(title: str, artist: str = "") -> str:
    """Purana API: gaane ka ek saaf naam (pehla key)."""
    keys = title_keys(title, artist)
    return keys[0] if keys else ""


def _tok_eq(a: str, b: str) -> bool:
    if a == b:
        return True
    return len(a) >= 5 and len(b) >= 5 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def _same_song(stored: str, candidate: str) -> bool:
    """Exact / prefix / spelling-similar / chhota naam bade ke andar / pehla lamba shabd same."""
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
    # chhote naam ke saare shabd bade naam mein hain (extra shabd: "aa", movie, hashtag)
    ss = set(short)
    if len("".join(ss)) >= 10 and all(any(_tok_eq(t, u) for u in long_) for t in ss):
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


async def is_repeat(chat_id: int, vidid: str, title: str = "", artist: str = "") -> bool:
    items = await _load_recent(int(chat_id))
    artist = artist or (_CACHE.get(int(chat_id)) or {}).get("artist", "")
    return _repeat_in(items, vidid, title_keys(title, artist))


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
    keys = title_keys(title, artist)
    items.append({
        "id": vidid,
        "title": keys[0] if keys else "",
        "keys": keys,
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
    padded = f" {ch} "
    for name in _artist_names():
        if name and f" {name} " in padded:
            return name
    return ""


_CHANNEL_NOISE = re.compile(
    r"\b(topic|official|vevo|music|records|record|channel|studio|studios|films|"
    r"entertainment|hd|company|series)\b")


for _lb in _EXT_LABELS:                      # autoplay_data.py ke "channels" -> label (artist nahi)
    _lb = re.sub(r"\s+", " ", _CHANNEL_NOISE.sub(" ", _lb)).strip()
    if len(_lb) >= 3:
        _LABEL_NAMES.add(_lb)


def _guess_artist(title: str, channel=None, query: str = "") -> str:
    """ARTIST_DB mein na ho (jaise Tuntun) to channel ka naam artist maano -- bas
    tab jab wo title / user ki query mein bhi aaye (label channel nahi)."""
    if isinstance(channel, dict):
        channel = channel.get("name")
    ch = _CHANNEL_NOISE.sub(" ", _norm(channel if isinstance(channel, str) else ""))
    ch = re.sub(r"\s+", " ", ch).strip()
    if len(ch) < 4 or ch in _LABEL_NAMES or (set(ch.split()) & _LABEL_NAMES):
        return ""
    hay = f" {_norm(title)} {_norm(query)} "
    if f" {ch} " in hay:
        return ch
    first = ch.split()[0]
    if len(first) >= 5 and first not in _LABEL_NAMES and f" {first} " in hay:
        return ch
    return ""


def _resolve_artist(title: str, channel=None, query: str = "") -> str:
    """extract_artist ka ankaa kabhi gaane ka NAAM hota hai ("Singer - Blue Eyes" mein
    separator ke baad wala hissa).  Anjaan naam tabhi maano jab channel se confirm ho,
    warna autoplay usi gaane ko dobara search karta hai."""
    artist = extract_artist(title)
    if artist and _is_remixer(artist):               # "X - DJ Rahul Remix" -> remixer artist nahi
        artist = ""
    if artist and artist not in _artist_names():
        ch = _norm(_chan_str(channel))
        ch = ch[:-6].strip() if ch.endswith(" topic") else ch
        if not (ch and (artist in ch or ch in artist)):
            artist = ""
    out = artist or _artist_from_channel(channel) or _guess_artist(title, channel, query)
    return "" if _is_remixer(out) else out


def _context_from_title(title: str, channel=None, query: str = "") -> dict:
    artist = _resolve_artist(title, channel, query)
    if not artist and query:                         # user ki query mein jaana-pehchana artist
        qa = extract_artist(query)
        if qa and qa in _artist_names() and not _is_remixer(qa):
            artist = qa
    remix = is_remix(title, channel)
    # remix/DJ seed: "dj" se mood "party" mat banao -- alag-alag normal gaane chalne chahiye
    mood_src = _strip_remix(title) if remix else title
    # Language: title/channel -> user ki query -> artist ki language.  Pakki na ho to "" (kuch lock nahi).
    # (Pehle "hindi" thop dete the aur Bhojpuri gaane INCOMPATIBLE_LANGS se block ho jate the.)
    lang = _lang_hint(title, channel) or (_lang_hint(query) if query else None) or _artist_lang(artist) or ""
    return {
        "title": title,
        "lang": lang,
        "mood": detect_mood(mood_src),
        "artist": artist,
        "movie": detect_movie(title),
        "remix": remix,
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
    await _save_context(int(chat_id), {"lang": lg or ""})


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
    cached = _CACHE.get(chat_id) or {}
    q = cached.get("query", "") if not cached.get("seed_vid") else ""   # user ki taaza query
    doc = _context_from_title(title, channel, q)
    doc["seed_vid"] = str(vid or "")
    await _save_context(chat_id, doc)
    LOGGER.info("Autoplay seed | chat_id=%s | %r | channel=%r | lang=%r artist=%r remix=%s",
                chat_id, title, _chan_str(channel), doc.get("lang"), doc.get("artist"), doc.get("remix"))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SMART QUERY BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

_MOOD_QUERIES = {
    "sad":        lambda lp: [f"sad {lp} songs", f"heartbreak {lp} songs"] + (["bewafa songs"] if lp == "hindi" else []),
    "love":       lambda lp: [f"romantic {lp} songs", f"love {lp} songs"] + (["ishq wala love song"] if lp == "hindi" else []),
    "party":      lambda lp: [f"party {lp} songs", f"dance {lp} songs"],
    "wedding":    lambda lp: [f"wedding {lp} songs"] + (["shaadi sangeet songs"] if lp == "hindi" else [f"{lp} shaadi songs"]),
    "devotional": lambda lp: [f"{lp} bhajan", f"{lp} aarti songs", f"{lp} bhakti songs"],
    "oldschool":  lambda lp: [f"90s {lp} songs", f"old {lp} songs"] + (["retro bollywood"] if lp == "hindi" else []),
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


def _clean_queries(queries: List[str]) -> List[str]:
    final: List[str] = []
    for q in queries:
        if any(_has_any([b], q) for b in BAD_WORDS):
            continue
        if q not in final and len(q) > 3:
            final.append(q)
    return final


_YEARS = list(range(2005, 2027))


def build_artist_queries(artist: str, lang: str = "") -> List[str]:
    """Sirf us artist ke gaane -- koi dusra artist / language nahi.
    Bahut saare alag-alag queries (purane gaane, saal-wise, mood-wise) taaki artist ka
    POORA catalogue mile, sirf top hits nahi."""
    a = (artist or "").lower().strip()
    if not a:
        return []
    qs = [
        f"{a} official songs", f"{a} original song", f"{a} new song",
        f"{a} hit songs", f"{a} superhit songs", f"{a} all songs",
        f"{a} top songs", f"{a} latest song",
        # purane / chhupe hue gaane
        f"{a} old songs", f"{a} purane gane", f"{a} old hit songs", f"{a} superhit old songs",
        f"{a} full video song", f"{a} film songs", f"{a} duet songs",
        f"{a} romantic songs", f"{a} love songs", f"{a} sad songs", f"{a} dard bhare gane",
        f"{a} dance songs", f"{a} masti songs", f"{a} shaadi songs",
    ]
    qs += [f"{a} {y} song" for y in _YEARS]          # saal-wise: har daur ke gaane
    if lang:
        qs += [f"{a} {lang} official hits", f"{a} {lang} songs", f"{a} {lang} old songs"]
    return _clean_queries(qs)


def similar_artists(artist: str, n_peers: int = 4) -> List[str]:
    """SIMILAR_ARTISTS + usi language ke kuch random aur artist (poori ARTIST_LANG se)."""
    a = _norm(artist)
    out = list(SIMILAR_ARTISTS.get(a, []))
    lang = _artist_lang(a)
    if lang:
        peers = [p for p in ARTIST_LANG.get(lang, []) if p != a and p not in out]
        random.shuffle(peers)
        out += peers[:n_peers]
    return out


def build_lang_queries(lang: str, n_artists: int = 10) -> List[str]:
    """Poori language ke alag-alag artists ke queries -- har baar naye random artists,
    taaki ek hi artist / ek hi tarah ke gaane na ghoomte rahein."""
    lang = (lang or "hindi").lower()
    pool = list(ARTIST_LANG.get(lang, []))
    random.shuffle(pool)
    qs = [f"{a} official songs" for a in pool[:n_artists]]
    qs += [f"{lang} official songs", f"{lang} superhit songs", f"{lang} new songs",
           f"{lang} romantic songs", f"{lang} sad songs", f"{lang} old songs"]
    qs += _LANG_FALLBACK.get(lang, [])
    return qs


def build_smart_queries(title, artist, movie, lang, mood, recent_artists_list=None) -> List[str]:
    """Artist ho to PEHLE sirf uske queries aate hain (artist-lock).  Phir usi language ke
    similar artists / mood / language-wide queries -- hamesha SEED KI LANGUAGE mein."""
    # NOTE: gaane ke apne title se query NAHI banti -- wahi gaana / cover wapas aata tha.
    queries: List[str] = build_artist_queries(artist, lang)

    if artist:
        for sim in similar_artists(artist):
            queries.append(f"{sim} official songs")

    if movie:
        queries += [f"{movie} official jukebox", f"{movie} all songs", f"{movie} original soundtrack"]

    lp = lang if lang in LANG_DB else "hindi"
    if mood in _MOOD_QUERIES:
        queries += _MOOD_QUERIES[mood](lp)

    queries += build_lang_queries(lang or "hindi")
    return _clean_queries(queries)[:90]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BEST SONG PICKER  (filters + score)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Ye languages "lock" hoti hain: seed Bhojpuri to sirf Bhojpuri (Hindi/English/Punjabi... nahi)
STRICT_LANGS = {"bhojpuri", "haryanvi", "gujarati", "tamil", "telugu", "bengali", "marathi",
                "malayalam", "kannada"}


def _artist_hit(artist: str, title: str, channel: str = "") -> bool:
    """Title / channel mein ye artist (ya uska alias) hai?"""
    a = _norm(artist)
    if not a:
        return False
    keys = {a} | {_norm(k) for k in ARTIST_DB.get(a, [])}
    first = a.split()[0]
    if a not in ARTIST_DB and len(first) >= 6:        # anjaan artist: "tuntun yadav" -> "tuntun"
        keys.add(first)
    return _has_any(sorted(keys), f"{title} {channel}")


async def pick_next(chat_id: int, candidates: List[dict], ctx: Optional[dict] = None,
                    strict_artist: bool = False) -> Optional[dict]:
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
    mood, lang = ctx.get("mood") or "normal", ctx.get("lang") or ""

    blocked = set(INCOMPATIBLE_LANGS.get(lang, [])) if lang else {"english"}   # language anjaan ho tab bhi English nahi
    recent_art = await recent_artists(chat_id)
    history = await _load_recent(chat_id)
    seed_keys = title_keys(last_title, artist) + title_keys(ctx.get("query") or "", artist)
    # live/cover/acoustic jaise words seed mein ho to allow; remix/DJ/lofi family kabhi allow nahi
    bad = [b for b in BAD_WORDS if b in REMIX_FAMILY or not _has_any([b], last_title)]
    strict_lang = lang in STRICT_LANGS

    scored = []
    for r in candidates or []:
        vid, raw = _vid(r), r.get("title") or ""
        tl = raw.lower()
        if not vid or vid == last_vid:
            continue
        if any(_has_any([b], tl) for b in bad) or _EPISODE_RE.search(tl):
            continue
        ckeys = title_keys(raw, artist)
        if seed_keys and _keys_match(seed_keys, ckeys):      # seed gaana / uska koi bhi version
            continue
        sec = _result_duration(r)
        if sec and not (MIN_SEC <= sec <= MAX_SEC):
            continue
        if _repeat_in(history, vid, ckeys):
            continue
        if mood != "devotional" and _has_any(DEVOTIONAL_WORDS, tl):
            continue
        ch = _channel_name(r)
        if _has_any(REMIX_FAMILY, ch):                   # DJ / remix / lofi wale channels
            continue
        art_hit = bool(artist) and _artist_hit(artist, raw, ch)
        if artist and strict_artist and not art_hit:     # artist-lock: dusre artist ka gaana nahi
            continue
        hint = _lang_hint(raw, ch)
        # artist ka apna gaana ho to language filter mat lagao
        if not art_hit:
            if blocked and hint in blocked:
                continue
            if strict_lang and hint and hint != lang:    # Bhojpuri seed par Hindi/English/Punjabi nahi
                continue
        lang_ok = bool(lang) and hint == lang

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
        if lang_ok:
            score += 40
        if mood != "normal" and _has_any(MOOD_DB.get(mood, []), tl):
            score += 15
        # (same-artist penalty hata di: user ko usi artist ka playlist chahiye)

        scored.append((score, official, r, art_hit, lang_ok))

    if not scored:
        return None
    if strict_lang:                      # language pakki wale mile to sirf wahi (anjaan language peeche)
        confirmed = [x for x in scored if x[4] or x[3]]
        if confirmed:
            scored = confirmed
    hits = [x for x in scored if x[3]]
    if artist and hits:                  # artist ke gaane mile to sirf wahi (official-only pool se bhi pehle)
        scored = hits
    scored = [x[:3] for x in scored]
    # official sirf bonus (score mein) -- exclusive nahi, warna purane gaane (chhote channels) kabhi nahi bajte
    scored.sort(key=lambda x: x[0], reverse=True)
    return random.choice(scored[:10])[2]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AUTOPLAY  (naya search jab tak fresh gaana na mile)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _probe_lang(chat_id: int, ctx: dict, search_fn) -> str:
    """Seed ki language title/channel se na mile to seed ko hi YouTube par search karo aur
    top results ki language ka vote lo (Bhojpuri gaana -> results mein Bhojpuri channel/artist).
    Seed per ek hi baar chalta hai; natija context mein save."""
    seed = ctx.get("title") or ctx.get("query") or ""
    if not seed or ctx.get("lang_probed") == seed:
        return ctx.get("lang") or ""
    try:
        res = await search_fn(seed) or []
    except Exception as err:
        LOGGER.warning("autoplay lang probe failed: %s", err)
        res = []
    votes: Dict[str, int] = {}
    for r in res[:12]:
        h = _lang_hint(r.get("title") or "", _channel_name(r))
        if h:
            votes[h] = votes.get(h, 0) + 1
    lang = ""
    if votes:
        top, n = max(votes.items(), key=lambda kv: kv[1])
        if n >= 2 and n * 2 >= sum(votes.values()):
            lang = top
    await _save_context(int(chat_id), {"lang": lang, "lang_probed": seed})
    LOGGER.info("Autoplay lang probe | chat_id=%s | %r -> %r (%s)", chat_id, seed, lang, votes)
    return lang


async def next_autoplay_song(
    chat_id: int, search_fn, max_queries: int = 12, batch: int = 3,
    reserve: bool = True, limit: int = 20,
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
        if not (ctx.get("lang") or ""):
            await _probe_lang(chat_id, ctx, search_fn)
            ctx = await get_context(chat_id) or ctx
        artist, lang = ctx.get("artist", ""), ctx.get("lang") or ""
        all_q = build_smart_queries(
            ctx.get("title") or ctx.get("query") or "latest hindi song",
            artist, ctx.get("movie", ""), lang, ctx.get("mood", "normal"),
        )
        art_set = set(build_artist_queries(artist, lang))
        head = [q for q in all_q if q in art_set]       # sirf artist ke queries
        tail = [q for q in all_q if q not in art_set]   # fallback (similar artist / lang)
        # Rotation: jo queries abhi nahi chali wo pehle -> har baar catalogue ka naya hissa
        used = _QUERY_USED.setdefault(chat_id, [])
        if head and all(q in used for q in head):
            used.clear()                                  # poora chakkar ho gaya, dobara shuru
        fresh_h = [q for q in head if q not in used]
        stale_h = [q for q in head if q in used]
        random.shuffle(fresh_h)
        random.shuffle(stale_h)
        random.shuffle(tail)
        head = fresh_h + stale_h                          # artist ke SAARE queries tail se pehle
        queries = head + tail[:max_queries]
        n_head = len(head)

        for i in range(0, len(queries), batch):
            pool: List[dict] = []
            for q in queries[i:i + batch]:
                try:
                    pool += (await search_fn(q) or [])[:limit]
                except Exception as err:
                    LOGGER.warning("autoplay search failed (%r): %s", q, err)
                await asyncio.sleep(0.15)
            used.extend(q for q in queries[i:i + batch] if q in art_set)
            del used[:-300]
            # artist ke queries par strict (dusra artist nahi); fallback par normal
            song = await pick_next(chat_id, pool, ctx, strict_artist=bool(artist) and i < n_head)
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


# Bhojpuri gaano ke title mein aane wale pakke shabd (jab "bhojpuri" likha na ho)
_BHOJPURI_WORDS = [
    "lagelu", "lagela", "lagelee", "kailu", "bhatar", "bhatara", "hamar", "hamaar",
    "tohar", "tohaar", "chhauri", "chhaura", "devarwa", "balamua", "piyawa", "sejiya", "sejia", "labar",
]
# Jude hue likhe naam bhi pakdo: "HamarBhojpuri", "भोजपुरी" (unidecode -> bhojpurii)
_COMPACT_LANG_TAGS = {
    "bhojpuri": ("bhojpuri", "bhojpurii", "bhajpuri", "bhojpuriya"),
    "haryanvi": ("haryanvi", "haryanavi", "hariyanvi"),
}


def _lang_hint(title: Optional[str], channel=None) -> Optional[str]:
    """Title/channel se language, pakki na ho to None.
    Order: language ka naam -> artist (poora ARTIST_LANG) -> title ke indicators -> Bhojpuri shabd."""
    padded = _pad(f"{title or ''} {_chan_str(channel)}")
    compact = padded.replace(" ", "")
    for lang, tags in _COMPACT_LANG_TAGS.items():
        if any(t in compact for t in tags):
            return lang
    for lang, keys in LANG_DB.items():
        if lang != "hindi" and _in_pad(keys, padded):
            return lang
    best = None                              # sabse lamba naam jeete ("mukesh premi" > "mukesh")
    for lang, artists in ARTIST_LANG.items():
        for a in artists:
            if f" {a} " in padded and (best is None or len(a) > best[0]):
                best = (len(a), lang)
    alias_artist, alias_len = _best_artist_match(padded)
    alias_lang = _artist_lang(alias_artist) if alias_artist else ""
    if alias_lang and (best is None or alias_len > best[0]):
        return alias_lang
    if best:
        return best[1]
    for lang, kws in LANG_TITLE_INDICATORS.items():
        if _in_pad(kws, padded):
            return lang
    if _in_pad(_BHOJPURI_WORDS, padded):
        return "bhojpuri"
    return "hindi" if _in_pad(LANG_DB["hindi"], padded) else None


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
