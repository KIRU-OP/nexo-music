import asyncio
import json
import os
import re
import shlex
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Union
import string
import requests
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from youtubesearchpython.__future__ import VideosSearch
try:
    from youtubesearchpython.__future__ import Recommendations
except ImportError:
    Recommendations = None
import base64
from nexo import LOGGER
from nexo.utils.database import is_on_off
from nexo.utils.formatters import time_to_seconds
from nexo.utils.url_guard import is_safe_media_url
from nexo.security import build_subprocess_env
from nexo.utils.stream.source_status import set_youtube_source_status
from nexo.utils.autoplay_context_db import (
    learn_artist,
    looks_like_artist,
    matches_core,
    matches_topic,
)
try:   # language lock + mood (autoplay_context_db v2.3+). Purana module ho to bina lock ke chalta hai.
    from nexo.utils.autoplay_context_db import (
        STRICT_LANG as _STRICT_LANG,
        classify_song,
        detect_language,
        dominant_mood,
        language_match,
        learn_channel_language,
        llm_enabled,
        mood_hit,
        mood_ok,
        normalize_lang,
        verify_language,
        warm_channel_langs,
    )
    _LANG_LOCK = True
except ImportError:  # pragma: no cover
    _LANG_LOCK = False
    _STRICT_LANG = False

    def detect_language(*_a, **_k):
        return None

    def dominant_mood(*_a, **_k):
        return None

    def language_match(*_a, **_k):
        return 1

    def mood_hit(*_a, **_k):
        return False

    def mood_ok(*_a, **_k):
        return True

    def normalize_lang(x):
        return x

    async def classify_song(*_a, **_k):
        return None

    async def verify_language(*_a, **_k):
        return None

    async def learn_channel_language(*_a, **_k):
        return None

    async def warm_channel_langs():
        return None

    def llm_enabled():
        return False
from nexo.utils.played_db import _same_song
from config import DURATION_LIMIT, YT_API_KEY, YTPROXY_URL, autoclean

logger = LOGGER(__name__)

# Worker API (kept configurable through env for production overrides)
WORKER_FALLBACK_API_URL = os.getenv(
    "WORKER_FALLBACK_API_URL",
    "https://youtubenewapi.skybotsdeveloper.workers.dev",
).strip()
WORKER_FALLBACK_API_KEY = os.getenv("WORKER_FALLBACK_API_KEY", "itsmesid").strip()
YTPROXY = (YTPROXY_URL or "").strip().rstrip("/")
YT_API_KEY = (YT_API_KEY or "").strip()
MIN_CACHED_MEDIA_BYTES = 128 * 1024
DOWNLOAD_CACHE_EXTENSIONS = (".m4a", ".mp3", ".mp4", ".webm")


def int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def bool_env(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "off", "no"}


# ---------------------------------------------------------------------------
# Resilient video lookup: retry VideosSearch, then fall back to yt-dlp
# ---------------------------------------------------------------------------
VIDEO_SEARCH_ATTEMPTS = max(1, int_env("YOUTUBE_SEARCH_ATTEMPTS", 4))
VIDEO_SEARCH_RETRY_DELAY = max(0, int_env("YOUTUBE_SEARCH_RETRY_DELAY_MS", 800)) / 1000


def _format_duration(seconds) -> str:
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "None"
    if seconds <= 0:
        return "None"
    h, rem = divmod(seconds, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _ytdlp_entry_to_result(entry: dict):
    vid = entry.get("id")
    if not vid:
        return None
    thumb = entry.get("thumbnail")
    if not thumb:
        thumbs = entry.get("thumbnails") or []
        thumb = thumbs[-1].get("url") if thumbs else None
    thumb = thumb or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return {
        "id": vid,
        "title": entry.get("title") or "Unknown",
        "duration": _format_duration(entry.get("duration")),
        "link": entry.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}",
        "thumbnails": [{"url": thumb}],
    }


def _ytdlp_lookup_sync(query: str, limit: int) -> list:
    is_url = query.startswith(("http://", "https://"))
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "extract_flat": False if is_url else "in_playlist",
    }
    target = query if is_url else f"ytsearch{limit}:{query}"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(target, download=False)
    entries = info.get("entries") if info and "entries" in info else [info]
    results = []
    for entry in entries or []:
        item = _ytdlp_entry_to_result(entry or {})
        if item:
            results.append(item)
    return results[:limit]


async def search_videos_with_retry(query: str, limit: int = 1) -> list:
    """Return a non-empty list of VideosSearch-style results or raise ValueError."""
    last_exc = None
    for attempt in range(1, VIDEO_SEARCH_ATTEMPTS + 1):
        try:
            data = await VideosSearch(query, limit=limit).next()
            results = (data or {}).get("result") or []
            if results:
                return results
            last_exc = ValueError("empty search result")
        except Exception as e:
            last_exc = e
        logger.warning(
            f"VideosSearch attempt {attempt}/{VIDEO_SEARCH_ATTEMPTS} failed "
            f"for {query!r}: {last_exc}"
        )
        if attempt < VIDEO_SEARCH_ATTEMPTS:
            await asyncio.sleep(VIDEO_SEARCH_RETRY_DELAY * attempt)

    # Last resort: yt-dlp
    for attempt in range(1, 3):
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None, _ytdlp_lookup_sync, query, limit
            )
            if results:
                logger.info(f"yt-dlp fallback succeeded for {query!r}")
                return results
        except Exception as e:
            last_exc = e
            logger.warning(f"yt-dlp lookup attempt {attempt}/2 failed for {query!r}: {e}")
            await asyncio.sleep(VIDEO_SEARCH_RETRY_DELAY)

    raise ValueError(f"Failed to fetch track details: {last_exc}")


STREAM_HTTP_PROBE_TIMEOUT = max(2, int_env("YOUTUBE_STREAM_HTTP_PROBE_TIMEOUT", 15))
STREAM_PREFLIGHT_TIMEOUT = max(3, int_env("YOUTUBE_STREAM_PREFLIGHT_TIMEOUT", 15))
STREAM_PREFLIGHT_ENABLED = bool_env("YOUTUBE_STREAM_PREFLIGHT", True)
DOWNLOAD_CACHE_MAX_BYTES = max(0, int_env("DOWNLOAD_CACHE_MAX_MB", 2048)) * 1024 * 1024
DOWNLOAD_CACHE_MIN_FREE_BYTES = max(0, int_env("DOWNLOAD_CACHE_MIN_FREE_MB", 512)) * 1024 * 1024
WORKER_FALLBACK_API_ATTEMPTS = min(3, max(1, int_env("WORKER_FALLBACK_API_ATTEMPTS", 3)))
WORKER_FALLBACK_API_RETRY_DELAY_MS = min(
    5000,
    max(0, int_env("WORKER_FALLBACK_API_RETRY_DELAY_MS", 1000)),
)

def build_yt_dlp_args(args: list[str]) -> list[str]:
    return list(args)


