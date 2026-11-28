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


def test_pytgcalls_accepts_kirugram_client():
    import importlib
    import sys
    import kirugram

    modules = (
        "errors",
        "raw.base",
        "raw.functions.auth",
        "raw.functions.channels",
        "raw.functions.messages",
        "raw.functions.phone",
        "raw.functions.updates",
        "raw.functions.upload",
        "raw.types",
        "raw.types.messages",
        "session",
    )
    for module_name in modules:
        importlib.import_module(f"kirugram.{module_name}")

    for module_name, module in tuple(sys.modules.items()):
        if module_name == "kirugram" or module_name.startswith("kirugram."):
            sys.modules["pyrogram" + module_name[len("kirugram"):]] = module

    from pytgcalls.mtproto.bridged_client import BridgedClient
    from pytgcalls import PyTgCalls

    original_package_name = BridgedClient.package_name

    def package_name(client):
        if client.__class__.__module__.split(".", 1)[0] == "kirugram":
            return "pyrogram"
        return original_package_name(client)

    BridgedClient.package_name = staticmethod(package_name)
    client = kirugram.Client("kirugram-pytgcalls-test", 12345, "0" * 32)
    calls = PyTgCalls(client)

    assert calls is not None
    assert BridgedClient.package_name(client) == "pyrogram"
