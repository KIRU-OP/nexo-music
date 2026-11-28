def test_legacy_pyrogram_imports_resolve_to_kirugram():
    import kirugram
    import kirugram_compat  # noqa: F401
    import pyrogram

    assert pyrogram is kirugram

    from pyrogram import Client, filters
    from kirugram import Client as KirugramClient, filters as kirugram_filters

    assert Client is KirugramClient
    assert filters is kirugram_filters

    from pyrogram.enums import ChatMemberStatus
    from kirugram.enums import ChatMemberStatus as KirugramChatMemberStatus
    from pyrogram.errors import Forbidden
    from kirugram.errors import Forbidden as KirugramForbidden
    from pyrogram.handlers import RawUpdateHandler
    from kirugram.handlers import RawUpdateHandler as KirugramRawUpdateHandler
    from pyrogram.raw.functions.channels import GetFullChannel
    from kirugram.raw.functions.channels import GetFullChannel as KirugramGetFullChannel
    from pyrogram.raw.functions.messages import GetFullChat
    from kirugram.raw.functions.messages import GetFullChat as KirugramGetFullChat
    from pyrogram.raw.types import PeerUser
    from kirugram.raw.types import PeerUser as KirugramPeerUser
    from pyrogram.session.auth import Auth
    from kirugram.session.auth import Auth as KirugramAuth
    from pyrogram.storage.sqlite_storage import PROD
    from kirugram.storage.sqlite_storage import PROD as KIRUGRAM_PROD
    from pyrogram.types import InlineKeyboardButton
    from kirugram.types import InlineKeyboardButton as KirugramInlineKeyboardButton

    assert ChatMemberStatus is KirugramChatMemberStatus
    assert Forbidden is KirugramForbidden
    assert RawUpdateHandler is KirugramRawUpdateHandler
    assert GetFullChannel is KirugramGetFullChannel
    assert GetFullChat is KirugramGetFullChat
    assert PeerUser is KirugramPeerUser
    assert Auth is KirugramAuth
    assert PROD == KIRUGRAM_PROD
    assert InlineKeyboardButton is KirugramInlineKeyboardButton
