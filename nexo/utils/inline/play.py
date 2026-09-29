import time
from pyrogram.types import InlineKeyboardButton
from nexo.button_styles import danger_button, primary_button, success_button
from nexo.utils.formatters import time_to_seconds

LAST_UPDATE_TIME = {}

# chat_id -> autoplay ON/OFF (button label ke liye cache)
AUTOPLAY_UI = {}


def set_autoplay_ui(chat_id, state: bool):
    AUTOPLAY_UI[chat_id] = bool(state)


def autoplay_button(chat_id, state=None):
    if state is None:
        state = AUTOPLAY_UI.get(chat_id)
    if state is None:
        return primary_button(text="⟳ Autoplay", callback_data=f"AutoplayToggle|{chat_id}")
    if state:
        return success_button(text="⟳ Autoplay: ON", callback_data=f"AutoplayToggle|{chat_id}")
    return danger_button(text="⟳ Autoplay: OFF", callback_data=f"AutoplayToggle|{chat_id}")


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
                callback_data=f"forceclose {videoid}|{user_id}"
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
    filled = int(round(bar_length * percentage / 70))
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
        [[InlineKeyboardButton(text=f"{played} {bar} {dur}", callback_data="GetTimer")]] +
        control_buttons(_, chat_id, autoplay) +
        [[danger_button(text=_["CLOSE_BUTTON"], callback_data="close")]]
    )


def stream_markup(_, chat_id, autoplay=None):
    return control_buttons(_, chat_id, autoplay) + [[danger_button(text=_["CLOSE_BUTTON"], callback_data="close")]]


def playlist_markup(_, videoid, user_id, ptype, channel, fplay):
    buttons = [
        [
            success_button(
                text=_["P_B_1"],
                callback_data=f"VivaanPlaylists {videoid}|{user_id}|{ptype}|a|{channel}|{fplay}"
            ),
            primary_button(
                text=_["P_B_2"],
                callback_data=f"VivaanPlaylists {videoid}|{user_id}|{ptype}|v|{channel}|{fplay}"
            ),
        ],
        [
            danger_button(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}"
            ),
        ],
    ]

    return buttons

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
                callback_data=f"forceclose {videoid}|{user_id}"
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
