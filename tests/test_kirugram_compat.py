def test_legacy_pyrogram_imports_resolve_to_kirugram():
    import kirugram
    import kirugram_compat  # noqa: F401
    import pyrogram

    assert pyrogram is kirugram

    from pyrogram import Client
    from kirugram import Client as KirugramClient

    assert Client is KirugramClient

    from pyrogram.types import InlineKeyboardButton
    from kirugram.types import InlineKeyboardButton as KirugramInlineKeyboardButton

    assert InlineKeyboardButton is KirugramInlineKeyboardButton