async def check_file_size(link):
    async def get_format_info(link):
        args = build_yt_dlp_args(["yt-dlp"])
        args.extend(["-J", link])
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=build_subprocess_env(),
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f'Error:\n{stderr.decode()}')
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    
    formats = info.get('formats', [])
    if not formats:
        print("No formats found.")
        return None
    
    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    if isinstance(cmd, (list, tuple)):
        args = [str(item) for item in cmd]
    else:
        args = shlex.split(str(cmd))
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=build_subprocess_env(),
    )
    out, errorz = await proc.communicate()
    stdout = out.decode("utf-8", errors="replace")
    stderr = errorz.decode("utf-8", errors="replace")
    if stdout and proc.returncode == 0:
        return stdout
    if stderr:
        if "unavailable videos are hidden" in stderr.lower():
            return stdout
        return stderr
    return stdout


async def validate_playable_stream_url(url: str, media_type: str = "audio") -> bool:
    if not url:
        return False

    loop = asyncio.get_running_loop()

    def http_probe():
        session = None
        try:
            session = requests.Session()
            response = session.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Range": "bytes=0-0",
                },
                stream=True,
                timeout=STREAM_HTTP_PROBE_TIMEOUT,
            )
            if response.status_code not in {200, 206}:
                return False
            for chunk in response.iter_content(chunk_size=1):
                return bool(chunk)
            return True
        except Exception:
            return False
        finally:
            if session:
                session.close()

    if not await loop.run_in_executor(None, http_probe):
        return False
    if not STREAM_PREFLIGHT_ENABLED:
        return True

    args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        url,
        "-map",
        "0:a:0",
        "-t",
        "1",
        "-f",
        "null",
        "-",
    ]
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            env=build_subprocess_env(),
        )
        _, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=STREAM_PREFLIGHT_TIMEOUT,
        )
        if proc.returncode == 0:
            return True
        reason = (stderr or b"").decode("utf-8", errors="replace").strip()
        if reason:
            reason = reason.splitlines()[-1][:220]
        logger.warning(
            "YouTube stream preflight failed | media=%s | reason=%s",
            media_type,
            reason or f"ffmpeg exited with {proc.returncode}",
        )
        return False
    except asyncio.TimeoutError:
        if proc and proc.returncode is None:
            proc.kill()
            try:
                await proc.communicate()
            except Exception:
                pass
        logger.warning(
            "YouTube stream preflight timed out | media=%s | timeout=%ss",
            media_type,
            STREAM_PREFLIGHT_TIMEOUT,
        )
        return False
    except FileNotFoundError:
        logger.warning("YouTube stream preflight skipped because ffmpeg is not installed.")
        return True
    except Exception as exc:
        logger.warning(
            "YouTube stream preflight failed | media=%s | reason=%s",
            media_type,
            exc,
        )
        return False


_TITLE_NOISE_RE = re.compile(
    r"\b(official|video|audio|lyrics?|lyrical|full|hd|4k|hq|visualizer|song|songs|"
    r"music|new|latest|feat\.?|ft\.?|prod\.?|by|from|the|"
    r"remix(?:es|ed)?|rmx|re-?mix|dj|lo-?fi|slowed|reverb|sped|speed|up|nightcore|"
    r"8d|cover|mashup|mash-?up|bass|boosted?|version|mix|edit|jhankar|"
    r"unplugged|acoustic|reprise|extended|original|full|status|shorts?)\b",
    re.IGNORECASE,
)


def _title_tokens(title: str) -> set:
    t = re.sub(r"\[[^\]]*\]|\([^\)]*\)", " ", title or "")
    t = _TITLE_NOISE_RE.sub(" ", t.lower())
    return set(re.findall(r"[a-z0-9\u0900-\u097f]+", t))


def _same_title(a: str, b: str, da: int = 0, db: int = 0) -> bool:
    """Do title ek hi gaane ke lagte hain? (brackets / official / lyrics / remix ignore)"""
    ta, tb = _title_tokens(a), _title_tokens(b)
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    shared = ta & tb
    # same length (+-2s) aur kaafi shabd mile => wahi gaana (dusra upload)
    try:
        if da and db and abs(int(da) - int(db)) <= 2 and shared:
            if len(shared) / min(len(ta), len(tb)) >= 0.6:
                return True
    except (TypeError, ValueError):
        pass
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(small) >= 2 and small <= big:
        return True
    return len(ta & tb) / len(ta | tb) >= 0.7


# ---------------------------------------------------------------------------
# NEW SONGS FIRST: autoplay mein naye (recent upload) gaane pehle, har baar alag
# ---------------------------------------------------------------------------
AUTOPLAY_NEW_DAYS = max(1, int_env("AUTOPLAY_NEW_DAYS", 180))     # itne din tak ka upload = "new"
AUTOPLAY_POOL = max(3, int_env("AUTOPLAY_POOL", 12))              # itne candidates mein se sabse naya chuno
AUTOPLAY_POOL_HARD = max(AUTOPLAY_POOL, int_env("AUTOPLAY_POOL_HARD", 40))  # naya na mile to itna tak dhundho

