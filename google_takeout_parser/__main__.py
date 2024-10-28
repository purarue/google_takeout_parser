import os
import json
from datetime import datetime, date
import dataclasses
from typing import List, Optional, Callable, Sequence, Any, Dict, Type, Tuple

import click


@click.group(
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120}
)
@click.option(
    "--verbose/--quiet",
    default=None,
    is_flag=True,
    show_default=True,
    help="Change default log level",
)
def main(verbose: Optional[bool]) -> None:
    """
    Parse a google takeout!
    """
    import logging

    from . import log

    if verbose is not None:
        if verbose:
            log.logger = log.setup(level=logging.DEBUG)
        else:
            log.logger = log.setup(level=logging.ERROR)


# use the union of types to determine the possible filters
from .models import DEFAULT_MODEL_TYPE, get_union_args

model_types: Optional[Tuple[Type[DEFAULT_MODEL_TYPE]]] = get_union_args(
    DEFAULT_MODEL_TYPE
)
assert model_types is not None

FILTER_OPTIONS: Dict[str, Type[DEFAULT_MODEL_TYPE]] = {
    t.__name__: t for t in model_types
}

from .locales.all import LOCALES

SHARED = [
    click.option("--cache/--no-cache", default=False, show_default=True),
    click.option(
        "-a",
        "--action",
        type=click.Choice(["repl", "summary", "json"], case_sensitive=False),
        default="repl",
        help="What to do with the parsed result",
        show_default=True,
    ),
    click.option(
        "-l",
        "--locale",
        type=click.Choice(LOCALES, case_sensitive=False),
        default=None,
        help="Locale to use for matching filenames [default: EN]",
        show_default=True,
        envvar="GOOGLE_TAKEOUT_PARSER_LOCALE",
        show_envvar=True,
    ),
    click.option(
        "-f",
        "--filter",
        "filter_",
        type=click.Choice(list(FILTER_OPTIONS.keys()), case_sensitive=False),
        multiple=True,
        help="Filter to only show events of this type. Can be provided multiple times",
    ),
]


# decorator to apply shared arguments to inspect/merge
def shared_options(func: Callable[..., None]) -> Callable[..., None]:
    for decorator in SHARED:
        func = decorator(func)
    return func


def _serialize_default(obj: Any) -> Any:
    if isinstance(obj, Exception):
        return {"type": type(obj).__name__, "value": str(obj)}
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        d = dataclasses.asdict(obj)  # type: ignore[call-overload]  # see https://github.com/python/mypy/issues/17550
        assert "type" not in d
        d["type"] = type(obj).__name__
        return d
    elif isinstance(obj, datetime):
        return str(obj)
    elif isinstance(obj, date):
        return str(obj)
    raise TypeError(f"No known way to serialize {type(obj)} '{obj}'")


def _handle_action(res: List[Any], action: str) -> None:
    if action == "repl":
        import IPython  # type: ignore[import]

        click.echo(f"Interact with the export using {click.style('res', 'green')}")
        IPython.embed()  # type: ignore[no-untyped-call]
    elif action == "json":
        click.echo(json.dumps(res, default=_serialize_default))
    else:
        from collections import Counter
        from pprint import pformat

        click.echo(pformat(Counter([type(t).__name__ for t in res])))


@main.command(short_help="parse a takeout directory")
@shared_options
@click.argument("TAKEOUT_DIR", type=click.Path(exists=True), required=True)
def parse(
    cache: bool,
    locale: Optional[str],
    action: str,
    takeout_dir: str,
    filter_: Sequence[str],
) -> None:
    """
    Parse a takeout directory takeout
    """
    from .path_dispatch import TakeoutParser
    from .log import logger

    tp = TakeoutParser(
        takeout_dir,
        error_policy="drop",
        locale_name=locale,
    )
    tp._warn_if_no_activity()
    filter_type = tuple(FILTER_OPTIONS[ff] for ff in filter_)
    # note: actually no exceptions since since they're dropped
    if cache:
        if filter_:
            logger.warn(
                "As it would otherwise re-compute every time, filtering happens after loading from cache"
            )
        res = list(tp.parse(cache=True))
        if filter_:
            res = [r for r in res if isinstance(r, filter_type)]
    else:
        res = list(tp.parse(cache=False, filter_type=filter_type))
    _handle_action(res, action)


