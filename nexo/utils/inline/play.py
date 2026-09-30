import logging
import time

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import BANNED_USERS
from nexo.button_styles import danger_button, primary_button, success_button
from nexo.utils.database import get_autoplay, set_autoplay
from nexo.utils.formatters import time_to_seconds

# Voice Play ke saath autoplay conflict na ho, isliye optional import
try:
    from nexo.utils.database import get_voiceplay, set_voiceplay
except Exception:
    get_voiceplay = None
    set_voiceplay = None

try:
    from nexo.misc import SUDOERS
except Exception:
    SUDOERS = set()

LOGGER = logging.getLogger(__name__)

LAST_UPDATE_TIME = {}

# chat_id -> autoplay ON/OFF (button label ke liye cache)
AUTOPLAY_UI = {}


# ------------------------------------------------------------ autoplay UI
def set_autoplay_ui(chat_id, state: bool):
    AUTOPLAY_UI[chat_id] = bool(state)


async def sync_autoplay_ui(chat_id):
    """DB se asli state padh ke button cache update karo.
    call.py mein stream_markup() se pehle await karna."""
    try:
        state = bool(await get_autoplay(chat_id))
        set_autoplay_ui(chat_id, state)
        return state
    except Exception as e:
        LOGGER.warning("sync_autoplay_ui failed | chat_id=%s | %s", chat_id, e)
        return AUTOPLAY_UI.get(chat_id, False)


def autoplay_button(chat_id, state=None):
    if state is None:
        state = AUTOPLAY_UI.get(chat_id, False)
    if state:
        return success_button(
            text="⟳ Autoplay: ON", callback_data=f"AutoplayToggle|{chat_id}"
        )
    return danger_button(
        text="⟳ Autoplay: OFF", callback_data=f"AutoplayToggle|{chat_id}"
    )


# ---------------------------------------------------------------- markups
def track_markup(_, videoid, user_id, channel, fplay):
    return [
        [
            success_button(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            primary_button(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            danger_button(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            )
        ],
    ]


def should_update_progress(chat_id):
    now = time.time()
    last = LAST_UPDATE_TIME.get(chat_id, 0)
    if now - last >= 6:
        LAST_UPDATE_TIME[chat_id] = now
        return True
    return False


def generate_progress_bar(played_sec, duration_sec):
    if duration_sec == 0:
        percentage = 0
    else:
        percentage = min((played_sec / duration_sec) * 100, 100)

    bar_length = 8
    filled = int(round(bar_length * percentage / 100))
    return "▰" * filled + "▱" * (bar_length - filled)


def control_buttons(_, chat_id, autoplay=None):
    if autoplay is not None:
        set_autoplay_ui(chat_id, autoplay)
    return [
        [
            success_button(text="▷", callback_data=f"ADMIN Resume|{chat_id}"),
            primary_button(text="II", callback_data=f"ADMIN Pause|{chat_id}"),
            InlineKeyboardButton(text="↻", callback_data=f"ADMIN Replay|{chat_id}"),
            primary_button(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}"),
            danger_button(text="▢", callback_data=f"ADMIN Stop|{chat_id}"),
        ],
        [autoplay_button(chat_id)],
    ]


def stream_markup_timer(_, chat_id, played, dur, autoplay=None):
    if not should_update_progress(chat_id):
        return None

    played_sec = time_to_seconds(played)
    duration_sec = time_to_seconds(dur)
    bar = generate_progress_bar(played_sec, duration_sec)

    return (
        [[InlineKeyboardButton(text=f"{played} {bar} {dur}", callback_data="GetTimer")]]
        + control_buttons(_, chat_id, autoplay)
        + [[danger_button(text=_["CLOSE_BUTTON"], callback_data="close")]]
    )


def stream_markup(_, chat_id, autoplay=None):
    return control_buttons(_, chat_id, autoplay) + [
        [danger_button(text=_["CLOSE_BUTTON"], callback_data="close")]
    ]


def playlist_markup(_, videoid, user_id, ptype, channel, fplay):
    return [
        [
            success_button(
                text=_["P_B_1"],
                callback_data=f"VivaanPlaylists {videoid}|{user_id}|{ptype}|a|{channel}|{fplay}",
            ),
            primary_button(
                text=_["P_B_2"],
                callback_data=f"VivaanPlaylists {videoid}|{user_id}|{ptype}|v|{channel}|{fplay}",
            ),
        ],
        [
            danger_button(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            ),
        ],
    ]


def livestream_markup(_, videoid, user_id, mode, channel, fplay):
    return [
        [
            success_button(
                text=_["P_B_3"],
                callback_data=f"LiveStream {videoid}|{user_id}|{mode}|{channel}|{fplay}",
            )
        ],
        [
            danger_button(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            )
        ],
    ]


def slider_markup(_, videoid, user_id, query, query_type, channel, fplay):
    short_query = query[:20]
    return [
        [
            success_button(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            primary_button(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="◁",
                callback_data=f"slider B|{query_type}|{short_query}|{user_id}|{channel}|{fplay}",
            ),
            danger_button(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {short_query}|{user_id}",
            ),
            primary_button(
                text="▷",
                callback_data=f"slider F|{query_type}|{short_query}|{user_id}|{channel}|{fplay}",
            ),
        ],
    ]


# ------------------------------------------- autoplay button (ON / OFF)
async def _is_admin(chat_id: int, user_id: int) -> bool:
    from nexo import app

    if user_id in SUDOERS:
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


def _register_autoplay_callback():
    from nexo import app

    @app.on_callback_query(
        filters.regex(r"^AutoplayToggle\|") & ~BANNED_USERS, group=-1
    )
    async def autoplay_toggle_cb(_, query: CallbackQuery):
        try:
            chat_id = int(query.data.split("|")[1])
        except (IndexError, ValueError):
            return await query.answer()

        if not await _is_admin(query.message.chat.id, query.from_user.id):
            return await query.answer(
                "Sirf admins autoplay change kar sakte hain.", show_alert=True
            )

        try:
            new_state = not bool(await get_autoplay(chat_id))
            await set_autoplay(chat_id, new_state)
            set_autoplay_ui(chat_id, new_state)

            # Autoplay ON karte waqt Voice Play OFF, warna call.py autoplay
            # ko wapas OFF kar deta hai
            if new_state and get_voiceplay and set_voiceplay:
                vp = await get_voiceplay(chat_id)
                if vp and vp.get("enabled"):
                    await set_voiceplay(chat_id, False)
        except Exception as e:
            LOGGER.exception("Autoplay toggle failed | chat_id=%s | %s", chat_id, e)
            return await query.answer(
                "Autoplay change nahi ho paya.", show_alert=True
            )

        await query.answer(f"Autoplay {'ON ✅' if new_state else 'OFF ❌'}")

        # sirf autoplay button badlo, baaki keyboard jaisa hai waisa
        try:
            rows = [
                [
                    autoplay_button(chat_id, new_state)
                    if (b.callback_data or "").startswith("AutoplayToggle|")
                    else b
                    for b in row
                ]
                for row in query.message.reply_markup.inline_keyboard
            ]
            await query.message.edit_reply_markup(InlineKeyboardMarkup(rows))
        except Exception as e:
            LOGGER.warning("Autoplay keyboard edit failed: %s", e)


_register_autoplay_callback()
