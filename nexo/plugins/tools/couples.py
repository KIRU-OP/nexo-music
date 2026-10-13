import random
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, UnidentifiedImageError
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import SUPPORT_CHANNEL
from nexo import app
from nexo.core.dir import COUPLE_DIR
from nexo.mongo.couples_db import get_couple, save_couple

ASSETS = Path("nexo/assets")
FALLBACK = ASSETS / "upic.png"
OUT_DIR = Path(COUPLE_DIR)

# @username ya username ho to bhi sahi link ban jaye
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


async def generate_image(chat_id: int, uid1: int, uid2: int, date: str) -> str:
    base = Image.open(ASSETS / "vivaan/couple.png").convert("RGBA")
    p1 = await get_photo(uid1, f"pfp1_{chat_id}.png")
    p2 = await get_photo(uid2, f"pfp2_{chat_id}.png")

    for p, pos in ((p1, (410, 500)), (p2, (1395, 500))):
        av = circular(p)
        base.paste(av, pos, av)
        if p != FALLBACK:
            p.unlink(missing_ok=True)

    out = OUT_DIR / f"couple_{chat_id}_{date.replace('/', '-')}.png"
    base.save(out)
    return str(out)


def user_button(user) -> InlineKeyboardButton:
    text = f"👤 {user.first_name[:15]}"
    if user.username:
        return InlineKeyboardButton(text, url=f"https://t.me/{user.username}")
    return InlineKeyboardButton(text, user_id=user.id)


async def pick_couple(chat_id: int):
    members = [
        m.user.id
        async for m in app.get_chat_members(chat_id, limit=250)
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

    # Aaj ka couple pehle se bana hai to wahi dikhao
    record = await get_couple(cid, date)
    if record:
        user1 = await get_user(record["user1"])
        user2 = await get_user(record["user2"])
        img_path = record["img"]
        if not (user1 and user2 and img_path and Path(img_path).exists()):
            user1 = user2 = img_path = None

    # Nahi bana to naya banao
    if not img_path:
        pair = await pick_couple(cid)
        if not pair:
            return await message.reply("**ɴᴏᴛ ᴇɴᴏᴜɢʜ ᴠᴀʟɪᴅ ᴍᴇᴍʙᴇʀs ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ.**")
        user1, user2 = pair
        img_path = await generate_image(cid, user1.id, user2.id, date)
        await save_couple(cid, date, {"user1": user1.id, "user2": user2.id}, img_path)

    caption = (
        "💌 **ᴄᴏᴜᴘʟᴇ ᴏꜰ ᴛʜᴇ ᴅᴀʏ!**\n\n"
        f"💞 {user1.mention} ✕ {user2.mention}\n\n"
        f"📅 **ɴᴇxᴛ ꜱᴇʟᴇᴄᴛɪᴏɴ:** `{tomorrow()}`"
    )

    buttons = InlineKeyboardMarkup(
        [
            [user_button(user1), user_button(user2)],
            [InlineKeyboardButton("💬 Support Channel", url=SUPPORT_URL)],
        ]
    )

    await message.reply_photo(img_path, caption=caption, reply_markup=buttons)
