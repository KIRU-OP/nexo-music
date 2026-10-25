import asyncio
import logging
import time
from typing import Any, Tuple

from pyrogram import filters
from pyrogram.errors import FloodWait, MessageNotModified, RPCError
from pyrogram.types import Message

from config import BANNED_USERS, PING_VID_URL
from nexo import app
from nexo.core.call import JARVIS
from nexo.utils import bot_sys_stats
from nexo.utils.decorators.language import language
from nexo.utils.inline import supp_markup

LOGGER = logging.getLogger(__name__)

# Jab koi value fetch na ho paaye to yeh dikhayenge
NOT_AVAILABLE = "N/A"


# --------------------------------------------------------------------------- #
#  Helper functions
# --------------------------------------------------------------------------- #
def _elapsed_ms(start: float) -> float:
    """`start` (time.perf_counter) se ab tak ka time milliseconds mein."""
    return round((time.perf_counter() - start) * 1000, 2)


async def _get_voice_ping() -> Any:
    """PyTgCalls ka ping. Fail hone par 'N/A' return karta hai."""
    try:
        return await JARVIS.ping()
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Voice call ping fail hua: %s", exc)
        return NOT_AVAILABLE


async def _get_system_stats() -> Tuple[Any, Any, Any, Any]:
    """(uptime, cpu, ram, disk). Fail hone par sab 'N/A'."""
    try:
        return await bot_sys_stats()
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("System stats fetch fail hue: %s", exc)
        return (NOT_AVAILABLE,) * 4


async def _send_initial(message: Message, _: dict) -> Message:
    """
    Pehla "pinging..." message bhejo.
    Video fail ho jaye (bad URL, network, etc.) to text reply se kaam chalao.
    """
    caption = _["ping_1"].format(app.mention)
    try:
        return await message.reply_video(video=PING_VID_URL, caption=caption)
    except FloodWait as fw:
        await asyncio.sleep(fw.value)
        return await message.reply_video(video=PING_VID_URL, caption=caption)
    except RPCError as exc:
        LOGGER.error("Ping video bhejna fail hua, text fallback: %s", exc)
        return await message.reply_text(caption)


async def _edit_result(response: Message, text: str, markup) -> None:
    """
    Message edit karo. Media message ho to caption edit hoga,
    warna normal text edit.
    """
    try:
        if response.media:
            await response.edit_caption(caption=text, reply_markup=markup)
        else:
            await response.edit_text(text, reply_markup=markup)
    except MessageNotModified:
        pass  # content same tha, koi dikkat nahi
    except FloodWait as fw:
        await asyncio.sleep(fw.value)
        await _edit_result(response, text, markup)


# --------------------------------------------------------------------------- #
#  Command handler
# --------------------------------------------------------------------------- #
@app.on_message(filters.command("ping", prefixes=["/"]) & ~BANNED_USERS)
@language
async def ping_com(client, message: Message, _):
    start = time.perf_counter()

    # Step 1: Initial "pinging..." message
    response = await _send_initial(message, _)

    # Step 2: Dono kaam saath mein (total wait = max of the two, sum nahi)
    pytgping, (UP, CPU, RAM, DISK) = await asyncio.gather(
        _get_voice_ping(),
        _get_system_stats(),
    )

    # Step 3: Response time (seconds + microseconds dono ginke)
    resp = _elapsed_ms(start)

    # Step 4: Final result dikhao
    text = _["ping_2"].format(resp, app.mention, UP, RAM, CPU, DISK, pytgping)
    await _edit_result(response, text, supp_markup(_))