@main.command(short_help="merge multiple takeout directories")
@shared_options
@click.argument("TAKEOUT_DIR", type=click.Path(exists=True), nargs=-1, required=True)
def merge(
    cache: bool,
    locale: Optional[str],
    action: str,
    takeout_dir: Sequence[str],
    filter_: Sequence[str],
) -> None:
    """
    Parse and merge multiple takeout directories
    """
    from .path_dispatch import TakeoutParser
    from .merge import cached_merge_takeouts, merge_events
    from .models import DEFAULT_MODEL_TYPE, Res
    from .log import logger

    res: List[Res[DEFAULT_MODEL_TYPE]] = []
    filter_type = tuple(FILTER_OPTIONS[ff] for ff in filter_)
    if cache:
        if filter_:
            logger.warn(
                "As it would otherwise re-compute every time, filtering happens after loading from cache"
            )
        res = list(cached_merge_takeouts(list(takeout_dir), locale_name=locale))
        if filter_:
            res = [r for r in res if isinstance(r, filter_type)]
    else:
        res = list(
            merge_events(
                *iter(  # type: ignore
                    [
                        TakeoutParser(p, locale_name=locale).parse(
                            cache=False,
                            filter_type=filter_type,
                        )
                        for p in takeout_dir
                    ]
                )
            )
        )
    _handle_action(res, action)


@main.group(
    name="cache_dir", invoke_without_command=True, short_help="interact with cache dir"
)
@click.pass_context
def cache_dir(ctx: click.Context) -> None:
    """
    Print location of cache dir
    """
    from .cache import takeout_cache_path

    if ctx.invoked_subcommand is None:
        click.echo(str(takeout_cache_path.absolute()))


@cache_dir.command(name="clear")
def cache_dir_remove() -> None:
    """
    Remove the cache directory
    """
    import shutil
    from .cache import takeout_cache_path

    click.echo(str(takeout_cache_path))
    click.echo("Contents:")
    for f in takeout_cache_path.rglob("*"):
        print(f"\t{str(f)}")
    if click.confirm("Really remove this directory?"):
        shutil.rmtree(str(takeout_cache_path))


@main.command(name="move", short_help="move new google takeouts")
@click.option(
    "--from",
    "from_",
    required=True,
    help="Google takeout zip file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--to-dir",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True, exists=True),
    help="Directory which contains your Takeout files",
)
@click.option(
    "--extract/--no-extract",
    required=False,
    default=True,
    help="Whether or not to extract the zipfile",
)
def move(from_: str, to_dir: str, extract: bool) -> None:
    """
    Utility command to help move/extract takeouts into the correct location
    """
    import time
    import tempfile
    import zipfile

    ts = int(time.time())
    target = f"{to_dir}/Takeout-{ts}"
    if not extract:
        target += ".zip"
        _safe_shutil_mv(from_, target)
    else:
        assert from_.endswith("zip")
        zf = zipfile.ZipFile(from_)
        with tempfile.TemporaryDirectory() as td:
            click.echo(f"Extracting {from_} to {td}")
            zf.extractall(path=td)
            top_level = [f for f in os.listdir(td) if not f.startswith(".")]
            if len(top_level) == 1 and top_level[0].lower().startswith("takeout"):
                from_ = os.path.join(td, top_level[0])
                _safe_shutil_mv(from_, target)
            else:
                raise RuntimeError(
                    f"Expected top-level 'Takeout' folder in extracted folder, contents are {top_level}"
                )


def _safe_shutil_mv(from_: str, to: str) -> None:
    import shutil

    click.echo(f"Moving {from_} to {to}")
    assert os.path.exists(from_)
    assert not os.path.exists(to)
    shutil.move(from_, to)


if __name__ == "__main__":
    main(prog_name="google_takeout_parser")
