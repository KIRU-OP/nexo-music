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
