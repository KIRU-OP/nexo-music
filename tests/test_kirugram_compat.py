from pathlib import Path


def test_kirugram_imports_and_required_api():
    import kirugram
    from kirugram import Client, filters
    from kirugram.raw.types import InputGroupCallSlug

    assert kirugram.__version__ == "2.2.27"
    assert Client is kirugram.Client
    assert filters is kirugram.filters
    assert InputGroupCallSlug is not None


def test_start_script_installs_kirugram_distribution():
    start_script = (Path(__file__).resolve().parents[1] / "start").read_text()
    assert "Kirugram @ git+https://github.com/KIRU-OP/Kirugram.git@main" in start_script
    assert "kurigram" not in start_script.lower()
    assert "from kirugram.raw.types import InputGroupCallSlug" in start_script


def test_pytgcalls_compatibility_is_owned_by_kirugram():
    import kirugram
    from pytgcalls import PyTgCalls
    from pytgcalls.mtproto.bridged_client import BridgedClient

    client = kirugram.Client("kirugram-pytgcalls-test", 12345, "0" * 32)
    calls = PyTgCalls(client)

    assert calls is not None
    assert BridgedClient.package_name(client) == "pyrogram"

    call_source = (
        Path(__file__).resolve().parents[1] / "nexo" / "core" / "call.py"
    ).read_text()
    assert "_KIRUGRAM_PYTG_CALLS_MODULES" not in call_source
    assert "BridgedClient.package_name =" not in call_source
