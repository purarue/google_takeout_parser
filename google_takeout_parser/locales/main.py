from typing import List, Sequence, Optional

from .common import HandlerFunction
from .en import HANDLER_MAP as EN_DEFAULT_HANDLER_MAP
from .de import HANDLER_MAP as DE_DEFAULT_HANDLER_MAP

LOCALES = {
    "EN": EN_DEFAULT_HANDLER_MAP,
    "DE": DE_DEFAULT_HANDLER_MAP,
}


def get_paths_for_functions(
    functions: Optional[Sequence[HandlerFunction]] = None,
) -> List[str]:
    """
    returns the base directory name for which the json activity parses for every locale

    if functions are passed, uses those instead of the default ones

    for example, the EN path is:
    My Activity/Ads/MyActivity.json

    in german its
    Meine Aktivität/Werbung/MeineAktivität.json

    this will return ['My Activity', 'Meine Aktivität']

    this is used in HPI to find the correct directory to parse

    note: should probably remove whitespace as well, so like:

    ['My Activity', 'MyActivity', 'Meine Aktivität', 'MeineAktivität'] when testing against filepaths
    """
    from ..parse_json import (
        _parse_json_activity,
        _parse_location_history,
        _parse_chrome_history,
    )

    funcs: List[HandlerFunction] = (
        list(functions)
        if functions is not None
        else [_parse_json_activity, _parse_location_history, _parse_chrome_history]
    )

    paths = set()
    for handler_map in LOCALES.values():
        for path, match_func in handler_map.items():
            for function in funcs:
                if function == match_func:
                    # no need to use os.sep here since paths in handler map always use /
                    paths.add(path.split("/")[0])

    # sort to prevent behaviour changing based on available locales
    return sorted(paths)
