import re
from pathlib import Path
from collections.abc import Iterator
from datetime import datetime, timezone

import bs4

from ..models import YoutubeComment
from ..common import Res
from ..http_allowlist import convert_to_https
from .activity import _group_by_brs, clean_latin1_chars

# seems to always be in UTC?
# new format:
# 2020-05-06 19:32:44 UTC
# old format (pre-2019?):
# 2016-06-15T08:50:49Z
COMMENT_DATE_REGEX = re.compile(
    r"([0-9]{4})\-([0-9]{2})\-([0-9]{2})(?:\s*|T)([0-9]{2})\:([0-9]{2})\:([0-9]{2})"
)

# for YoutubeComment
# can be in lots of formats
# sent at '...'
# on '....'
# probably just need to use regex


def _extract_html_li_date(comment: str) -> datetime:
    matches = re.search(COMMENT_DATE_REGEX, comment)
    if matches:
        g = matches.groups()
        year, month, day, hour, minute, second = tuple(map(int, g))
        return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    else:
        raise RuntimeError(f"Couldn't parse date from {comment}")


def _parse_html_li(li: bs4.element.Tag) -> YoutubeComment:
    parsed_date: datetime = _extract_html_li_date(li.text)
    groups = _group_by_brs(li.children)
    assert len(groups) == 2, f"Expected 2 parts separated by a <br /> {groups}"
    desc = ""
    for tag in groups[1]:
        if isinstance(tag, bs4.element.NavigableString):
            desc += str(tag)
        elif isinstance(tag, bs4.element.Tag):
            desc += str(tag.text)
    urls: list[str] = []
    for link in li.select("a"):
        if "href" in link.attrs:
            val = link.attrs["href"]
            if isinstance(val, str):
                urls.append(convert_to_https(val))
            else:
                assert isinstance(
                    val, list
                ), f"Expected href to be a str or list, found {type(val)} {val}"
                urls.extend(convert_to_https(cu) for cu in val)

    return YoutubeComment(
        content=clean_latin1_chars(desc).strip(), urls=urls, dt=parsed_date
    )


def _parse_html_comment_file(p: Path) -> Iterator[Res[YoutubeComment]]:
    soup = bs4.BeautifulSoup(p.read_text(), "lxml")
    for li in soup.select("li"):
        try:
            yield _parse_html_li(li)
        except Exception as e:
            yield e


def test_parse_html_comment_file() -> None:
    li_obj = bs4.BeautifulSoup(
        """<ul><li>Sent at 2020-04-27 23:18:23 UTC while watching <a href="http://www.youtube.com/watch?v=mM">a video</a>.<br/>content here</li></ul>""",
        "lxml",
    ).select_one("li")
    assert li_obj is not None
    parsed_li = _parse_html_li(li_obj)
    assert parsed_li == YoutubeComment(
        content="content here",
        dt=datetime(2020, 4, 27, 23, 18, 23, tzinfo=timezone.utc),
        urls=["https://www.youtube.com/watch?v=mM"],
    )
