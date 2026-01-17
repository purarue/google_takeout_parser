from pathlib import Path
from collections.abc import Callable, Iterator

from ..models import BaseEvent, Res
from ..parse_html.activity import _parse_html_activity  # noqa: F401
from ..parse_html.comment import _parse_html_comment_file  # noqa: F401
from ..parse_json import (  # noqa: F401
    _parse_likes,
    _parse_app_installs,
    _parse_json_activity,
    _parse_location_history,
    _parse_semantic_location_history,
    _parse_chrome_history,
    _parse_keep,
)
from ..parse_csv import (  # noqa: F401
    _parse_youtube_comments_csv,
    _parse_youtube_live_chats_csv,
)

BaseResults = Iterator[Res[BaseEvent]]

HandlerFunction = Callable[[Path], BaseResults]
HandlerMap = dict[str, HandlerFunction | None]
