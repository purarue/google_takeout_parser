"""
Parses the HTML MyActivity.html files that used to be the standard
"""

from pathlib import Path
from datetime import datetime
from collections.abc import Iterator, Iterable
from urllib.parse import urlparse, parse_qs

import bs4
from bs4.element import Tag, PageElement

from ..models import Activity, Subtitles, LocationInfo
from ..common import Res
from ..log import logger
from ..http_allowlist import convert_to_https_opt
from .html_time_utils import parse_html_dt


def clean_latin1_chars(s: str) -> str:
    # these are latin1 encoded space characters, replace them with spaces
    return s.replace("\xa0", " ").replace("\u2003", " ")


TextOrEl = bs4.element.Tag | bs4.element.NavigableString | str
ListOfTags = list[list[TextOrEl]]


def _group_by_brs(els: Iterable[PageElement]) -> ListOfTags:
    """
    splits elements (children of some top-level div)
    into groups of elements, separated by 'br' elements

    we want to split by lines which have '<br/>' elements, since
    it can contain URLs whose link text contains both text and
    a URL we want
    """
    res: ListOfTags = []
    cur: list[TextOrEl]
    cur = []
    for tag in els:
        if isinstance(tag, bs4.element.NavigableString):
            cur.append(tag)
        elif isinstance(tag, str):
            cur.append(tag)
        elif isinstance(tag, bs4.element.Tag):
            # is a bs4.element.Tag
            if tag.name == "br":
                res.append(cur)
                cur = []
            else:
                cur.append(tag)
        else:
            logger.warning(
                f"While parsing subtitle {els}, found unexpected type: {type(tag)} {tag}"
            )
    if cur:
        res.append(cur)
    return res


def _parse_subtitles(
    subtitle_cell: bs4.element.Tag,
    *,
    file_dt: datetime | None,
) -> Res[tuple[list[Subtitles], datetime]]:
    parsed_subs: list[Subtitles] = []

    # iterate over direct children, and remove the last
    # one (the date)
    sub_children: list[PageElement] = list(subtitle_cell.children)
    dt_raw_el = sub_children.pop(-1)
    if not isinstance(dt_raw_el, str):
        return ValueError(
            f"Could not extract datetime (should be last element) from {subtitle_cell}"
        )
    dt_raw = dt_raw_el.strip()

    for group in _group_by_brs(sub_children):
        # loop vars
        buf: str = ""  # current text, till we hit a br (next group)
        url: str | None = None  # a URL, if this subtitle contains one

        for tag in group:
            if isinstance(tag, bs4.element.NavigableString):
                buf += str(tag)
            elif isinstance(tag, bs4.element.Tag):
                if tag.name == "a":
                    buf += str(tag.text)
                    if "href" in tag.attrs:
                        v = tag.attrs["href"]
                        if isinstance(v, str):
                            url = v
                        elif isinstance(v, list) and len(v) > 0:
                            url = v[0]
                        else:
                            assert (
                                False
                            ), f"Could not parse href into valid value, {type(v)} {v}"
                else:
                    logger.warning(f"Unexpected tag! {tag}")
            else:
                raise RuntimeError(f"Unexpected Type {tag} {type(tag)}")

        parsed_subs.append(
            Subtitles(name=clean_latin1_chars(buf), url=convert_to_https_opt(url))
        )

    return parsed_subs, parse_html_dt(dt_raw, file_dt=file_dt)


def _split_by_caption_headers(groups: ListOfTags) -> dict[str, ListOfTags]:
    """
    Captions are structured like:

    head1:
        value1
    head2:
        value2
        value3
    {
        "head1": [value1],
        "head2": [value2, value]
    }
    """

    k = ""
    res: dict[str, ListOfTags] = {}
    vals: ListOfTags = []

    for g in groups:
        possible_key = g[0]
        # keys look like [<b>Products:</b>]
        if (
            isinstance(possible_key, bs4.element.Tag)
            and possible_key.name == "b"
            and possible_key.text.endswith(":")
        ):
            # if we already have data, add that to the result
            if k:
                res[k] = vals
                vals = []
            k = possible_key.text.strip()
        else:
            # add non-header key to values
            assert (
                k
            ), f"While parsing caption; Found value while key has no value {groups}"
            vals.append(g)

    # add last key/val pair
    if vals:
        res[k] = vals

    return res


COMMON_GMAPS_QUERY_PARAMS = {
    "api",
    "map_action",
    "center",
    "zoom",
}


def _is_location_api_link(url: str) -> bool:
    query_params = parse_qs(urlparse(url).query)
    query_match_count = [
        param in query_params for param in COMMON_GMAPS_QUERY_PARAMS
    ].count(True)
    return query_match_count > 2


