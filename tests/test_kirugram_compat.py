def test_legacy_kirugram_imports_resolve_to_kirugram():
    import kirugram
    import kirugram_compat  # noqa: F401
    import kirugram

    assert kirugram is kirugram

    from kirugram import Client, filters
    from kirugram import Client as KirugramClient, filters as kirugram_filters

    assert Client is KirugramClient
    assert filters is kirugram_filters

    from kirugram.enums import ChatMemberStatus
    from kirugram.enums import ChatMemberStatus as KirugramChatMemberStatus
    from kirugram.errors import Forbidden
    from kirugram.errors import Forbidden as KirugramForbidden
    from kirugram.handlers import RawUpdateHandler
    from kirugram.handlers import RawUpdateHandler as KirugramRawUpdateHandler
    from kirugram.raw.functions.channels import GetFullChannel
    from kirugram.raw.functions.channels import GetFullChannel as KirugramGetFullChannel
    from kirugram.raw.functions.messages import GetFullChat
    from kirugram.raw.functions.messages import GetFullChat as KirugramGetFullChat
    from kirugram.raw.types import PeerUser
    from kirugram.raw.types import PeerUser as KirugramPeerUser
    from kirugram.session.auth import Auth
    from kirugram.session.auth import Auth as KirugramAuth
    from kirugram.storage.sqlite_storage import PROD
    from kirugram.storage.sqlite_storage import PROD as KIRUGRAM_PROD
    from kirugram.types import InlineKeyboardButton
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


def test_start_script_installs_kirugram_not_old_distribution():
    from pathlib import Path

    start_script = (Path(__file__).resolve().parents[1] / "start").read_text()
    assert "Kirugram @ git+https://github.com/KIRU-OP/Kirugram.git@main" in start_script
    assert "kurigram" not in start_script.lower()
    assert "from kirugram.raw.types import InputGroupCallSlug" in start_script
