"""
This file loads and parses files according to a localized HandlerMap
"""

import os
import re
from pathlib import Path
from typing import (
    Callable,
    Any,
    Optional,
    Union,
    Literal,
    Iterator,
    Iterable,
    Sequence,
)
from re import Pattern

from collections import defaultdict

from cachew import cachew

from . import __version__ as _google_takeout_version
from .common import Res, PathIsh

from .locales.common import BaseResults, HandlerFunction, HandlerMap
from .locales.main import LOCALES, get_paths_for_functions


from .cache import takeout_cache_path
from .log import logger
from .models import BaseEvent, get_union_args


CacheKey = tuple[type[BaseEvent], ...]


FilterType = Union[
    None,
    type[BaseEvent],
    Sequence[type[BaseEvent]],
]


def _cache_key_to_str(c: CacheKey) -> str:
    """Convert a cache key to a string"""
    return "_".join(sorted(p.__name__ for p in c)).casefold()


def _handler_type_cache_key(handler: HandlerFunction) -> CacheKey:
    # Take a function like Iterator[Union[Item, Exception]] and return Item

    import inspect

    sig = inspect.signature(handler)

    # get the return type of the function
    # e.g. Iterator[Union[Item, Exception]]
    return_type = sig.return_annotation

    # this must have a return type
    if return_type == inspect.Signature.empty:
        raise TypeError(f"Could not get return type for {handler.__name__}")

    # remove top-level iterator if it has it
    if return_type._name == "Iterator":
        return_type = return_type.__args__[0]

    args: Optional[tuple[type]] = get_union_args(return_type)  # type: ignore[type-arg]
    if args is None:
        raise TypeError(
            f"Could not get union args for {return_type} in {handler.__name__}"
        )

    # remove exceptions
    t_args = tuple(t for t in args if t != Exception)

    for t in t_args:
        if BaseEvent not in t.__mro__:
            raise TypeError(
                f"Return type {t} from {return_type} of {handler.__name__} does not contain BaseEvent"
            )
        if t == BaseEvent:
            raise TypeError(
                f"Return type {t} from {return_type} of {handler.__name__} is BaseEvent, which is not allowed"
            )

    return tuple(t_args)


def _cache_key_to_type(c: CacheKey) -> Any:
    """
    If there's one item in the cache key, return that
    If there's multiple, return a Union of them
    """
    assert len(c) > 0
    if len(c) == 1:
        return c[0]
    else:
        assert isinstance(c, tuple)

        return Union[c]  # type: ignore[valid-type]


HandlerMatch = Res[Optional[HandlerFunction]]

ErrorPolicy = Literal["yield", "raise", "drop"]


def _handler_map_to_list(
    passed_locale_map: Union[HandlerMap, list[HandlerMap], None],
) -> list[HandlerMap]:
    """
    converts user input to a list of handler maps
    """
    handlers: list[HandlerMap] = []
    if passed_locale_map is not None:
        if isinstance(passed_locale_map, Sequence):
            for h in passed_locale_map:
                assert isinstance(h, dict), f"Expected dict, got {type(h)}"
                handlers.append(h)
        elif isinstance(passed_locale_map, dict):
            handlers = [passed_locale_map]
        else:
            raise TypeError(
                f"Expected dict or list of dicts, got {type(passed_locale_map)}"
            )
    return handlers


