import re
from os import getenv
from dotenv import load_dotenv
from pyrogram import filters

# Load environment variables from .env file
load_dotenv()

# ── Core bot config ────────────────────────────────────────────────────────────
API_ID = int(getenv("API_ID", 0))
API_HASH = getenv("API_HASH", "")
BOT_TOKEN = getenv("BOT_TOKEN")

OWNER_ID = int(getenv("OWNER_ID", 0))
OWNER_USERNAME = getenv("OWNER_USERNAME", "")
BOT_USERNAME = getenv("BOT_USERNAME", "")
BOT_NAME = getenv("BOT_NAME", "˹♪")
ASSUSERNAME = getenv("ASSUSERNAME", "")

# ── Database & logging ─────────────────────────────────────────────────────────
MONGO_DB_URI = getenv("MONGO_DB_URI")
LOGGER_ID = int(getenv("LOGGER_ID", 0))

# ── Limits (durations in min/sec; sizes in bytes) ──────────────────────────────
DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 300))
SONG_DOWNLOAD_DURATION = int(getenv("SONG_DOWNLOAD_DURATION", "1200"))
SONG_DOWNLOAD_DURATION_LIMIT = int(getenv("SONG_DOWNLOAD_DURATION_LIMIT", "1800"))
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", "157286400"))       # 150 MB
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", "2147483648"))      # 2 GB (fixed from bogus 1.17 PB value)
QUEUE_LIMIT = int(getenv("QUEUE_LIMIT", "10"))
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", str(QUEUE_LIMIT)))

# ── External APIs ──────────────────────────────────────────────────────────────
API_URL = getenv("API_URL")        # optional
API_KEY = getenv("API_KEY")        # optional
DEEP_API = getenv("DEEP_API")      # optional
REPLICATE_API_TOKEN = getenv("REPLICATE_API_TOKEN")  # optional
REPLICATE_API_TOKENS = getenv("REPLICATE_API_TOKENS", "")  # optional comma-separated pool
GENVID_USE_PUBLIC_FALLBACKS = getenv("GENVID_USE_PUBLIC_FALLBACKS", "0")
HF_TOKEN = getenv("HF_TOKEN")  # optional
HF_TOKENS = getenv("HF_TOKENS", "")  # optional comma-separated pool
OCR_SPACE_API_KEY = getenv("OCR_SPACE_API_KEY", "helloworld")  # optional shared free key
ELITE_LLM_API_BASE = getenv("ELITE_LLM_API_BASE", "https://elite-llms.vercel.app/v1")
ELITE_LLM_API_KEY = getenv("ELITE_LLM_API_KEY", "")

# Vars For API End Point.
YTPROXY_URL = getenv("YTPROXY_URL", "")  # Optional xBit fallback endpoint.
YT_API_KEY = getenv("YT_API_KEY", None)  # Optional xBit API key like: xbit_10000000xx0233

# ── Hosting / deployment ───────────────────────────────────────────────────────
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

# ── Git / updates ──────────────────────────────────────────────────────────────
UPSTREAM_REPO = getenv("UPSTREAM_REPO", "https://github.com/KIRU-OP/nexo-music")
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "master")
GIT_TOKEN = getenv("GIT_TOKEN")  # needed if repo is private

# ── Support links ──────────────────────────────────────────────────────────────
SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/about_deadly_venom")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/+2PkcrtzO-1A5MjY1")
POLICY_URL = getenv("POLICY_URL", "https://t.me/+GO2K-RVFS7o3ZjNl")

# ── Assistant auto-leave ───────────────────────────────────────────────────────
AUTO_LEAVING_ASSISTANT = True
AUTO_LEAVE_ASSISTANT_TIME = int(getenv("ASSISTANT_LEAVE_TIME", "15000"))

# ── Debug ──────────────────────────────────────────────────────────────────────
DEBUG_IGNORE_LOG = True

# ── Spotify (optional) ─────────────────────────────────────────────────────────
# Get this credentials from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", "1c21247d714244ddbb09925dac565aed")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", "709e1a2969664491b58200860623ef19")

# ── Session strings (optional) ─────────────────────────────────────────────────
STRING1 = getenv("STRING_SESSION")
STRING2 = getenv("STRING_SESSION2")
STRING3 = getenv("STRING_SESSION3")
STRING4 = getenv("STRING_SESSION4")
STRING5 = getenv("STRING_SESSION5")

