from pathlib import Path


def test_kurigram_imports_and_required_api():
    import pyrogram
    from pyrogram import Client, filters
    from pyrogram.raw.types import InputGroupCallSlug

    assert pyrogram.__version__ == "2.2.27"
    assert Client is pyrogram.Client
    assert filters is pyrogram.filters
    assert InputGroupCallSlug is not None


def test_start_script_pins_kurigram_distribution():
    start_script = (Path(__file__).resolve().parents[1] / "start").read_text()
    assert '"kurigram==2.2.27"' in start_script
    assert "--force-reinstall --no-cache-dir" in start_script
    assert "Kurigram/PyTgCalls compatibility OK" in start_script
    assert "Kirugram @ git+https://github.com/KIRU-OP/Kirugram.git@main" not in start_script
    assert "from pyrogram.raw.types import InputGroupCallSlug" in start_script


def test_pytgcalls_accepts_kurigram_client():
    import pyrogram
    from pytgcalls import PyTgCalls
    from pytgcalls.mtproto.bridged_client import BridgedClient

    client = pyrogram.Client("kurigram-pytgcalls-test", 12345, "0" * 32)
    calls = PyTgCalls(client)

    assert calls is not None
    assert BridgedClient.package_name(client) == "pyrogram"

    call_source = (
        Path(__file__).resolve().parents[1] / "nexo" / "core" / "call.py"
    ).read_text()
    assert "_KIRUGRAM_PYTG_CALLS_MODULES" not in call_source
    assert "BridgedClient.package_name =" not in call_source
