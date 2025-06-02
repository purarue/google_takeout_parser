import csv
import json
import io
from pathlib import Path
from typing import List, TextIO, Iterator, Literal, Union, Any, Dict

from .models import CSVYoutubeComment, CSVYoutubeLiveChat
from .common import Res
from .time_utils import parse_json_utc_date


def _parse_youtube_comment_row(row: Dict[str, Any]) -> Res[CSVYoutubeComment]:
    try:
        comment_id = row["Comment ID"]
        channel_id = row["Channel ID"]
        created_at = row["Comment create timestamp"]
        price = row["Price"]
        parent_comment_id = row["Parent comment ID"]
        video_id = row["Video ID"]
        textJSON = row["Comment text"]
    except KeyError as e:
        return e
    return CSVYoutubeComment(
        commentId=comment_id,
        channelId=channel_id,
        dt=parse_json_utc_date(created_at),
        price=price,
        parentCommentId=parent_comment_id if parent_comment_id.strip() else None,
        videoId=video_id,
        # for now just pass the contents of the message as JSON forwards,
        # will add helpers that let the user access it in different ways programmatically
        # instead of trying to define every access pattern in a model
        contentJSON=textJSON,
    )


def is_empty_row(row: List[str]) -> bool:
    if len(row) == 0:
        return True
    for item in row:
        if item.strip():
            return False
    return True


def _parse_youtube_comments_buffer(buf: TextIO) -> Iterator[Res[CSVYoutubeComment]]:
    reader = csv.DictReader(buf)
    for row in reader:
        yield _parse_youtube_comment_row(row)


def _parse_youtube_comments_csv(path: Path) -> Iterator[Res[CSVYoutubeComment]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        yield from _parse_youtube_comments_buffer(f)


# Live Chat ID,Channel ID,Live Chat Create Timestamp,Price,Video ID,Live Chat Text


def _parse_youtube_live_chat_row(row: List[str]) -> Res[CSVYoutubeLiveChat]:
    try:
        (
            live_chat_id,
            channel_id,
            created_at,
            price,
            video_id,
            textJSON,
        ) = row
    except ValueError as e:
        return e
    return CSVYoutubeLiveChat(
        liveChatId=live_chat_id,
        channelId=channel_id,
        dt=parse_json_utc_date(created_at),
        price=price,
        videoId=video_id,
        contentJSON=textJSON,
    )


def _parse_youtube_live_chats_buffer(
    buf: TextIO,
    skip_first: bool = True,
) -> Iterator[Res[CSVYoutubeLiveChat]]:
    reader = csv.reader(buf)
    if skip_first:
        next(reader)
    for row in reader:
        if is_empty_row(row):
            continue
        if len(row) != 6:
            yield ValueError(f"Expected 6 columns, got {len(row)}: {row}")
            continue
        yield _parse_youtube_live_chat_row(row)


def _parse_youtube_live_chats_csv(path: Path) -> Iterator[Res[CSVYoutubeLiveChat]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        yield from _parse_youtube_live_chats_buffer(f)


CSVOutputFormat = Literal["text", "markdown"]


def _validate_content(content: Union[str, Dict[Any, Any]]) -> Res[List[Dict[str, Any]]]:
    if isinstance(content, str) and content.startswith('{"text":"'):
        # new format (since 2024)
        # this is a sequence of comma-separated serialized jsons...
        json_end = '"}'
        json_start = '{"'
        split = content.split(json_end + "," + json_start)
        segments = []
        for i, js in enumerate(split):
            if i != 0:
                js = json_start + js
            if i != len(split) - 1:
                js = js + json_end
            # we get \n as a result of csv parser... but json parser can't handle them!
            js = js.replace("\n", "\\n")
            segments.append(json.loads(js))
        return segments
    # old format

    if isinstance(content, dict):
        data = content
    else:
        if not isinstance(content, str):
            return ValueError(f"Expected str or dict, got {type(content)} {content}")  # type: ignore[unreachable]
        data = json.loads(content)
    if "takeoutSegments" not in data:
        return ValueError(f"Expected 'takeoutSegments' in content, got {data.keys()}")

    takeout_segments = data["takeoutSegments"]
    if not isinstance(takeout_segments, list):
        return ValueError(f"Expected a list, got {type(takeout_segments)}")

    return takeout_segments


def reconstruct_comment_content(
    content: Union[str, Dict[Any, Any]], format: CSVOutputFormat
) -> Res[str]:
    takeout_segments = _validate_content(content)
    if isinstance(takeout_segments, Exception):
        return takeout_segments
    if format == "text":
        buf = io.StringIO()
        for segment in takeout_segments:
            if "text" in segment:
                buf.write(segment["text"])
        return buf.getvalue()
    elif format == "markdown":
        buf = io.StringIO()
        for segment in takeout_segments:
            if "link" in segment and "linkUrl" in segment["link"]:
                if "text" in segment:
                    buf.write(f'[{segment["text"]}]({segment["link"]["linkUrl"]})')
                else:
                    buf.write(segment["link"]["linkUrl"])
            elif "text" in segment:
                buf.write(segment["text"])
            else:
                return ValueError(
                    f"Expected 'text' or 'link' in segment, got {segment}"
                )
        return buf.getvalue()
    else:
        # this is not a user-facing error, its misconfiguration, so we raise it
        raise ValueError(f"Unknown format {format}")


def extract_comment_links(content: Union[str, Dict[Any, Any]]) -> Res[List[str]]:
    takeout_segments = _validate_content(content)
    if isinstance(takeout_segments, Exception):
        return takeout_segments
    links = []
    for segment in takeout_segments:
        if "link" in segment and "linkUrl" in segment["link"]:
            links.append(segment["link"]["linkUrl"])
    return links
