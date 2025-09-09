import inspect

import google_takeout_parser.models as mod
from google_takeout_parser.models import get_union_args


def test_check_union() -> None:
    """
    Makes sure that any classes defined in models are included in the union type

    sanity check test to ensure cachew doesn't fail with difficult to debug union/errors
    """

    classes = {
        v
        for _name, v in inspect.getmembers(mod, predicate=inspect.isclass)
        if mod.BaseEvent in v.__mro__ and v != mod.BaseEvent
    }
    ua = get_union_args(mod.DEFAULT_MODEL_TYPE)
    assert ua is not None
    union_args = set(ua)

    assert union_args == classes


def test_parsing_return_type() -> None:
    from typing import Union, Iterator
    from pathlib import Path
    from google_takeout_parser.path_dispatch import (
        _cache_key_to_str,
        _cache_key_to_type,
        _handler_type_cache_key,
    )
    from google_takeout_parser.models import Activity, Res, PlayStoreAppInstall

    def _test_func(path: Path) -> Iterator[Res[Activity]]:
        yield Exception("test")

    ret_type = _handler_type_cache_key(_test_func)
    assert ret_type is not None
    assert ret_type == (Activity,)
    assert _cache_key_to_str(ret_type) == "activity"
    assert _cache_key_to_type(ret_type) == Activity

    def _test_multiple(
        path: Path,
    ) -> Iterator[Res[Union[Activity, PlayStoreAppInstall]]]:
        yield Exception("test")

    ret_type = _handler_type_cache_key(_test_multiple)
    assert ret_type is not None
    assert ret_type == (Activity, PlayStoreAppInstall)
    assert _cache_key_to_str(ret_type) == "activity_playstoreappinstall"
    assert _cache_key_to_type(ret_type) == Union[Activity, PlayStoreAppInstall]


def test_locale_names() -> None:
    from google_takeout_parser.locales.main import LOCALES
    from google_takeout_parser.locales.all import LOCALES as ALL_LOCALES

    errmsg = "LOCALES in all.py/main.py must be the same length and have the same keys, you probably added a locale to one of these and not the other"

    assert set(LOCALES.keys()) == set(ALL_LOCALES), errmsg
