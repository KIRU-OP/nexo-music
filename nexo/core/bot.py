import asyncio
import os
import sys

from kirugram import Client, errors
from kirugram.enums import ChatMemberStatus
from kirugram.session.auth import Auth
from kirugram.storage.sqlite_storage import PROD, TEST

import config
from ..logging import LOGGER


class JARVIS(Client):
    def __init__(self):
        super().__init__(
            name="VivaanXMusic",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True,
            workers=48,
            max_concurrent_transmissions=7,
        )
        self._login_dc = int(os.getenv("BOT_LOGIN_DC", "5"))
        self._login_attempts = max(1, int(os.getenv("BOT_LOGIN_ATTEMPTS", "3")))
        self._login_retry_delay = max(
            1.0, float(os.getenv("BOT_LOGIN_RETRY_DELAY", "2"))
        )
        LOGGER(__name__).info(
            "Bot client initialized (preferred Telegram DC: %s).",
            self._login_dc,
        )

    async def load_session(self):
        """Create a fresh bot authorization key on the selected Telegram DC."""
        await self.storage.open()

        session_empty = any(
            [
                await self.storage.test_mode() is None,
                await self.storage.auth_key() is None,
                await self.storage.user_id() is None,
                await self.storage.is_bot() is None,
            ]
        )

        if session_empty:
            if not self.api_id or not self.api_hash:
                raise AttributeError(
                    "The API key is required for new Telegram authorizations."
                )

            dc_servers = TEST if self.test_mode else PROD
            server_address = dc_servers[self._login_dc]
            port = 80 if self.test_mode else 443

            await self.storage.api_id(self.api_id)
            await self.storage.dc_id(self._login_dc)
            await self.storage.server_address(server_address)
            await self.storage.port(port)
            await self.storage.date(0)
            await self.storage.test_mode(self.test_mode)
            auth_key = await Auth(
                self,
                self._login_dc,
                server_address,
                port,
                self.test_mode,
            ).create()
            await self.storage.auth_key(auth_key)
            await self.storage.user_id(None)
            await self.storage.is_bot(None)
        elif not await self.storage.api_id() and self.api_id:
            # Preserve compatibility with older session storage versions.
            await self.storage.api_id(self.api_id)

    @staticmethod
    def _is_temporary_login_error(exc):
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError, OSError, ConnectionError)):
            return True

        details = " ".join(
            str(value)
            for value in (
                type(exc).__name__,
                getattr(exc, "ID", ""),
                getattr(exc, "MESSAGE", ""),
                exc,
            )
        ).upper()
        return any(
            marker in details
            for marker in (
                "RPC_CALL_FAIL",
                "TIMEOUT",
                "CONNECTION",
                "NETWORK",
                "INTERNAL_SERVER_ERROR",
                "TEMPORARY",
                "SERVER_ERROR",
            )
        )

    async def _reset_failed_login(self):
        try:
            if self.is_connected:
                await self.disconnect()
            elif self.session:
                await self.session.stop()
        except Exception as cleanup_error:
            LOGGER(__name__).warning(
                "Telegram login cleanup warning: %s",
                type(cleanup_error).__name__,
            )
        finally:
            self.session = None

        if self.storage:
            # The bot client uses in-memory storage; discard only the failed
            # local authorization so the next attempt can create a DC-specific key.
            await self.storage.auth_key(None)
            await self.storage.user_id(None)
            await self.storage.is_bot(None)
            await self.storage.dc_id(0)

    async def start(self):
        preferred_dc = self._login_dc
        fallback_dc = 2 if preferred_dc != 2 else 5
        last_error = None

        for dc_index, dc_id in enumerate((preferred_dc, fallback_dc)):
            self._login_dc = dc_id

            for attempt in range(1, self._login_attempts + 1):
                try:
                    await super().start()
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    await self._reset_failed_login()

                    if not self._is_temporary_login_error(exc):
                        raise

                    if attempt < self._login_attempts:
                        delay = min(
                            self._login_retry_delay * (2 ** (attempt - 1)),
                            30,
                        )
                        LOGGER(__name__).warning(
                            "Temporary Telegram login failure on DC%s "
                            "(attempt %s/%s): %s. Retrying in %.1fs.",
                            dc_id,
                            attempt,
                            self._login_attempts,
                            type(exc).__name__,
                            delay,
                        )
                        await asyncio.sleep(delay)

            if last_error is None:
                break

            if dc_index == 0:
                LOGGER(__name__).warning(
                    "Telegram DC%s login did not recover; switching to DC%s.",
                    preferred_dc,
                    fallback_dc,
                )

        if last_error is not None:
            raise last_error

        me = await self.get_me()
        self.username, self.id = me.username, me.id
        self.name = f"{me.first_name} {me.last_name or ''}".strip()
        self.mention = me.mention

        try:
            await self.send_message(
                config.LOGGER_ID,
                (
                    f"<u><b>» {self.mention} ʙᴏᴛ sᴛᴀʀᴛᴇᴅ :</b></u>\n\n"
                    f"ɪᴅ : <code>{self.id}</code>\n"
                    f"ɴᴀᴍᴇ : {self.name}\n"
                    f"ᴜsᴇʀɴᴀᴍᴇ : @{self.username}"
                ),
            )
        except (errors.ChannelInvalid, errors.PeerIdInvalid):
            LOGGER(__name__).error(
                "❌ Bot cannot access the log group/channel – add & promote it first!"
            )
            sys.exit()
        except Exception as exc:
            LOGGER(__name__).error(
                "❌ Bot has failed to access the log group.\n"
                "Reason: %s",
                type(exc).__name__,
            )
            sys.exit()

        try:
            member = await self.get_chat_member(config.LOGGER_ID, self.id)
            if member.status != ChatMemberStatus.ADMINISTRATOR:
                LOGGER(__name__).error(
                    "❌ Promote the bot as admin in the log group/channel."
                )
                sys.exit()
        except Exception as exc:
            LOGGER(__name__).error(
                "❌ Could not check admin status: %s", type(exc).__name__
            )
            sys.exit()

        LOGGER(__name__).info(
            "✅ Music Bot started as %s (@%s) on Telegram DC%s",
            self.name,
            self.username,
            self._login_dc,
        )