# ── Media assets ───────────────────────────────────────────────────────────────
START_VIDS = [
    "https://te.legra.ph/file/5fd13f2cc0d03bce9f7f2.jpg",
    "https://te.legra.ph/file/5fd13f2cc0d03bce9f7f2.jpg",
    "https://te.legra.ph/file/5fd13f2cc0d03bce9f7f2.jpg",
]
STICKERS = [
    "CAACAgUAAx0Cd6nKUAACASBl_rnalOle6g7qS-ry-aZ1ZpVEnwACgg8AAizLEFfI5wfykoCR4h4E",
    "CAACAgUAAx0Cd6nKUAACATJl_rsEJOsaaPSYGhU7bo7iEwL8AAPMDgACu2PYV8Vb8aT4_HUPHgQ",
]
HELP_IMG_URL = "https://files.catbox.moe/km9sob.jpg"
PING_VID_URL = "https://files.catbox.moe/km9sob.jpg"
PLAYLIST_IMG_URL = "https://files.catbox.moe/km9sob.jpg"
STATS_VID_URL = "https://files.catbox.moe/km9sob.jpg"
TELEGRAM_AUDIO_URL = "https://files.catbox.moe/km9sob.jpg"
TELEGRAM_VIDEO_URL = "https://files.catbox.moe/km9sob.jpg"
STREAM_IMG_URL = "https://files.catbox.moe/km9sob.jpg"
SOUNCLOUD_IMG_URL = "https://files.catbox.moe/km9sob.jpg"
YOUTUBE_IMG_URL = "https://files.catbox.moe/km9sob.jpg"
SPOTIFY_ARTIST_IMG_URL = SPOTIFY_ALBUM_IMG_URL = SPOTIFY_PLAYLIST_IMG_URL = YOUTUBE_IMG_URL

# ── Helpers ────────────────────────────────────────────────────────────────────
def time_to_seconds(time: str) -> int:
    return sum(int(x) * 60**i for i, x in enumerate(reversed(time.split(":"))))

DURATION_LIMIT = time_to_seconds(f"{DURATION_LIMIT_MIN}:00")

