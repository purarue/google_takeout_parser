"""
Helper module to remove duplicate events when combining takeouts
"""

from itertools import chain
from typing import Set, Tuple, List, Any, Optional, Type


from cachew import cachew

from .log import logger
from .cache import takeout_cache_path
from .common import PathIsh
from .models import BaseEvent, CacheResults
from .path_dispatch import TakeoutParser

# hmm -- feel there are too many usecases to support
# everything here, so just need to document this a bit
# so is obvious how to use
#
# else Im just duplicating code that would exist in HPI anyways


# Note: only used for this module, HPI caches elsewhere
@cachew(
    cache_path=str(takeout_cache_path / "_merged_takeouts"),
    depends_on=lambda tp: str(list(sorted(str(p) for p in tp))),
    force_file=True,
    logger=logger,
)
def cached_merge_takeouts(
    takeout_paths: List[PathIsh], locale_name: Optional[str]
) -> CacheResults:
    """
    Cached version of merge events, merges each of these into one cachew database

    Additional arguments are passed to TakeoutParser constructor

    If your takeout directory was something like:

    $ /bin/ls ~/data/google_takeout -1
    Takeout-1599315526
    Takeout-1599728222
    Takeout-1616796262

    takeout_paths would be:
    ['Takeout-1599315526', 'Takeout-1616796262', 'Takeout-1599728222']
    """
    itrs: List[CacheResults] = []
    for pth in takeout_paths:
        tk = TakeoutParser(pth, warn_exceptions=True, locale_name=locale_name)
        # have to ignore type conversion here -- its returns BaseEvent,
        # while CacheResults is the combined Union type
        itrs.append(tk.parse(cache=True))  # type: ignore[misc,arg-type]
    yield from merge_events(*itrs)


# TODO: need to make sure that differences in format (HTML/JSON) don't result in duplicate events
def merge_events(*sources: CacheResults) -> CacheResults:
    """
    Given a bunch of iterators, merges takeout events together
    """
    emitted: GoogleEventSet = GoogleEventSet()
    count = 0
    for event in chain(*sources):
        count += 1
        if isinstance(event, Exception):
            yield event
            continue
        if event in emitted:
            continue
        emitted.add(event)
        yield event
    logger.debug(
        f"TakeoutParse merge: received {count} events, removed {count - len(emitted)} duplicates"
    )


Key = Tuple[Type[Any], Any]


def _create_key(e: BaseEvent) -> Key:
    return (type(e), e.key)


# This is so that its easier to use this logic in other
# places, e.g. in github.com/purarue/HPI
class GoogleEventSet:
    """
    Class to help manage keys for the models
    """

    def __init__(self) -> None:
        self.keys: Set[Key] = set()

    def __contains__(self, other: BaseEvent) -> bool:
        return _create_key(other) in self.keys

    def __len__(self) -> int:
        return len(self.keys)

    def add(self, other: BaseEvent) -> None:
        self.keys.add(_create_key(other))

    def add_if_not_present(self, other: BaseEvent) -> bool:
        """
        Returns False if element already existed, True if it didn't and we added it.
        More efficient than checking membership and adding separately, since we only compute key once.
        """
        key = _create_key(other)
        if key in self.keys:
            return False
        self.keys.add(key)
        return True