class TakeoutParser:
    def __init__(
        self,
        takeout_dir: PathIsh,
        cachew_identifier: Optional[str] = None,
        locale_name: Optional[str] = None,
        handlers: Union[HandlerMap, list[HandlerMap], None] = None,
        warn_exceptions: bool = True,
        error_policy: ErrorPolicy = "yield",
    ) -> None:
        """
        takeout_dir: Path to the google takeout directory
        cachew_identifier: some unique string that identifies this takeout
            If not given, approximates using the full path. Useful if you're
            temporarily extracting the zipfile to extract events or if the
            Takeout dir path isn't at its regular location
        locale_name:
            The name of the locale to use. See locales/all.py for predefined locales.
        handlers: 0-n handlers resolving Paths to a parser-functions.
            A handler can either resolve a path to a callable function which parses the path,
            or .
            See locales/all.py for predefined handlers.
            Default to 'EN', if not overridden by the user or by
            'GOOGLE_TAKEOUT_PARSER_LOCALE' environment variable.
        error_policy: How to handle exceptions while parsing:
            "yield": return as part of the results (default)
            "raise": raise exceptions
            "drop": drop/ignore exceptions
        """
        # isinstance check to avoid messing up objects which mimic Path (e.g. zip wrappers)
        takeout_dir = (
            takeout_dir if isinstance(takeout_dir, Path) else Path(takeout_dir)
        )
        self.takeout_dir = takeout_dir.absolute()
        if not self.takeout_dir.exists():
            raise FileNotFoundError(f"{self.takeout_dir} does not exist!")
        self.cachew_identifier: Optional[str] = cachew_identifier

        self.error_policy: ErrorPolicy = error_policy
        self.warn_exceptions = warn_exceptions
        self.handlers = self._resolve_locale_handler_map(
            takeout_dir=self.takeout_dir,
            locale_name=locale_name,
            passed_locale_map=handlers,
        )

    @classmethod
    def _resolve_locale_handler_map(
        cls,
        *,
        takeout_dir: Path,
        locale_name: Optional[str],
        passed_locale_map: Union[HandlerMap, list[HandlerMap], None] = None,
    ) -> list[HandlerMap]:
        # any passed locale map overrides the environment variable, this would only
        # really be done by someone calling this manually in python
        handlers = _handler_map_to_list(passed_locale_map)
        if len(handlers) > 0:
            return handlers

        # if no locale is specified, use the environment variable
        if locale_name is None:
            locale_name = os.environ.get("GOOGLE_TAKEOUT_PARSER_LOCALE")

        if locale_name is not None:
            logger.debug(f"User specified locale: {locale_name}")

        if locale_name is not None and locale_name in LOCALES:
            logger.debug(
                f"Using locale {locale_name}. To override set, GOOGLE_TAKEOUT_PARSER_LOCALE"
            )
            return [LOCALES[locale_name]]

        # if not provided, guess by using the dispatch map with all known handlers,
        # using the one with the maximum number of matches
        return cls._guess_locale(takeout_dir=takeout_dir)

    @classmethod
    def _guess_locale(
        cls,
        *,
        takeout_dir: Path,
    ) -> list[HandlerMap]:
        logger.debug(
            "No locale specified, guessing based on how many filepaths match from each locale"
        )
        locale_scores: dict[str, int] = {
            locale_name: len(
                cls._dispatch_map_pure(
                    takeout_dir=takeout_dir,
                    handler_maps=[locale_map],
                    warn_exceptions=False,  # dont warn here, we expect a bunch of path misses
                )
            )
            for locale_name, locale_map in LOCALES.items()
        }

        logger.debug(f"Locale scores: {locale_scores}")

        # if there's multiple max values, return both of them
        max_score = max(locale_scores.values())

        matched_locales = [
            name for name, score in locale_scores.items() if score == max_score
        ]

        logger.debug(f"Using locales: {matched_locales}")

        return [LOCALES[name] for name in matched_locales]

    def _warn_if_no_activity(self) -> None:
        expect_one_of = get_paths_for_functions()

        logger.debug(f"Trying to match one of: {expect_one_of}")

        path_names = [p.name for p in self.takeout_dir.iterdir()]

        for activity_dir in expect_one_of:
            # match regex path
            for p in path_names:
                if re.match(activity_dir, str(p)):
                    logger.debug(f"Matched expected directory: {activity_dir}")
                    return

        logger.warning(
            f"Warning: given '{self.takeout_dir}', expected one of '{expect_one_of}' to exist, perhaps you passed the wrong location?"
        )

    @staticmethod
    def _match_handler(
        relative_path: str,
        handler: Iterable[tuple[Pattern[str], Optional[HandlerFunction]]],
    ) -> HandlerMatch:
        """
        Match one of the handler regexes to a function which parses the file
        """
        # replace OS-specific (e.g. windows) path separator to match the handler
        sf = relative_path.replace(os.sep, "/")
        for prefix_re, h in handler:
            # regex match the map (e.g. above)
            if prefix_re.match(sf) is not None:
                # could be None, if chosen to ignore
                if h is None:
                    return None
                elif callable(h):
                    return h
        else:
            return RuntimeError(f"No function to handle parsing {sf}")

    def dispatch_map(self) -> dict[Path, HandlerFunction]:
        return self._dispatch_map_pure(
            takeout_dir=self.takeout_dir,
            handler_maps=self.handlers,
            warn_exceptions=self.warn_exceptions,
        )

    @classmethod
    def _dispatch_map_pure(
        cls,
        *,
        takeout_dir: Path,
        handler_maps: list[HandlerMap],
        warn_exceptions: bool = True,
    ) -> dict[Path, HandlerFunction]:
        """
        A pure function for dispatch map so it can be used in other contexts (e.g. to detect locales by scanning the directory)
        """

        # precompile regexes to avoid compiling every time we try to match a file
        # normally re.match caches them, but it's an lru cache, so we overwhelm it with so many handlers/locales
        compiled_handlers = [
            [(re.compile(prefix), handler) for prefix, handler in handler_map.items()]
            for handler_map in handler_maps
        ]

        def iter_relative_paths() -> Iterator[str]:
            # we use walk rather than .glob to avoid instantiating too many Path objects
            # many of them will get rejected by the regexes in handlers anyway

            takeout_dir_walk: Callable[..., Iterator[tuple[Path, list[str], list[str]]]]
            if hasattr(takeout_dir, "walk"):
                # this codepath is used from python 3.12 that has Path.walk
                # , or other implementations that support it (e.g. zipfile wrappers)
                takeout_dir_walk = takeout_dir.walk
            else:

                def takeout_dir_walk() -> Iterator[tuple[Path, list[str], list[str]]]:
                    for root, dirs, files in os.walk(takeout_dir):
                        yield Path(root), dirs, files

            for root, dirs, files in takeout_dir_walk():
                dirs.sort()
                files.sort()

                # compute relative path of parent dir once, this saves a lot of time when takeout has tens of thousands of files
                root_relative = root.relative_to(takeout_dir)
                for f in files:
                    if f[0] == ".":
                        continue
                    yield os.path.join(root_relative, f)

        res: dict[Path, HandlerFunction] = {}
        for rf in iter_relative_paths():
            # try to resolve file to parser-function by checking all supplied handlers

            # cache handler information for warning if we can't resolve the file
            file_resolved: bool = False
            handler_exception: Optional[Exception] = None

            for compiled_handler in compiled_handlers:
                file_handler: HandlerMatch = cls._match_handler(rf, compiled_handler)
                # file_handler matched something
                if not isinstance(file_handler, Exception):
                    # if not explicitly ignored by the handler map
                    if file_handler is not None:
                        f = takeout_dir / rf
                        res[f] = file_handler
                    file_resolved = True
                    break  # file was handled, don't check other HandlerMaps
                else:
                    handler_exception = file_handler

            if not file_resolved:
                # this is an exception specifying an unhandled file
                # this shouldn't cause a fatal error, so don't check
                # error_policy here, just warn the user
                if warn_exceptions:
                    logger.warning(str(handler_exception))

        return res

    def _log_handler(self, path: Path, handler: Any) -> None:
        """Log the path/function parsing it"""
        rel_path = str(path)[len(str(self.takeout_dir)) + 1 :]
        func_name: str = getattr(handler, "__name__", str(handler))
        logger.info(f"Parsing '{rel_path}' using '{func_name}'")

    def _parse_raw(self, filter_type: FilterType = None) -> BaseResults:
        """Parse the takeout with no cache. If a filter is specified, only parses those files"""
        handlers = self._group_by_return_type(filter_type=filter_type)
        for _, result_tuples in handlers.items():
            for path, itr in result_tuples:
                self._log_handler(path, itr)
                yield from itr

    def _handle_errors(self, results: BaseResults) -> BaseResults:
        """Wrap the results and handle any errors according to the policy"""
        for e in results:
            if not isinstance(e, Exception):
                yield e
            else:
                if self.warn_exceptions:
                    logger.warning(str(e))
                # return errors as part of the result, default
                if self.error_policy == "yield":
                    yield e
                # raise errors; crash
                elif self.error_policy == "raise":
                    raise e
                # ignore errors
                elif self.error_policy == "drop":
                    continue

    def parse(self, cache: bool = False, filter_type: FilterType = None) -> BaseResults:
        """
        Parses the Takeout

        if cache is True, using cachew to cache the results
        if filter_type is given, only parses the files which have that type
        """
        if not cache:
            yield from self._handle_errors(self._parse_raw(filter_type=filter_type))
        else:
            yield from self._handle_errors(self._cached_parse(filter_type=filter_type))

    def _group_by_return_type(
        self, filter_type: FilterType = None
    ) -> dict[CacheKey, list[tuple[Path, BaseResults]]]:
        """
        Groups the dispatch_map by output model type
        If filter_type is provided, only returns that Model

        e.g.:

        Activity -> [
            (filepath, iterator that produces activity)
            (filepath, iterator that produces activity),
            (filepath, iterator that produces activity),
        ]
        """
        handlers: dict[CacheKey, list[tuple[Path, BaseResults]]] = defaultdict(list)
        ftype: list[type[BaseEvent]] = []
        if filter_type is not None:
            if isinstance(filter_type, Sequence):
                ftype = list(filter_type)
            else:
                ftype = [filter_type]
        for path, handler in self.dispatch_map().items():
            ckey: CacheKey = _handler_type_cache_key(handler)
            # don't include in the result if we're filtering to a specific type
            if len(ftype) and all(t not in ftype for t in ckey):
                logger.debug(
                    f"Provided '{ftype}' as filter, '{ckey}' doesn't match, ignoring '{path}'..."
                )
                continue
            # call the function -- since the parsers are all generators,
            # this doesn't run here, it just waits till its consumed
            handlers[ckey].append((path, handler(path)))
        return dict(handlers)

    def _depends_on(self) -> str:
        """
        basename of all files in the takeout directory + google_takeout_version version
        """
        file_index: list[str] = list(
            sorted([str(p.name) for p in self.takeout_dir.rglob("*")])
        )
        # store version at the beginning of hash
        # if pip version changes, invalidates old results and re-computes
        file_index.insert(0, f"google_takeout_version: {_google_takeout_version}")
        return str(file_index)

    def _determine_cache_path(self, cache_key: CacheKey) -> str:
        """
        Create the unique cachew database path for this TakeoutParser instance
        """
        base = takeout_cache_path
        part: str
        if self.cachew_identifier is not None:
            part = self.cachew_identifier
        else:
            # use a full-ish path of the takeout dir to create a unique identifier
            part = os.path.join(*self.takeout_dir.parts[1:])
        return str(base / part / _cache_key_to_str(cache_key))

    def _cached_parse(self, filter_type: FilterType = None) -> BaseResults:
        handlers = self._group_by_return_type(filter_type=filter_type)
        for cache_key, result_tuples in handlers.items():
            _ret_type: Any = _cache_key_to_type(cache_key)

            def _func() -> Iterator[Res[_ret_type]]:  # type: ignore[valid-type]
                for path, itr in result_tuples:
                    self._log_handler(path, itr)
                    yield from itr

            cached_itr: Callable[[], BaseResults] = cachew(
                depends_on=lambda: self._depends_on(),
                cache_path=lambda: self._determine_cache_path(cache_key),
                force_file=True,
                logger=logger,
            )(_func)

            yield from cached_itr()
