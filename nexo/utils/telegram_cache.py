"""
Telegram channel cache for downloaded media.

Idea: the first time a song/video is fetched (via yt-dlp / worker API / xBit),
we also upload it to a private Telegram "cache channel" and remember the
resulting file_id. On every later request for the same video_id, we pull the
media straight from Telegram instead of re-hitting YouTube or the worker API
— this avoids IP-based rate limiting on those upstream services.

Requirements:
  1. Set CACHE_CHANNEL_ID below (or in config.py — see the override note).
  2. A Pyrogram Client instance importable as `app` from the `nexo` package
     (change the import below if your bot exposes it under a different name).
"""

import asyncio
import json
import os

from nexo import LOGGER, app  # noqa: F401  -- adjust `app` import if your bot names it differently

logger = LOGGER(__name__)

# ============================================================================
# SET YOUR CACHE CHANNEL ID HERE
# This must be the numeric id of a channel where your bot is an admin
# (needs permission to post/upload media). Example: -1001234567890
# Leave as None to disable channel caching entirely.
# ============================================================================
CACHE_CHANNEL_ID = None  # <-- put your channel id here, e.g. -1001234567890

# Optional: if config.py defines CACHE_CHANNEL_ID, it overrides the value above
# so you can also set it there instead if you prefer keeping all config in one place.
try:
    from config import CACHE_CHANNEL_ID as _CONFIG_CACHE_CHANNEL_ID
    if _CONFIG_CACHE_CHANNEL_ID:
        CACHE_CHANNEL_ID = _CONFIG_CACHE_CHANNEL_ID
except ImportError:
    pass

_CACHE_INDEX_PATH = os.path.join("nexo", "utils", "channel_cache.json")
_lock = asyncio.Lock()


def _load_index() -> dict:
    if not os.path.exists(_CACHE_INDEX_PATH):
        return {}
    try:
        with open(_CACHE_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_index(data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_CACHE_INDEX_PATH), exist_ok=True)
        tmp_path = _CACHE_INDEX_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, _CACHE_INDEX_PATH)
    except Exception as exc:
        logger.warning(f"Failed to save Telegram channel cache index: {exc}")


def channel_cache_enabled() -> bool:
    return bool(CACHE_CHANNEL_ID)


async def get_channel_cached_file(vid_id: str, media_type: str, dest_path: str):
    """
    If we've previously cached this video's audio/video in the channel,
    download it from Telegram into dest_path and return dest_path.
    Returns None on a miss or on failure.
    """
    if not channel_cache_enabled():
        return None

    data = _load_index()
    file_id = (data.get(vid_id) or {}).get(media_type)
    if not file_id:
        return None

    try:
        result = await app.download_media(file_id, file_name=dest_path)
        if result and os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            return dest_path
    except Exception as exc:
        logger.warning(
            f"Telegram channel cache download failed for {vid_id} ({media_type}): {exc}"
        )
        # stale file_id (e.g. message deleted) -- drop it so we don't keep retrying
        async with _lock:
            data = _load_index()
            if vid_id in data:
                data[vid_id].pop(media_type, None)
                if not data[vid_id]:
                    data.pop(vid_id, None)
                _save_index(data)
    return None


async def cache_upload(vid_id: str, media_type: str, filepath: str, title: str = None):
    """Upload filepath to the cache channel and remember its file_id."""
    if not channel_cache_enabled():
        return
    if not filepath or not os.path.exists(filepath):
        return

    async with _lock:
        data = _load_index()
        if (data.get(vid_id) or {}).get(media_type):
            return  # already cached by another request

    caption = (title or vid_id)[:1024]
    try:
        if media_type == "video":
            msg = await app.send_video(CACHE_CHANNEL_ID, filepath, caption=caption)
            file_id = msg.video.file_id if msg and msg.video else None
        else:
            msg = await app.send_audio(CACHE_CHANNEL_ID, filepath, caption=caption)
            file_id = msg.audio.file_id if msg and msg.audio else None

        if not file_id:
            return

        async with _lock:
            data = _load_index()
            data.setdefault(vid_id, {})[media_type] = file_id
            _save_index(data)

        logger.info(f"Telegram channel cache stored | video_id={vid_id} | media={media_type}")
    except Exception as exc:
        logger.warning(
            f"Telegram channel cache upload failed | video_id={vid_id} | media={media_type} | reason={exc}"
        )


def schedule_cache_upload(vid_id: str, media_type: str, filepath: str, title: str = None):
    """Fire-and-forget upload so callers don't have to await it."""
    if not channel_cache_enabled():
        return
    try:
        asyncio.create_task(cache_upload(vid_id, media_type, filepath, title))
    except RuntimeError:
        # no running loop (shouldn't happen inside async bot code) -- ignore
        pass
