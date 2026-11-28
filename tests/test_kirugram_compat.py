from pathlib import Path


def test_kirugram_imports():
    from importlib.metadata import version

    import kirugram
    from kirugram import Client, filters
    from kirugram.raw.types import InputGroupCallSlug

    assert kirugram.__version__ == "2.2.27"
    assert version("Kirugram") == "2.2.27"
    assert Client is kirugram.Client
    assert filters is kirugram.filters
    assert InputGroupCallSlug is not None


def test_start_script_installs_kirugram():
    start_script = (Path(__file__).resolve().parents[1] / "start").read_text()
    assert "Kirugram @ git+https://github.com/KIRU-OP/Kirugram.git@2.2.27" in start_script
    assert "--force-reinstall --no-cache-dir" in start_script
    assert "Kirugram 2.2.27 and PyTgCalls compatibility OK" in start_script
    assert "import kirugram" in start_script


def test_pytgcalls_accepts_kirugram_client():
    import kirugram
    from pytgcalls import PyTgCalls

    client = kirugram.Client("kirugram-pytgcalls-test", 12345, "0" * 32)
    calls = PyTgCalls(client)

    assert calls is not None
