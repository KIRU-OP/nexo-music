import html
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, UnidentifiedImageError
from pyrogram import filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import SUPPORT_CHANNEL
from nexo import app
from nexo.core.dir import COUPLE_DIR
from nexo.mongo.couples_db import get_couple, save_couple

ASSETS = Path("nexo/assets")
FALLBACK = ASSETS / "upic.png"
OUT_DIR = Path(COUPLE_DIR)

# True = din bhar wahi couple, False = har /couple par naya couple
COUPLE_FIXED_PER_DAY = False
MEMBER_LIMIT = 1000

SUPPORT_URL = (
    SUPPORT_CHANNEL
    if SUPPORT_CHANNEL.startswith("http")
    else f"https://t.me/{SUPPORT_CHANNEL.lstrip('@')}"
)


def today() -> str:
    return datetime.now().strftime("%d/%m/%Y")


def tomorrow() -> str:
    return (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")


def circular(path) -> Image.Image:
    try:
        img = Image.open(path).convert("RGBA")
    except (FileNotFoundError, UnidentifiedImageError):
        img = Image.open(FALLBACK).convert("RGBA")
    img = img.resize((486, 486))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, *img.size), fill=255)
    img.putalpha(mask)
    return img


async def get_user(uid: int):
    try:
        return await app.get_users(uid)
    except Exception:
        return None


async def get_photo(uid: int, name: str) -> Path:
    try:
        chat = await app.get_chat(uid)
        if chat.photo:
            path = await app.download_media(
                chat.photo.big_file_id, file_name=str(OUT_DIR / name)
            )
            if path:
                return Path(path)
    except Exception:
        pass
    return FALLBACK


async def generate_image(chat_id: int, uid1: int, uid2: int, tag: str) -> str:
    base = Image.open(ASSETS / "vivaan/couple.png").convert("RGBA")
    p1 = await get_photo(uid1, f"pfp1_{chat_id}_{tag}.png")
    p2 = await get_photo(uid2, f"pfp2_{chat_id}_{tag}.png")

    for p, pos in ((p1, (410, 500)), (p2, (1395, 500))):
        av = circular(p)
        base.paste(av, pos, av)
        if p != FALLBACK:
            p.unlink(missing_ok=True)

    out = OUT_DIR / f"couple_{chat_id}_{tag}.png"
    base.save(out)
    return str(out)


def short_name(user, limit: int = 10) -> str:
    parts = (user.first_name or "").split()
    name = parts[0] if parts else "User"
    return name[:limit]


def user_button(user) -> InlineKeyboardButton:
    text = f"👤 {short_name(user)}"
    if user.username:
        return InlineKeyboardButton(text, url=f"https://t.me/{user.username}")
    return InlineKeyboardButton(text, user_id=user.id)


def mention(user) -> str:
    return f'<a href="tg://user?id={user.id}">{html.escape(short_name(user))}</a>'


async def pick_couple(chat_id: int):
    members = [
        m.user.id
        async for m in app.get_chat_members(chat_id, limit=MEMBER_LIMIT)
        if not m.user.is_bot and not m.user.is_deleted
    ]
    random.shuffle(members)
    found = []
    for uid in members:
        user = await get_user(uid)
        if user:
            found.append(user)
        if len(found) == 2:
            return found
    return None


@app.on_message(filters.command("couple"))
async def couples_handler(_, message: Message):
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply("**ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴏɴʟʏ ᴡᴏʀᴋs ɪɴ ɢʀᴏᴜᴘs.**")

    cid, date = message.chat.id, today()
    user1 = user2 = img_path = None

    # Sirf fixed mode mein aaj ka saved couple use hoga
    if COUPLE_FIXED_PER_DAY:
        record = await get_couple(cid, date)
        if record:
            user1 = await get_user(record["user1"])
            user2 = await get_user(record["user2"])
            img_path = record["img"]
            if not (user1 and user2 and img_path and Path(img_path).exists()):
                user1 = user2 = img_path = None

    if not img_path:
        pair = await pick_couple(cid)
        if not pair:
            return await message.reply(
                "**ɴᴏᴛ ᴇɴᴏᴜɢʜ ᴠᴀʟɪᴅ ᴍᴇᴍʙᴇʀs ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ.**"
            )
        user1, user2 = pair
        tag = (
            date.replace("/", "-")
            if COUPLE_FIXED_PER_DAY
            else str(int(time.time() * 1000))
        )
        img_path = await generate_image(cid, user1.id, user2.id, tag)
        if COUPLE_FIXED_PER_DAY:
            await save_couple(
                cid, date, {"user1": user1.id, "user2": user2.id}, img_path
            )

    caption = (
        "💌 <b>ᴄᴏᴜᴘʟᴇ ᴏꜰ ᴛʜᴇ ᴅᴀʏ!</b>\n\n"
        f"💞 {mention(user1)} ✕ {mention(user2)}"
    )
    if COUPLE_FIXED_PER_DAY:
        caption += f"\n\n📅 <b>ɴᴇxᴛ ꜱᴇʟᴇᴄᴛɪᴏɴ:</b> <code>{tomorrow()}</code>"

    buttons = InlineKeyboardMarkup(
        [
            [user_button(user1), user_button(user2)],
            [InlineKeyboardButton("💬 Support Channel", url=SUPPORT_URL)],
        ]
    )

    await message.reply_photo(
        img_path,
        caption=caption,
        reply_markup=buttons,
        parse_mode=ParseMode.HTML,
    )

    # Random mode mein image dobara kaam nahi aati, delete kar do
    if not COUPLE_FIXED_PER_DAY:
        Path(img_path).unlink(missing_ok=True)
