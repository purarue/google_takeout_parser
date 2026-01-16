from google_takeout_parser.path_dispatch import TakeoutParser
from google_takeout_parser.locales.main import LOCALES

from .common import testdata


def test_structure() -> None:
    recent_takeout = testdata / "RecentTakeout"
    assert recent_takeout.exists()
    files = [f for f in recent_takeout.rglob("*") if f.is_file()]
    tk = TakeoutParser(recent_takeout)
    m = tk.dispatch_map()
    assert len(files) == 53
    assert len(m) == 35

    assert tk._guess_locale_order(takeout_dir=tk.takeout_dir) == [
        LOCALES["EN"],
        LOCALES["DE"],
    ]


def test_structure_ger() -> None:
    recent_takeout = testdata / "RecentTakeout_ger"
    assert recent_takeout.exists()
    files = [f for f in recent_takeout.rglob("*") if f.is_file()]
    tk = TakeoutParser(recent_takeout, locale_name="de")
    m = tk.dispatch_map()
    assert len(files) == 148
    assert len(m) == 19

    assert tk._guess_locale_order(takeout_dir=tk.takeout_dir) == [
        LOCALES["DE"],
        LOCALES["EN"],
    ]
