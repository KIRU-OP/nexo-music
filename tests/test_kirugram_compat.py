from pathlib import Path


def test_pyrogram_and_kirugram_imports():
    import kirugram
    import pyrogram
    from kirugram import Client as KirugramClient
    from pyrogram import Client as PyrogramClient, filters
    from pyrogram.raw.types import InputGroupCallSlug

    assert pyrogram.__version__ == "2.2.27"
    assert kirugram.__version__ == "2.2.27"
    assert PyrogramClient is pyrogram.Client
    assert KirugramClient is kirugram.Client
    assert filters is pyrogram.filters
    assert InputGroupCallSlug is not None


def test_start_script_installs_both_distributions():
    start_script = (Path(__file__).resolve().parents[1] / "start").read_text()
    assert '"Pyrogram==2.2.27"' in start_script
    assert '"Kirugram==2.2.27"' in start_script
    assert "--force-reinstall --no-cache-dir" in start_script
    assert "Pyrogram/Kirugram 2.2.27 compatibility OK" in start_script
    assert "import kirugram, pyrogram" in start_script


def test_pytgcalls_accepts_pyrogram_client():
    import pyrogram
    from pytgcalls import PyTgCalls
    from pytgcalls.mtproto.bridged_client import BridgedClient

    client = pyrogram.Client("pyrogram-pytgcalls-test", 12345, "0" * 32)
    calls = PyTgCalls(client)

    assert calls is not None
    assert BridgedClient.package_name(client) == "pyrogram"
