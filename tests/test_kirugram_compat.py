from pathlib import Path


def test_kirugram_imports():
    import kirugram
    import kirugram
    from kirugram import Client as KirugramClient
    from kirugram import Client as KirugramClient, filters
    from kirugram.raw.types import InputGroupCallSlug

    assert kirugram.__version__ == "2.2.27"
    assert kirugram.__version__ == "2.2.27"
    assert KirugramClient is kirugram.Client
    assert KirugramClient is kirugram.Client
    assert filters is kirugram.filters
    assert InputGroupCallSlug is not None


def test_start_script_installs_both_distributions():
    start_script = (Path(__file__).resolve().parents[1] / "start").read_text()
    assert '"Kirugram==2.2.27"' in start_script
    assert '"Kirugram==2.2.27"' in start_script
    assert "--force-reinstall --no-cache-dir" in start_script
    assert "Kirugram 2.2.27/PyTgCalls compatibility OK" in start_script
    assert "import kirugram" in start_script


def test_pytgcalls_accepts_pyrogram_client():
    import kirugram
    from pytgcalls import PyTgCalls
    from pytgcalls.mtproto.bridged_client import BridgedClient

    client = kirugram.Client("kirugram-pytgcalls-test", 12345, "0" * 32)
    calls = PyTgCalls(client)

    assert calls is not None
    assert BridgedClient.package_name(client) == "pyrogram"
