import os
import logging
import shutil
import time
import tempfile
import zipfile
from typing import List, Optional, Callable, Sequence, Any

import click

from . import log
from .cache import takeout_cache_path
from .common import Res
from .path_dispatch import TakeoutParser
from .models import BaseEvent, DEFAULT_MODEL_TYPE
from .merge import cached_merge_takeouts, merge_events


@click.group()
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
    if verbose is not None:
        if verbose:
            log.logger = log.setup(level=logging.DEBUG)
        else:
            log.logger = log.setup(level=logging.ERROR)


SHARED = [
    click.option("--cache/--no-cache", default=False, show_default=True),
    click.option(
        "-a",
        "--action",
        type=click.Choice(["repl", "summary"]),
        default="repl",
        help="What to do with the parsed result",
        show_default=True,
    ),
]


# decorator to apply shared arguments to inspect/merge
def shared_options(func: Callable[..., None]) -> Callable[..., None]:
    for decorator in SHARED:
        func = decorator(func)
    return func


def _handle_action(res: List[Any], action: str) -> None:
    if action == "repl":
        import IPython  # type: ignore[import]

        click.echo(f"Interact with the export using {click.style('res', 'green')}")
        IPython.embed()
    else:
        from collections import Counter
        from pprint import pformat

        click.echo(pformat(Counter([type(t).__name__ for t in res])))


@main.command(short_help="parse a takeout directory")
@shared_options
@click.argument("TAKEOUT_DIR", type=click.Path(exists=True), required=True)
def parse(cache: bool, action: str, takeout_dir: str) -> None:
    """
    Parse a takeout directory takeout
    """
    tp = TakeoutParser(takeout_dir, error_policy="drop")
    # note: actually no exceptions since since they're dropped
    res: List[Res[BaseEvent]] = list(tp.parse(cache=cache))
    _handle_action(res, action)


@main.command(short_help="merge multiple takeout directories")
@shared_options
@click.argument("TAKEOUT_DIR", type=click.Path(exists=True), nargs=-1, required=True)
def merge(cache: bool, action: str, takeout_dir: Sequence[str]) -> None:
    """
    Parse and merge multiple takeout directories
    """
    res: List[DEFAULT_MODEL_TYPE] = []
    if cache:
        res = list(cached_merge_takeouts(takeout_dir))
    else:
        res = list(merge_events(*iter([TakeoutParser(p).parse(cache=False) for p in takeout_dir])))  # type: ignore[arg-type]
    _handle_action(res, action)


@main.group(
    name="cache_dir", invoke_without_command=True, short_help="interact with cache dir"
)
@click.pass_context
def cache_dir(ctx: click.Context) -> None:
    """
    Print location of cache dir
    """
    if ctx.invoked_subcommand is None:
        click.echo(str(takeout_cache_path.absolute()))


@cache_dir.command(name="clear")
def cache_dir_remove() -> None:
    """
    Remove the cache directory
    """
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
    click.echo(f"Moving {from_} to {to}")
    assert os.path.exists(from_)
    assert not os.path.exists(to)
    shutil.move(from_, to)


if __name__ == "__main__":
    main(prog_name="google_takeout_parser")