# ───── Bot Introduction Messages ───── #
AYU = ["🥀 𝐏ɤσƈɛssɩŋʛ..."]
AYUV = [
    "ʜᴇʏ {0}, ɪ'ᴍ {1} 🎧\n\nʏᴏᴜʀ ᴀʟʟ-ɪɴ-ᴏɴᴇ ᴛᴇʟᴇɢʀᴀᴍ ᴄᴏᴍᴘᴀɴɪᴏɴ, ʙᴜɪʟᴛ ᴛᴏ ᴋᴇᴇᴘ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴇɴᴛᴇʀᴛᴀɪɴᴇᴅ ᴀɴᴅ ᴡᴇʟʟ ᴍᴀɴᴀɢᴇᴅ.\n\n✦ ᴡʜᴀᴛ ɪ ᴄᴀɴ ᴅᴏ:\n▸ ᴘʟᴀʏ ᴍᴜsɪᴄ ɪɴ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs — ʏᴏᴜᴛᴜʙᴇ, sᴘᴏᴛɪғʏ & ᴍᴏʀᴇ\n▸ ɢᴇɴᴇʀᴀᴛᴇ sᴛᴜɴɴɪɴɢ ᴀɪ ɪᴍᴀɢᴇs\n▸ ᴛʀᴀɴsʟᴀᴛᴇ ᴛᴇxᴛ ᴀᴄʀᴏss ᴍᴜʟᴛɪᴘʟᴇ ʟᴀɴɢᴜᴀɢᴇs\n▸ ғᴜʟʟ ɢʀᴏᴜᴘ ᴍᴏᴅᴇʀᴀᴛɪᴏɴ — ᴍᴜᴛᴇ, ʙᴀɴ, ᴋɪᴄᴋ & ᴍᴏʀᴇ\n▸ ᴄᴜsᴛᴏᴍ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇs ғᴏʀ ɴᴇᴡ ᴍᴇᴍʙᴇʀs\n▸ ᴘʟᴜs ᴘʟᴇɴᴛʏ ᴍᴏʀᴇ ᴛᴏᴏʟs — ᴛᴀᴘ ᴄᴏᴍᴍᴀɴᴅs ʙᴇʟᴏᴡ ᴛᴏ ᴇxᴘʟᴏʀᴇ\n\n📊 sᴛᴀᴛs\nᴜᴘᴛɪᴍᴇ: {2} · sᴛᴏʀᴀɢᴇ: {3}\nᴄᴘᴜ: {4} · ʀᴀᴍ: {5}\nᴜsᴇʀs: {6} · ᴄʜᴀᴛs: {7}\n\n💫 ᴅᴇᴠᴇʟᴏᴘᴇʀ: [𝐕 𝚬 𝚴 𝚶 𝚳 ⴕ](https://t.me/ll_deadly_venom_ll)",
    "ʜᴇʏ {0}, ɪ'ᴍ {1} 🎧\n\nʏᴏᴜʀ ᴀʟʟ-ɪɴ-ᴏɴᴇ ᴛᴇʟᴇɢʀᴀᴍ ᴄᴏᴍᴘᴀɴɪᴏɴ, ʙᴜɪʟᴛ ᴛᴏ ᴋᴇᴇᴘ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴇɴᴛᴇʀᴛᴀɪɴᴇᴅ ᴀɴᴅ ᴡᴇʟʟ ᴍᴀɴᴀɢᴇᴅ.\n\n✦ ᴡʜᴀᴛ ɪ ᴄᴀɴ ᴅᴏ:\n▸ ᴘʟᴀʏ ᴍᴜsɪᴄ ɪɴ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs — ʏᴏᴜᴛᴜʙᴇ, sᴘᴏᴛɪғʏ & ᴍᴏʀᴇ\n▸ ɢᴇɴᴇʀᴀᴛᴇ sᴛᴜɴɴɪɴɢ ᴀɪ ɪᴍᴀɢᴇs\n▸ ᴛʀᴀɴsʟᴀᴛᴇ ᴛᴇxᴛ ᴀᴄʀᴏss ᴍᴜʟᴛɪᴘʟᴇ ʟᴀɴɢᴜᴀɢᴇs\n▸ ғᴜʟʟ ɢʀᴏᴜᴘ ᴍᴏᴅᴇʀᴀᴛɪᴏɴ — ᴍᴜᴛᴇ, ʙᴀɴ, ᴋɪᴄᴋ & ᴍᴏʀᴇ\n▸ ᴄᴜsᴛᴏᴍ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇs ғᴏʀ ɴᴇᴡ ᴍᴇᴍʙᴇʀs\n▸ ᴘʟᴜs ᴘʟᴇɴᴛʏ ᴍᴏʀᴇ ᴛᴏᴏʟs — ᴛᴀᴘ ᴄᴏᴍᴍᴀɴᴅs ʙᴇʟᴏᴡ ᴛᴏ ᴇxᴘʟᴏʀᴇ\n\n📊 sᴛᴀᴛs\nᴜᴘᴛɪᴍᴇ: {2} · sᴛᴏʀᴀɢᴇ: {3}\nᴄᴘᴜ: {4} · ʀᴀᴍ: {5}\nᴜsᴇʀs: {6} · ᴄʜᴀᴛs: {7}\n\n💫 ᴅᴇᴠᴇʟᴏᴘᴇʀ: [𝐕 𝚬 𝚴 𝚶 𝚳 ⴕ](https://t.me/ll_deadly_venom_ll)",
]

# ── Runtime structures ─────────────────────────────────────────────────────────
BANNED_USERS = filters.user()
adminlist, lyrical, votemode, autoclean, confirmer = {}, {}, {}, [], {}

# ── Minimal validation ─────────────────────────────────────────────────────────
if SUPPORT_CHANNEL and not re.match(r"^https?://", SUPPORT_CHANNEL):
    raise SystemExit("[ERROR] - Invalid SUPPORT_CHANNEL URL. Must start with https://")

if SUPPORT_CHAT and not re.match(r"^https?://", SUPPORT_CHAT):
    raise SystemExit("[ERROR] - Invalid SUPPORT_CHAT URL. Must start with https://")

if POLICY_URL and not re.match(r"^https?://", POLICY_URL):
    raise SystemExit("[ERROR] - Invalid POLICY_URL. Must start with https://")