_AGE_RE = re.compile(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?", re.IGNORECASE)
_AGE_UNIT_DAYS = {"second": 0, "minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}


def _age_days(published) -> Union[int, None]:
    """"3 weeks ago" / "Streamed 2 months ago" -> din. Pata na chale to None."""
    m = _AGE_RE.search(str(published or ""))
    if not m:
        return None
    return int(m.group(1)) * _AGE_UNIT_DAYS[m.group(2).lower()]


def _age_bucket(age: Union[int, None]) -> int:
    """0 = bilkul naya, 1 = is saal ka, 2 = upload ka time pata nahi, 3 = purana."""
    if age is None:
        return 2
    if age <= AUTOPLAY_NEW_DAYS:
        return 0
    return 1 if age <= 365 else 3


def _pick_newest(items: list, avoid_channel: Union[str, None] = None):
    """Sabse naya gaana. Barabar hon to wo jo pichhle gaane ke channel se alag ho, phir relevance order.
    Return item (internal '_' keys hata ke) ya None."""
    if not items:
        return None
    best = min(
        enumerate(items),
        key=lambda p: (
            p[1].get("_tier", (0, 0)),            # pakki language / mood match wale pehle
            _age_bucket(p[1].get("_age")),
            1 if (avoid_channel and p[1].get("_ch") == avoid_channel) else 0,
            p[0],
        ),
    )[1]
    return {k: v for k, v in best.items() if not k.startswith("_")}


class YouTubeAPI:
    @staticmethod
    def same_title(a: str, b: str, da: int = 0, db: int = 0) -> bool:
        """Sirf autoplay ke title check ke liye (call.py use karta hai)."""
        return _same_title(a, b, da, db)

    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self.dl_stats = {
            "total_requests": 0,
            "okflix_downloads": 0,
            "cookie_downloads": 0,
            "existing_files": 0
        }
        self._background_cache_tasks = {}
        self._autoplay_channels = {}   # autoplay se chune gaane ka vidid -> channel (agla alag channel se)
        self._learned_seeds = set()    # jin seed gaano se channel-language seekh chuke

    def _has_disallowed_url_chars(self, link: str) -> bool:
        return any(char in link for char in [";", "&", "|", "$", "\n", "\r", "`"])

    def _clean_autoplay_query(self, title: str) -> str:
        if not title:
            return ""
        title = re.sub(r"\[[^\]]*\]|\([^\)]*\)", " ", title)
        title = re.sub(
            r"\b(official|video|audio|lyrics?|lyrical|fullscreen|4k|hd|hq|remix|status|song|songs|music|feat\.?|ft\.?|prod\.?|visualizer)\b",
            " ",
            title,
            flags=re.IGNORECASE,
        )
        title = re.sub(r"\s+", " ", title).strip()
        return title[:100]

    def _duration_to_seconds(self, duration: str) -> int:
        if not duration or str(duration) == "None":
            return 0
        try:
            return int(time_to_seconds(duration))
        except Exception:
            return 0

    def _format_autoplay_candidate(
        self,
        result: dict,
        current_videoid: str,
        max_duration: Union[int, None] = None,
    ) -> Union[dict, None]:
        videoid = result.get("id")
        duration_min = result.get("duration")
        if not videoid or videoid == current_videoid:
            return None
        duration_sec = self._duration_to_seconds(duration_min)
        if not duration_sec or duration_sec > DURATION_LIMIT:
            return None
        if max_duration and duration_sec > max_duration:
            return None
        title = result.get("title")
        thumbnails = result.get("thumbnails") or []
        thumbnail = thumbnails[0]["url"].split("?")[0] if thumbnails else None
        if not title or not thumbnail:
            return None
        return {
            "title": title,
            "duration_min": duration_min,
            "duration_sec": duration_sec,
            "thumb": thumbnail,
            "vidid": videoid,
            "link": result.get("link") or f"{self.base}{videoid}",
        }


    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if not is_safe_media_url(link):
            return False
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]


        result = (await search_videos_with_retry(link, limit=1))[0]
        title = result["title"]
        duration_min = result["duration"]
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        vidid = result["id"]
        if str(duration_min) == "None":
            duration_sec = 0
        else:
            duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]
            
        result = (await search_videos_with_retry(link, limit=1))[0]
        return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]

        result = (await search_videos_with_retry(link, limit=1))[0]
        return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]

        result = (await search_videos_with_retry(link, limit=1))[0]
        return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]

        args = build_yt_dlp_args(["yt-dlp"])
        args.extend(
            [
                "-g",
                "-f",
                "best[height<=?720][width<=?1280]",
                f"{link}",
            ]
        )
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=build_subprocess_env(),
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]
        if self._has_disallowed_url_chars(link):
            return []
        args = build_yt_dlp_args(
            [
                "yt-dlp",
                "-i",
                "--get-id",
                "--flat-playlist",
                "--playlist-end",
                str(limit),
                "--skip-download",
                link,
            ]
        )
        playlist = await shell_cmd(args)
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]

        result = (await search_videos_with_retry(link, limit=1))[0]
        title = result["title"]
        duration_min = result["duration"]
        vidid = result["id"]
        yturl = result["link"]
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def autoplay(
        self,
        videoid: str,
        title: str = "",
        max_duration: Union[int, None] = None,
        is_played=None,
        ctx: Union[dict, None] = None,
        lang: Union[str, None] = None,
        mood: Union[str, None] = None,
        channel: Union[str, None] = None,
        extra_text: Union[str, None] = None,
    ) -> Union[dict, None]:
        """Jo gaana abhi baja uske jaisa DOOSRA gaana chuno (same gaana nahi).

        is_played: async (videoid, title, duration_sec) -> bool
                   True ho to wo gaana pehle baj chuka hai, skip hoga.
        ctx      : autoplay_context_db.get_context(chat_id) -- isme seed ki "lang" aur "mood" hoti hain.
                   Dene par seed ki language (Bhojpuri/Hindi/...) aur mood ka gaana hi aata hai.
        lang/mood: ctx ke bina seedha de sakte ho. Kuch na do to title (+ channel) se khud pehchanta hai.
        """
        seed = {"v": str(videoid or ""), "t": title or "", "d": 0}

        def is_seed_song(cid, ctitle, cdur) -> bool:
            # Safety: DB fail ho tab bhi jo gaana abhi baja wo dobara na aaye
            if cid and cid == videoid:
                return True
            if not title:
                return False
            return _same_song(seed, {"v": str(cid or ""), "t": ctitle or "", "d": cdur})

        async def search_page(text: str, limit: int = 20) -> list:
            try:
                res = VideosSearch(text, limit=limit)
                return (await res.next()).get("result", []) or []
            except Exception as err:
                logger.warning("Autoplay search failed for %s: %s", text, err)
                return []

        first_cache: dict = {}

        async def get_first() -> list:
            if "r" not in first_cache:
                q = self._clean_autoplay_query(title)
                first_cache["r"] = await search_page(q) if q else []
            return first_cache["r"]

        def seed_channel_from(first: list):
            for r in first:
                if r.get("id") == videoid and isinstance(r.get("channel"), dict):
                    return r["channel"].get("name")
            for r in first[:3]:
                if isinstance(r.get("channel"), dict) and r["channel"].get("name"):
                    return r["channel"]["name"]
            return None

        # --- seed ka profile: language + mood (isi ke hisaab se aage ke gaane) ---
        c = ctx or {}
        seed_lang = normalize_lang(lang) if lang else (c.get("lang") or None)
        seed_mood = mood or c.get("mood") or None
        if _LANG_LOCK:
            await warm_channel_langs()
            ch0 = channel
            lang_given = bool(seed_lang)
            if not seed_lang:
                if not ch0:
                    ch0 = seed_channel_from(await get_first())
                seed_lang = detect_language(title, ch0, extra_text)
                if not seed_lang and llm_enabled():
                    # nishaan nahi mile -> Claude se pucho (Bhojpuri / Hindi / English ...)
                    info = await classify_song(title, ch0, extra_text)
                    seed_lang = normalize_lang((info or {}).get("language"))
                    if info and not seed_mood:
                        seed_mood = info.get("mood")
                seed_lang = seed_lang or "hindi"      # kuch bhi pata na chale to Hindi
            # pakki non-Hindi seed -> uska channel yaad (agli baar us channel ke gaane pehchane jaayenge)
            if seed_lang and seed_lang != "hindi" and str(videoid) not in self._learned_seeds:
                if ch0 is None:
                    ch0 = channel or seed_channel_from(await get_first())
                self._learned_seeds.add(str(videoid))      # ek gaane se ek hi baar seekho
                if len(self._learned_seeds) > 2000:
                    self._learned_seeds.clear()
                try:
                    await learn_channel_language(ch0, seed_lang)
                except Exception:
                    pass
            if not seed_mood:
                seed_mood = dominant_mood(title) or dominant_mood(title, soft=True)
        logger.info("Autoplay seed profile | %r | lang=%s | mood=%s", title, seed_lang, seed_mood)

        def lq(text: str) -> str:
            """Query mein language ka naam (Bhojpuri songs -> Bhojpuri hi results)."""
            if seed_lang and seed_lang not in text.lower():
                return f"{seed_lang} {text}"
            return text

        async def candidate_stream():
            # 1) YouTube ke related gaane (agar library support kare)
            if videoid and Recommendations is not None:
                try:
                    recs = await Recommendations.get(videoid, timeout=5) or []
                except Exception as err:
                    logger.warning("Autoplay recommendations failed for %s: %s", videoid, err)
                    recs = []
                for r in recs:
                    yield r

            # 2) Related nahi mila: gaane ke naam se search karne par wahi gaana
            #    (alag upload) pehle aata hai. Isliye "similar" / channel ke
            #    gaane bhi dhoondo, taaki doosre gaane mile.
            query = self._clean_autoplay_query(title)
            if not query:
                return
            first = await get_first()
            channel_name = seed_channel_from(first)

            for r in first:
                yield r
            year = time.gmtime().tm_year
            extra = [
                lq(f"{query} similar songs"),
                lq(f"songs like {query}"),
            ]
            if seed_mood:
                extra.append(lq(f"{seed_mood} songs"))
                extra.append(lq(f"new {seed_mood} songs {year}"))
            extra += [
                lq(f"new songs like {query}"),
                lq(f"latest songs {year}"),
            ]
            if channel_name:
                extra.append(f"{channel_name} new songs")
            for text in extra:
                for r in await search_page(text):
                    yield r

        # Pool banao (naye wale milne tak), phir sabse NAYA aur pehle se ALAG gaana chuno
        seed_channel = self._autoplay_channels.get(str(videoid or ""))
        pool: list = []
        unknown_pool: list = []
        picked_titles: list = []
        details_budget = 5            # candidate ki details alag se lani pade to itni hi baar
        seen = set()
        stream = candidate_stream()
        try:
            async for candidate in stream:
                candidate_id = candidate.get("id")
                if not candidate_id or candidate_id in seen:
                    continue
                seen.add(candidate_id)

                channel = candidate.get("channel")
                ch_name = channel.get("name") if isinstance(channel, dict) else None
                age = _age_days(candidate.get("publishedTime"))

                formatted = self._format_autoplay_candidate(candidate, videoid, max_duration)
                if not formatted:
                    if candidate_id == videoid or details_budget <= 0:
                        continue
                    details_budget -= 1
                    try:
                        (
                            resolved_title,
                            duration_min,
                            duration_sec,
                            thumbnail,
                            resolved_videoid,
                        ) = await self.details(candidate_id, videoid=True)
                    except Exception:
                        continue
                    if (
                        not resolved_videoid
                        or resolved_videoid == videoid
                        or not duration_sec
                        or duration_sec > DURATION_LIMIT
                        or (max_duration and duration_sec > max_duration)
                    ):
                        continue
                    formatted = {
                        "title": resolved_title,
                        "duration_min": duration_min,
                        "duration_sec": duration_sec,
                        "thumb": thumbnail,
                        "vidid": resolved_videoid,
                        "link": f"{self.base}{resolved_videoid}",
                    }

                if is_seed_song(formatted["vidid"], formatted["title"], formatted["duration_sec"]):
                    logger.info("Autoplay skip (same song): %s", formatted["title"])
                    continue
                if is_played and await is_played(
                    formatted["vidid"], formatted["title"], formatted["duration_sec"]
                ):
                    logger.info("Autoplay skip (already played): %s", formatted["title"])
                    continue
                # LANGUAGE LOCK: Bhojpuri seed par sirf Bhojpuri (Hindi/Marathi/English... kabhi nahi)
                lm = language_match(seed_lang, formatted["title"], ch_name) if seed_lang else 1
                if lm < 0:
                    logger.info("Autoplay skip (language %s nahi): %s", seed_lang, formatted["title"])
                    continue
                # MOOD: doosre mood ka gaana nahi (sad -> sad, romantic -> romantic)
                if seed_mood and not mood_ok(seed_mood, formatted["title"], ch_name):
                    logger.info("Autoplay skip (mood %s nahi): %s", seed_mood, formatted["title"])
                    continue
                # pool ke andar bhi ek gaana ek hi baar (alag upload / lyrics version nahi)
                if any(
                    _same_title(formatted["title"], t, formatted["duration_sec"], d)
                    for t, d in picked_titles
                ):
                    continue
                picked_titles.append((formatted["title"], formatted["duration_sec"]))

                formatted["_age"] = age
                formatted["_ch"] = ch_name
                formatted["_tier"] = (
                    0 if (seed_lang and lm == 1) else 1,
                    0 if (seed_mood and mood_hit(seed_mood, formatted["title"], ch_name)) else 1,
                )
                # Language pakki nahi pehchani gayi (Hindi/English Roman title ho sakta hai):
                # non-Hindi seed par bina verify ke nahi -> alag rakho, Claude se verify hoga
                if seed_lang and lm == 0 and _STRICT_LANG and seed_lang != "hindi":
                    unknown_pool.append(formatted)
                    continue
                pool.append(formatted)

                has_new = any(_age_bucket(i.get("_age")) == 0 for i in pool)
                if (len(pool) >= AUTOPLAY_POOL and has_new) or len(pool) >= AUTOPLAY_POOL_HARD:
                    break
        finally:
            try:
                await stream.aclose()
            except Exception:
                pass

        # anjaan-language candidates: Claude verify kare ki sach mein seed ki language ke hain
        if unknown_pool and len(pool) < AUTOPLAY_POOL:
            okset = await verify_language(
                seed_lang,
                [{"title": u["title"], "channel": {"name": u.get("_ch")}} for u in unknown_pool[:15]],
            )
            for i in sorted(okset or []):
                u = unknown_pool[i]
                u["_tier"] = (0, u["_tier"][1])
                pool.append(u)
                try:
                    await learn_channel_language(u.get("_ch"), seed_lang)
                except Exception:
                    pass
            if not okset:
                logger.info(
                    "Autoplay: %d anjaan-language gaane reject (%s lock; verify nahi hua)",
                    len(unknown_pool), seed_lang,
                )

        best_ch = None
        if pool:
            # _ch alag rakho (pick ke baad channel yaad rakhna hai)
            chosen = _pick_newest(pool, seed_channel)
            best_ch = next((i.get("_ch") for i in pool if i["vidid"] == chosen["vidid"]), None)
            if best_ch:
                if len(self._autoplay_channels) > 500:
                    self._autoplay_channels.clear()
                self._autoplay_channels[chosen["vidid"]] = best_ch
            logger.info(
                "Autoplay pick (new-first, lang=%s, mood=%s): %s | pool=%d | age_days=%s",
                seed_lang, seed_mood, chosen["title"], len(pool),
                next((i.get("_age") for i in pool if i["vidid"] == chosen["vidid"]), None),
            )
            return chosen
        return None

    async def autoplay_context(
        self,
        ctx: dict,
        current_videoid: str,
        max_duration: Union[int, None] = None,
        is_played=None,
    ) -> tuple:
        """User ke search (artist / topic) ke andar hi next gaana chuno.

        ctx       : autoplay_context_db.get_context() ka dict
        is_played : async (videoid, title, duration_sec) -> bool
        Return    : (recommendation | None, kind)
                    kind 'song' = ye artist nahi, normal autoplay chalao.
        """
        kind = ctx.get("kind") or "song"
        core = ctx.get("core") or ""
        aliases = ctx.get("aliases") or []
        base_search = ctx.get("search") or ctx.get("query") or ""
        if kind == "song" or not base_search:
            return None, "song"

        async def fetch(text: str) -> list:
            out = []
            try:
                search = VideosSearch(text, limit=20)
                for _ in range(2):
                    page = (await search.next()).get("result", [])
                    if not page:
                        break
                    out.extend(page)
            except Exception as err:
                logger.warning("Autoplay context search failed for %s: %s", text, err)
            return out

        first = await fetch(base_search)

        # Unknown naam: artist hai ya single gaane ka naam? (pehli baar verify)
        if kind == "pending":
            durs = [self._duration_to_seconds(r.get("duration")) for r in first]
            if looks_like_artist(core, first, durs):
                kind = "artist"
                try:
                    await learn_artist(core)  # agli baar seedha pehchan lega
                except Exception as err:
                    logger.warning("learn_artist failed for %s: %s", core, err)
            else:
                return None, "song"

        # Language lock (topic mode: "bhojpuri songs") + mood ("sad songs" / artist ke saath likha mood)
        ctx_lang = ctx.get("lang") if (_LANG_LOCK and kind != "artist") else None
        ctx_mood = ctx.get("mood") if _LANG_LOCK else None

        # NAYE gaane pehle: "new / latest" queries sabse pehle, har query mein sabse naya upload
        if kind == "artist":
            queries = [
                f"{core} new songs",
                f"{core} latest song",
                base_search,
                f"{core} superhit songs",
                f"{core} hit songs",
                f"{core} jukebox",
            ]
        else:
            queries = [f"{base_search} new", base_search, f"{base_search} best", f"{base_search} hits"]

        seen = set()
        for text in queries:
            results = first if text == base_search else await fetch(text)
            valid: list = []
            unk: list = []
            for r in results:
                vid = r.get("id")
                if not vid or vid in seen:
                    continue
                seen.add(vid)

                channel = r.get("channel")
                ch_name = channel.get("name") if isinstance(channel, dict) else None
                title = r.get("title")

                if kind == "artist":
                    if not matches_core(core, title, ch_name, aliases):
                        continue  # doosre artist ka gaana, skip
                elif not matches_topic(ctx, title, ch_name):
                    continue  # topic se bahar (ya namesake artist), skip

                lm = language_match(ctx_lang, title, ch_name) if ctx_lang else 1
                if lm < 0:
                    continue  # doosri language ka gaana
                needs_verify = bool(ctx_lang and lm == 0 and _STRICT_LANG and ctx_lang != "hindi")
                if ctx_mood and not mood_ok(ctx_mood, title, ch_name):
                    continue  # doosre mood ka gaana

                formatted = self._format_autoplay_candidate(r, current_videoid, max_duration)
                if not formatted:
                    continue
                if is_played and await is_played(
                    formatted["vidid"], formatted["title"], formatted["duration_sec"]
                ):
                    logger.info("Autoplay skip (already played): %s", formatted["title"])
                    continue
                if any(
                    _same_title(formatted["title"], v["title"], formatted["duration_sec"], v["duration_sec"])
                    for v in valid
                ):
                    continue
                formatted["_age"] = _age_days(r.get("publishedTime"))
                formatted["_ch"] = ch_name
                formatted["_tier"] = (
                    0 if (ctx_lang and lm == 1) else 1,
                    0 if (ctx_mood and mood_hit(ctx_mood, title, ch_name)) else 1,
                )
                if needs_verify:
                    unk.append(formatted)
                    continue
                valid.append(formatted)

            if unk and not valid:   # pakki language wala nahi mila -> anjaan wale Claude se verify
                okset = await verify_language(
                    ctx_lang, [{"title": u["title"], "channel": {"name": u.get("_ch")}} for u in unk[:15]]
                )
                for i in sorted(okset or []):
                    unk[i]["_tier"] = (0, unk[i]["_tier"][1])
                    valid.append(unk[i])

            chosen = _pick_newest(valid, self._autoplay_channels.get(str(current_videoid or "")))
            if chosen:
                ch_pick = next((v.get("_ch") for v in valid if v["vidid"] == chosen["vidid"]), None)
                if ch_pick:
                    if len(self._autoplay_channels) > 500:
                        self._autoplay_channels.clear()
                    self._autoplay_channels[chosen["vidid"]] = ch_pick
                logger.info("Autoplay pick (%s, new-first): %s", kind, chosen["title"])
                return chosen, kind
        return None, kind

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]
        ytdl_opts = {"quiet": True}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if not "dash" in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]

        try:
            results = []
            search_results = await search_videos_with_retry(link, limit=10)

            # Filter videos longer than 1 hour
            for result in search_results:
                duration_str = result.get("duration", "0:00")
                try:
                    parts = duration_str.split(":")
                    duration_secs = 0
                    if len(parts) == 3:
                        duration_secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    elif len(parts) == 2:
                        duration_secs = int(parts[0]) * 60 + int(parts[1])

                    if duration_secs <= 3600:
                        results.append(result)
                except (ValueError, IndexError):
                    continue

            if not results or query_type >= len(results):
                raise ValueError("No suitable videos found within duration limit")

            selected = results[query_type]
            return (
                selected["title"],
                selected["duration"],
                selected["thumbnails"][0]["url"].split("?")[0],
                selected["id"]
            )

        except Exception as e:
            LOGGER(__name__).error(f"Error in slider: {str(e)}")
            raise ValueError("Failed to fetch video details")

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
        stream: Union[bool, str] = True,
    ) -> str:
        if videoid:
            vid_id = link
            link = self.base + link
        log_title = re.sub(r"\s+", " ", str(title or "")).strip()
        log_title = log_title[:80] if log_title else "-"
        loop = asyncio.get_running_loop()

        def create_session():
            session = requests.Session()
            retries = Retry(total=3, backoff_factor=0.1)
            session.mount('http://', HTTPAdapter(max_retries=retries))
            session.mount('https://', HTTPAdapter(max_retries=retries))
            return session

        def cached_media_ready(filepath):
            try:
                return (
                    os.path.exists(filepath)
                    and os.path.getsize(filepath) >= MIN_CACHED_MEDIA_BYTES
                )
            except Exception:
                return False

        def partial_path(filepath):
            return f"{filepath}.downloading"

        def enforce_download_cache_budget(extra_bytes=0):
            if not DOWNLOAD_CACHE_MAX_BYTES and not DOWNLOAD_CACHE_MIN_FREE_BYTES:
                return True

            os.makedirs("downloads", exist_ok=True)
            protected = {
                os.path.abspath(str(path))
                for path in autoclean
                if isinstance(path, str) and path
            }
            try:
                from nexo.misc import db

                for queue in (db or {}).values():
                    for item in queue or []:
                        if not isinstance(item, dict):
                            continue
                        queued_file = str(item.get("file") or "")
                        if queued_file:
                            protected.add(os.path.abspath(queued_file))

                        videoid = str(item.get("vidid") or "").strip()
                        if not videoid or videoid in {"telegram", "soundcloud"}:
                            continue
                        if not queued_file.startswith("vid_"):
                            continue

                        streamtype = str(item.get("streamtype") or "audio")
                        ext = "mp4" if streamtype == "video" else "mp3"
                        protected.add(
                            os.path.abspath(os.path.join("downloads", f"{videoid}.{ext}"))
                        )
            except Exception:
                pass
            protected.update(
                os.path.abspath(path)
                for path, task in self._background_cache_tasks.items()
                if task and not task.done()
            )

            files = []
            total_size = 0
            try:
                entries = list(os.scandir("downloads"))
            except OSError:
                return True

            for entry in entries:
                try:
                    if not entry.is_file():
                        continue
                    name = entry.name.lower()
                    if name.endswith(".downloading") or not name.endswith(DOWNLOAD_CACHE_EXTENSIONS):
                        continue
                    stat = entry.stat()
                except OSError:
                    continue
                total_size += stat.st_size
                files.append((stat.st_mtime, stat.st_size, entry.path))

            try:
                free_bytes = shutil.disk_usage("downloads").free
            except OSError:
                free_bytes = DOWNLOAD_CACHE_MIN_FREE_BYTES

            needs_cleanup = (
                DOWNLOAD_CACHE_MAX_BYTES
                and total_size + int(extra_bytes or 0) > DOWNLOAD_CACHE_MAX_BYTES
            ) or (
                DOWNLOAD_CACHE_MIN_FREE_BYTES
                and free_bytes - int(extra_bytes or 0) < DOWNLOAD_CACHE_MIN_FREE_BYTES
            )
            if not needs_cleanup:
                return True

            removed = 0
            removed_bytes = 0
            for _, size, path in sorted(files):
                if os.path.abspath(path) in protected:
                    continue
                try:
                    os.remove(path)
                except OSError:
                    continue
                total_size -= size
                free_bytes += size
                removed += 1
                removed_bytes += size
                if (
                    (not DOWNLOAD_CACHE_MAX_BYTES or total_size <= DOWNLOAD_CACHE_MAX_BYTES)
                    and (
                        not DOWNLOAD_CACHE_MIN_FREE_BYTES
                        or free_bytes >= DOWNLOAD_CACHE_MIN_FREE_BYTES
                    )
                ):
                    break

            if removed:
                logger.info(
                    "YouTube cache budget cleanup removed %s file(s) (%s bytes).",
                    removed,
                    removed_bytes,
                )

            return (
                (not DOWNLOAD_CACHE_MAX_BYTES or total_size <= DOWNLOAD_CACHE_MAX_BYTES)
                and (
                    not DOWNLOAD_CACHE_MIN_FREE_BYTES
                    or free_bytes >= DOWNLOAD_CACHE_MIN_FREE_BYTES
                )
            )

        async def download_with_ytdlp(url, filepath, headers=None, max_retries=3):
            default_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.youtube.com/",
            }
            merged_headers = default_headers.copy()
            if headers:
                merged_headers.update(headers)
            temp_filepath = partial_path(filepath)

            # yt-dlp handles direct media URLs, reuse the running loop to avoid blocking the event loop.
            def run_download():
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "noprogress": True,
                    "outtmpl": temp_filepath,
                    "force_overwrites": True,
                    "nopart": True,
                    "retries": max_retries,
                    "http_headers": merged_headers,
                    "concurrent_fragment_downloads": 8,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

            try:
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                await loop.run_in_executor(None, run_download)
                if os.path.exists(temp_filepath):
                    os.replace(temp_filepath, filepath)
                    return filepath
            except Exception as e:
                logger.error(f"yt-dlp download failed: {str(e)}")
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            return None

        async def download_with_requests_fallback(url, filepath, headers=None):
            session = None
            temp_filepath = partial_path(filepath)
            try:
                session = create_session()
                
                # Use headers for authentication (including x-api-key)
                response = session.get(url, headers=headers, stream=True, timeout=60)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                chunk_size = 1024 * 1024 
                
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                with open(temp_filepath, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            file.write(chunk)
                            downloaded += len(chunk)
                os.replace(temp_filepath, filepath)
                return filepath
                
            except Exception as e:
                logger.error(f"Requests download failed: {str(e)}")
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                return None
            finally:
                if session:
                    session.close()

        async def download_from_source(url, filepath, headers=None):
            result = await download_with_ytdlp(url, filepath, headers)
            if result:
                return result
            return await download_with_requests_fallback(url, filepath, headers)

        async def validate_stream_source(url):
            media_type = "video" if video else "audio"
            return await validate_playable_stream_url(url, media_type)

        def schedule_background_cache(url, filepath, headers=None):
            if not url or not filepath or cached_media_ready(filepath):
                return
            existing = self._background_cache_tasks.get(filepath)
            if existing and not existing.done():
                return
            if not enforce_download_cache_budget():
                logger.warning(
                    "Skipping background cache because download cache budget is exhausted | file=%s",
                    os.path.basename(filepath),
                )
                return

            async def cache_job():
                try:
                    await download_from_source(url, filepath, headers)
                    enforce_download_cache_budget()
                except Exception as exc:
                    logger.warning(f"Background cache failed for {os.path.basename(filepath)}: {exc}")
                finally:
                    self._background_cache_tasks.pop(filepath, None)

            self._background_cache_tasks[filepath] = asyncio.create_task(cache_job())

        async def wait_for_background_cache(filepath):
            task = self._background_cache_tasks.get(filepath)
            if not task:
                return None
            try:
                await task
            except Exception:
                pass
            if cached_media_ready(filepath):
                return filepath
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            return None

        def first_media_url(value, media_format=None):
            if isinstance(value, str):
                value = value.strip()
                return value or None
            if isinstance(value, dict):
                preferred_keys = (
                    media_format,
                    "url",
                    "link",
                    "downloadUrl",
                    "download_url",
                    "directLink",
                    "streamLink",
                    "audio_url",
                    "video_url",
                )
                for key in preferred_keys:
                    if not key:
                        continue
                    url = first_media_url(value.get(key), media_format)
                    if url:
                        return url
                for item in value.values():
                    url = first_media_url(item, media_format)
                    if url:
                        return url
            if isinstance(value, (list, tuple)):
                for item in value:
                    url = first_media_url(item, media_format)
                    if url:
                        return url
            return None

        def select_media_links(data, media_format, prefer_stream=False):
            stream_keys = (
                "streamingUrl",
                "streaming_url",
                "playbackUrl",
                "playback_url",
                "streamLink",
                "streamUrl",
                "stream_url",
                "audioUrl",
                "audio_url",
            )
            download_keys = (
                "directLink",
                "directUrl",
                "downloadLink",
                "downloadUrl",
                "download_url",
                "downloads",
            )
            play_keys = (
                stream_keys + download_keys
                if prefer_stream
                else download_keys + stream_keys
            )
            cache_keys = download_keys + stream_keys

            def pick(keys):
                for key in keys:
                    url = first_media_url(data.get(key), media_format)
                    if url:
                        return key, url
                return None, None

            play_key, play_url = pick(play_keys)
            cache_key, cache_url = pick(cache_keys)
            return {
                "play_key": play_key,
                "play_url": play_url,
                "cache_key": cache_key or play_key,
                "cache_url": cache_url or play_url,
            }

        def mark_source(vid_id, media_type, source, ok=True):
            state = "OK" if ok else "FAILED"
            pretty_sources = {
                "LOCAL CACHE": "local cache",
                "WORKER PRIMARY": "worker primary",
                "WORKER FALLBACK": "worker fallback",
                "XBIT FALLBACK": "xBit fallback",
                "YT-DLP FALLBACK": "yt-dlp fallback",
                "WORKER PRIMARY + XBIT FALLBACK": "worker primary + xBit fallback",
            }
            pretty_media = {"audio": "audio", "video": "video"}.get(media_type, media_type)
            pretty_state = "ok" if ok else "failed"
            pretty_source = pretty_sources.get(source, source)
            text = f"{pretty_source} {pretty_state} ({pretty_media})"
            if not ok:
                text = f"{pretty_source} {pretty_state} ({pretty_media}) | id: {vid_id}"
            set_youtube_source_status(vid_id, text)
            logger.info(
                "YouTube source %s | source=%s | media=%s | video_id=%s | title=%s",
                state.lower(),
                source.lower().replace(" ", "_"),
                media_type,
                vid_id,
                log_title,
            )

        def log_primary_api_issue(media_type, vid_id, message):
            if WORKER_FALLBACK_API_URL and WORKER_FALLBACK_API_KEY:
                logger.info(
                    "xBit fallback API failed | media=%s | video_id=%s | title=%s | reason=%s | next=none",
                    media_type,
                    vid_id,
                    log_title,
                    message,
                )
                return
            logger.warning(
                "xBit fallback API failed | media=%s | video_id=%s | title=%s | reason=%s | next=none",
                media_type,
                vid_id,
                log_title,
                message,
            )

        def schedule_worker_background_cache(media, filepath, media_type, vid_id):
            cache_url = (media or {}).get("cache_url") or (media or {}).get("play_url")
            if not cache_url:
                return
            logger.info(
                "YouTube background cache scheduled | source=worker_primary | media=%s | video_id=%s | title=%s | play_link=%s | cache_link=%s | same_url=%s",
                media_type,
                vid_id,
                log_title,
                (media or {}).get("play_key") or "-",
                (media or {}).get("cache_key") or "-",
                cache_url == (media or {}).get("play_url"),
            )
            schedule_background_cache(cache_url, filepath)

        def fetch_worker_fallback_links_sync(vid_id, media_format):
            if not WORKER_FALLBACK_API_URL or not WORKER_FALLBACK_API_KEY:
                logger.warning("Worker fallback API URL/key not set. Skipping worker fallback.")
                return None

            session = None
            try:
                session = create_session()
                api_url = f"{WORKER_FALLBACK_API_URL.rstrip('/')}/api"
                payload = {
                    "key": WORKER_FALLBACK_API_KEY,
                    "url": f"https://youtube.com/watch?v={vid_id}",
                    "format": media_format,
                }

                response = None
                for attempt in range(WORKER_FALLBACK_API_ATTEMPTS):
                    response = session.get(api_url, params=payload, timeout=25)
                    if response.status_code not in {429, 500, 502, 503, 504}:
                        break
                    if attempt + 1 >= WORKER_FALLBACK_API_ATTEMPTS:
                        response.raise_for_status()
                    logger.warning(
                        "Worker fallback API transient response | format=%s | video_id=%s | "
                        "status=%s | retry=%s/%s",
                        media_format,
                        vid_id,
                        response.status_code,
                        attempt + 1,
                        WORKER_FALLBACK_API_ATTEMPTS,
                    )
                    response.close()
                    time.sleep((WORKER_FALLBACK_API_RETRY_DELAY_MS * (attempt + 1)) / 1000)

                response.raise_for_status()
                data = response.json()

                if not data.get("success"):
                    logger.error(
                        "Worker fallback API failed | format=%s | video_id=%s | title=%s | reason=%s",
                        media_format,
                        vid_id,
                        log_title,
                        data.get("error", "Unknown error"),
                    )
                    return None

                media = select_media_links(data, media_format, prefer_stream=bool(stream))
                if not media.get("play_url"):
                    logger.error(
                        "Worker fallback API failed | format=%s | video_id=%s | title=%s | reason=no media url",
                        media_format,
                        vid_id,
                        log_title,
                    )
                    return None
                logger.info(
                    "Worker fallback API selected | format=%s | video_id=%s | title=%s | play_link=%s | cache_link=%s",
                    media_format,
                    vid_id,
                    log_title,
                    media.get("play_key") or "-",
                    media.get("cache_key") or "-",
                )
                return media
            except Exception as e:
                logger.error(
                    "Worker fallback API failed | format=%s | video_id=%s | title=%s | reason=%s",
                    media_format,
                    vid_id,
                    log_title,
                    str(e),
                )
                return None
            finally:
                if session:
                    session.close()

        async def get_worker_fallback_links(vid_id, media_format):
            return await loop.run_in_executor(
                None, fetch_worker_fallback_links_sync, vid_id, media_format
            )

        async def ytdlp_local_fallback(vid_id, media_type, filepath):
            """Last resort: resolve/download directly with yt-dlp when worker and xBit both fail."""
            watch_url = f"https://www.youtube.com/watch?v={vid_id}"
            fmt = (
                "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best"
                if media_type == "video"
                else "bestaudio[ext=m4a]/bestaudio/best"
            )

            def resolve_direct():
                opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                    "skip_download": True,
                    "geo_bypass": True,
                    "nocheckcertificate": True,
                    "socket_timeout": 20,
                    "format": fmt,
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(watch_url, download=False)
                if not info:
                    return None
                # merged video+audio formats have no single direct URL
                if info.get("requested_formats") and media_type == "video":
                    return None
                url = info.get("url")
                if not url:
                    return None
                return url, dict(info.get("http_headers") or {})

            try:
                resolved = await loop.run_in_executor(None, resolve_direct)
            except Exception as exc:
                logger.warning(f"yt-dlp fallback resolve failed | video_id={vid_id} | reason={exc}")
                resolved = None

            if resolved:
                direct_url, direct_headers = resolved
                if stream and await validate_stream_source(direct_url):
                    mark_source(vid_id, media_type, "YT-DLP FALLBACK")
                    schedule_background_cache(direct_url, filepath, direct_headers)
                    return direct_url, False
                result = await download_from_source(direct_url, filepath, direct_headers)
                if result:
                    mark_source(vid_id, media_type, "YT-DLP FALLBACK")
                    return result, True

            # direct URL not usable (or merged format) -> let yt-dlp download the file itself
            def full_download():
                opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                    "geo_bypass": True,
                    "nocheckcertificate": True,
                    "socket_timeout": 20,
                    "retries": 3,
                    "format": fmt,
                    "outtmpl": partial_path(filepath).replace(".downloading", ".%(ext)s.downloading"),
                    "force_overwrites": True,
                    "nopart": True,
                    "prefer_ffmpeg": True,
                }
                if media_type == "video":
                    opts["merge_output_format"] = "mp4"
                else:
                    opts["postprocessors"] = [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ]
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([watch_url])

            try:
                if not enforce_download_cache_budget():
                    logger.warning("yt-dlp fallback: download cache budget exhausted.")
                await loop.run_in_executor(None, full_download)
            except Exception as exc:
                logger.error(f"yt-dlp fallback download failed | video_id={vid_id} | reason={exc}")

            # collect whatever yt-dlp produced for this id
            base = os.path.splitext(filepath)[0]
            wanted_ext = ".mp4" if media_type == "video" else ".mp3"
            produced = None
            try:
                for name in os.listdir("downloads"):
                    full = os.path.join("downloads", name)
                    if not name.startswith(f"{vid_id}."):
                        continue
                    if name.endswith(".downloading") or name == os.path.basename(filepath):
                        continue
                    if name.lower().endswith(wanted_ext):
                        produced = full
                        break
            except OSError:
                pass
            if produced and os.path.exists(produced) and produced != filepath:
                try:
                    os.replace(produced, filepath)
                except OSError:
                    filepath = produced
            for name in os.listdir("downloads") if os.path.isdir("downloads") else []:
                if name.startswith(f"{vid_id}.") and name.endswith(".downloading"):
                    try:
                        os.remove(os.path.join("downloads", name))
                    except OSError:
                        pass
            if cached_media_ready(filepath):
                mark_source(vid_id, media_type, "YT-DLP FALLBACK")
                return filepath, True
            return None

        async def audio_dl(vid_id):
            filepath = os.path.join("downloads", f"{vid_id}.mp3")
            if cached_media_ready(filepath):
                mark_source(vid_id, "audio", "LOCAL CACHE")
                return filepath, True
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            if not stream:
                cached = await wait_for_background_cache(filepath)
                if cached:
                    return cached, True

            headers = {
                "x-api-key": f"{YT_API_KEY}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            worker_audio = await get_worker_fallback_links(vid_id, "mp3")
            if worker_audio:
                worker_audio_url = worker_audio.get("play_url")
                worker_audio_cache_url = worker_audio.get("cache_url") or worker_audio_url
                if stream and await validate_stream_source(worker_audio_url):
                    mark_source(vid_id, "audio", "WORKER PRIMARY")
                    schedule_worker_background_cache(worker_audio, filepath, "audio", vid_id)
                    return worker_audio_url, False
                result = await download_from_source(worker_audio_cache_url, filepath)
                if result:
                    mark_source(vid_id, "audio", "WORKER PRIMARY")
                    return result, True
                logger.warning("Worker audio URL download failed, trying xBit fallback.")

            xbit_audio_url = None
            if YT_API_KEY and YTPROXY:
                session = None
                try:
                    session = create_session()
                    get_audio = session.get(f"{YTPROXY}/info/{vid_id}", headers=headers, timeout=60)
                    song_data = get_audio.json()
                    status = song_data.get('status')

                    if status == 'success':
                        xbit_audio_url = song_data.get('audio_url')
                    elif status == 'error':
                        log_primary_api_issue(
                            "audio",
                            vid_id,
                            song_data.get('message', 'Unknown error from API.'),
                        )
                    else:
                        log_primary_api_issue(
                            "audio",
                            vid_id,
                            "unexpected response while fetching audio",
                        )
                except requests.exceptions.RequestException as e:
                    log_primary_api_issue("audio", vid_id, f"network error: {str(e)}")
                except json.JSONDecodeError as e:
                    log_primary_api_issue("audio", vid_id, f"invalid response: {str(e)}")
                except Exception as e:
                    log_primary_api_issue("audio", vid_id, str(e))
                finally:
                    if session:
                        session.close()
            else:
                logger.info("xBit fallback not configured for audio.")

            if xbit_audio_url:
                if stream and await validate_stream_source(xbit_audio_url):
                    mark_source(vid_id, "audio", "XBIT FALLBACK")
                    schedule_background_cache(xbit_audio_url, filepath, headers)
                    return xbit_audio_url, False
                result = await download_from_source(xbit_audio_url, filepath, headers)
                if result:
                    mark_source(vid_id, "audio", "XBIT FALLBACK")
                    return result, True

            logger.warning("Worker/xBit failed for audio, trying local yt-dlp fallback.")
            local = await ytdlp_local_fallback(vid_id, "audio", filepath)
            if local:
                return local
            mark_source(vid_id, "audio", "WORKER PRIMARY + XBIT FALLBACK", ok=False)
            logger.error(
                "YouTube source failed | sources=worker_primary,xbit_fallback | media=audio | video_id=%s | title=%s",
                vid_id,
                log_title,
            )
            return None, True
        
        
        async def video_dl(vid_id):
            filepath = os.path.join("downloads", f"{vid_id}.mp4")
            if cached_media_ready(filepath):
                mark_source(vid_id, "video", "LOCAL CACHE")
                return filepath, True
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            if not stream:
                cached = await wait_for_background_cache(filepath)
                if cached:
                    return cached, True

            headers = {
                "x-api-key": f"{YT_API_KEY}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            worker_video = await get_worker_fallback_links(vid_id, "mp4")
            if worker_video:
                worker_video_url = worker_video.get("play_url")
                worker_video_cache_url = worker_video.get("cache_url") or worker_video_url
                if stream and await validate_stream_source(worker_video_url):
                    mark_source(vid_id, "video", "WORKER PRIMARY")
                    schedule_worker_background_cache(worker_video, filepath, "video", vid_id)
                    return worker_video_url, False
                result = await download_from_source(worker_video_cache_url, filepath)
                if result:
                    mark_source(vid_id, "video", "WORKER PRIMARY")
                    return result, True
                logger.warning("Worker video URL download failed, trying xBit fallback.")

            xbit_video_url = None
            if YT_API_KEY and YTPROXY:
                session = None
                try:
                    session = create_session()
                    get_video = session.get(f"{YTPROXY}/info/{vid_id}", headers=headers, timeout=60)
                    video_data = get_video.json()
                    status = video_data.get('status')

                    if status == 'success':
                        xbit_video_url = video_data.get('video_url')
                    elif status == 'error':
                        log_primary_api_issue(
                            "video",
                            vid_id,
                            video_data.get('message', 'Unknown error from API.'),
                        )
                    else:
                        log_primary_api_issue(
                            "video",
                            vid_id,
                            "unexpected response while fetching video",
                        )
                except requests.exceptions.RequestException as e:
                    log_primary_api_issue("video", vid_id, f"network error: {str(e)}")
                except json.JSONDecodeError as e:
                    log_primary_api_issue("video", vid_id, f"invalid response: {str(e)}")
                except Exception as e:
                    log_primary_api_issue("video", vid_id, str(e))
                finally:
                    if session:
                        session.close()
            else:
                logger.info("xBit fallback not configured for video.")

            if xbit_video_url:
                if stream and await validate_stream_source(xbit_video_url):
                    mark_source(vid_id, "video", "XBIT FALLBACK")
                    schedule_background_cache(xbit_video_url, filepath, headers)
                    return xbit_video_url, False
                result = await download_from_source(xbit_video_url, filepath, headers)
                if result:
                    mark_source(vid_id, "video", "XBIT FALLBACK")
                    return result, True

            logger.warning("Worker/xBit failed for video, trying local yt-dlp fallback.")
            local = await ytdlp_local_fallback(vid_id, "video", filepath)
            if local:
                return local
            mark_source(vid_id, "video", "WORKER PRIMARY + XBIT FALLBACK", ok=False)
            logger.error(
                "YouTube source failed | sources=worker_primary,xbit_fallback | media=video | video_id=%s | title=%s",
                vid_id,
                log_title,
            )
            return None, True
        
        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            fpath = f"downloads/{title}.mp4"
            return fpath
        elif songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            fpath = f"downloads/{title}.mp3"
            return fpath
        elif video:
            downloaded_file, direct = await video_dl(vid_id)
        else:
            downloaded_file, direct = await audio_dl(vid_id)
        
        return downloaded_file, direct