def _parse_caption(
    cap_cell: bs4.element.Tag,
) -> tuple[list[str], list[LocationInfo], list[str]]:
    details: list[str] = []
    locationInfos: list[LocationInfo] = []
    products: list[str] = []

    groups = _group_by_brs(list(cap_cell.children))

    split_groups = _split_by_caption_headers(groups)

    for header, values in split_groups.items():
        for value in values:
            if header == "Products:":
                products.append(clean_latin1_chars(str(value[0])).strip())
            elif header == "Locations:":
                # man...
                # so it seems that the name/url
                # and the source/sourceUrl come in pairs
                # because of how html works, there can be anywhere
                # from 2 to 5 elements here, so it seems its best to
                # convert the entire buffer of elements to text and URLs
                # and then use some logic to figure out what it is

                # if we have two, we can use the order and split by the hyphen
                # if we have one, check the url to see if its a specific sort
                # of google maps URL (e.g. https://www.google.com/maps/search/?api=1&query=...)
                # and if it is, use it as the name/url pair, else use the text
                # as the source

                name: str | None = None
                url: str | None = None
                source: str | None = None
                sourceUrl: str | None = None

                textbuf = ""
                links: list[str] = []

                for tag in value:
                    if isinstance(tag, bs4.element.NavigableString):
                        textbuf += str(tag)
                    elif isinstance(tag, bs4.element.Tag):
                        textbuf += str(tag.text)
                        if tag.name == "a" and "href" in tag.attrs:
                            vals = tag.attrs["href"]
                            if isinstance(vals, str):
                                links.append(vals)
                            else:
                                assert isinstance(
                                    vals, list
                                ), f"Expected value to be list or str, found {type(vals)} {vals}"
                                links.extend(vals)

                textbuf = clean_latin1_chars(textbuf).strip()

                if "-" in textbuf:
                    f, _, s = textbuf.partition("-")
                    name = f.strip()
                    source = s.strip()

                if len(links) == 2:
                    url = links[0]
                    sourceUrl = links[1]

                elif len(links) == 1:
                    if _is_location_api_link(links[0]):
                        url = links[0]
                        # wasn't set in partition above, was only one
                        # phrase of text
                        if name is None:
                            name = textbuf
                    else:
                        sourceUrl = links[0]
                        if source is None:
                            source = textbuf
                else:
                    # no links, just a description of the source
                    # (since there's no URL, can't be name)
                    source = textbuf

                locationInfos.append(
                    LocationInfo(
                        name=name,
                        url=convert_to_https_opt(url),
                        source=source,
                        sourceUrl=convert_to_https_opt(sourceUrl),
                    )
                )
            elif header == "Details:":
                details.append(str(clean_latin1_chars(str(value[0])).strip()))

            else:
                logger.warning(f"Unexpected header in caption {header} {value}")

    return details, locationInfos, products


def _parse_activity_div(
    div: bs4.element.Tag,
    *,
    file_dt: datetime | None,
) -> Res[Activity]:
    header_el = div.find("p", class_="mdl-typography--title")
    if header_el is None:
        return ValueError(f"Could not find header in {div}")
    header = header_el.text.strip()

    # all possible data that this div could parse
    dtime: datetime
    subtitles: list[Subtitles] = []  # more lines of text describing this
    details: list[str] = []
    locationInfos: list[LocationInfo] = []
    products: list[str] = []

    # cells in the div which contain the above information

    # has the main description/content and the datetime
    subtitle_cells: list[Tag] = []
    # has what product/extra info which this is related to
    caption_cells: list[Tag] = []

    # iterate over content-cells (contain all the info in this cell)
    # and categorize the cells. Pretty sure there should only be one
    # of each, but doing this to be safe
    for d in div.find_all(class_="content-cell"):
        div_classes = d.attrs["class"]
        # these are used for spacing on the right
        if "mdl-typography--text-right" in div_classes:
            continue
        # the main content cell -- the first item contains the title, and possible titleUrl
        # then after that, is the subtitles, which can contain text and possibly links
        elif "mdl-typography--body-1" in div_classes:
            subtitle_cells.append(d)
        # caption cells, optionally contains Products and Details, which contain lots of info
        # depending on the activity type
        elif "mdl-typography--caption" in div_classes:
            caption_cells.append(d)

    assert (
        len(subtitle_cells) == 1
    ), f"Expected one body cell in {div}, found {len(subtitle_cells)}"
    sub_cell = subtitle_cells[0]

    subs = _parse_subtitles(sub_cell, file_dt=file_dt)
    if isinstance(subs, Exception):
        return subs
    subtitles, dtime = subs

    assert (
        len(caption_cells) == 1
    ), f"Expected one body cell in {div}, found {len(subtitle_cells)}"
    cap_cell = caption_cells[0]

    details, locationInfos, products = _parse_caption(cap_cell)

    # the first subtitle is the title/titleUrl
    assert len(subtitles) >= 0, f"Could not extract a title from {div}"

    title_info = subtitles.pop(0)

    return Activity(
        header=header,
        title=title_info.name,
        # could be None, matched the JSON format
        titleUrl=convert_to_https_opt(title_info.url),
        description=None,  # always none since we can't differentiate in HTML parsing
        time=dtime,
        locationInfos=locationInfos,
        subtitles=subtitles,
        details=details,
        products=products,
    )


def _parse_html_activity(p: Path) -> Iterator[Res[Activity]]:
    file_dt = datetime.fromtimestamp(p.stat().st_mtime)
    data = p.read_text()

    def contains_outer_cell(cls: str | None) -> bool:
        return cls is not None and "outer-cell" in cls

    strainer = bs4.SoupStrainer(name="div", attrs={"class": contains_outer_cell})

    soup = bs4.BeautifulSoup(data, "lxml", parse_only=strainer)

    outer_divs: Iterable[bs4.element.Tag] = soup.children  # type: ignore[assignment]  # mypy can't guess they will actually be tags..
    for outer_div in outer_divs:
        try:
            yield _parse_activity_div(outer_div, file_dt=file_dt)
        except Exception as ae:
            yield ae
