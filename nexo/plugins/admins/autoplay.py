from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from nexo import app
from nexo.utils.database import get_autoplay, get_cmode, set_autoplay
from nexo.utils.decorators.admins import AdminActual
from nexo.utils.inline import close_markup
from nexo.utils.inline.play import autoplay_button, set_autoplay_ui
from config import BANNED_USERS

try:
    from nexo.misc import SUDOERS
except Exception:
    SUDOERS = set()


# ---------------------------------------------------------------- command
@app.on_message(filters.command(["autoplay", "cautoplay"]) & filters.group & ~BANNED_USERS)
@AdminActual
async def autoplay_control(_, message: Message, strings):
    usage = strings["admin_49"]
    command = message.command[0].lower()

    if command.startswith("c"):
        chat_id = await get_cmode(message.chat.id)
        if chat_id is None:
            return await message.reply_text(strings["setting_7"])
        try:
            await app.get_chat(chat_id)
        except Exception:
            return await message.reply_text(strings["cplay_4"])
    else:
        chat_id = message.chat.id

    if len(message.command) == 1:
        status = "enabled" if await get_autoplay(chat_id) else "disabled"
        return await message.reply_text(
            strings["admin_52"].format(status),
            reply_markup=close_markup(strings),
        )

    state = message.text.split(None, 1)[1].strip().lower()
    if state in {"on", "enable", "enabled", "yes"}:
        await set_autoplay(chat_id, True)
        set_autoplay_ui(chat_id, True)
        return await message.reply_text(
            strings["admin_50"].format(message.from_user.mention),
            reply_markup=close_markup(strings),
        )

    if state in {"off", "disable", "disabled", "no"}:
        await set_autoplay(chat_id, False)
        set_autoplay_ui(chat_id, False)
        return await message.reply_text(
            strings["admin_51"].format(message.from_user.mention),
            reply_markup=close_markup(strings),
        )

    return await message.reply_text(usage, reply_markup=close_markup(strings))


# ------------------------------------------------------- button (callback)
async def _is_admin(chat_id: int, user_id: int) -> bool:
    if user_id in SUDOERS:
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


@app.on_callback_query(filters.regex(r"^AutoplayToggle\|") & ~BANNED_USERS)
async def autoplay_toggle_cb(_, query: CallbackQuery):
    try:
        chat_id = int(query.data.split("|")[1])
    except (IndexError, ValueError):
        return await query.answer()

    if not await _is_admin(query.message.chat.id, query.from_user.id):
        return await query.answer("Sirf admins autoplay change kar sakte hain.", show_alert=True)

    new_state = not await get_autoplay(chat_id)
    await set_autoplay(chat_id, new_state)
    set_autoplay_ui(chat_id, new_state)
    await query.answer(f"Autoplay {'ON ✅' if new_state else 'OFF ❌'}")

    # sirf autoplay button badlo, baaki keyboard jaisa hai waisa
    try:
        new_rows = []
        for row in query.message.reply_markup.inline_keyboard:
            new_rows.append(
                [
                    autoplay_button(chat_id, new_state)
                    if (btn.callback_data or "").startswith("AutoplayToggle|")
                    else btn
                    for btn in row
                ]
            )
        await query.message.edit_reply_markup(InlineKeyboardMarkup(new_rows))
    except Exception:
        pass
