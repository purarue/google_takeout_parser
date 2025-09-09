"""
Taken from https://github.com/karlicoss/HPI/blob/4a04c09f314e10a4db8f35bf1ecc10e4d0203223/my/core/time.py
For backwards compatibility, used to parse HTML datetimes with non-standard timezones
"""

from typing import Optional
from functools import lru_cache
from datetime import datetime

import pytz


# Can modify this by appending to the global variable before _abbr_to_timezone_map runs
ABBR_TIMEZONES: list[str] = list(pytz.all_timezones)
ABBR_TIMEZONES.append("UTC")


@lru_cache(1)
def _abbr_to_timezone_map() -> dict[str, pytz.BaseTzInfo]:
    timezones = list(ABBR_TIMEZONES)

    res: dict[str, pytz.BaseTzInfo] = {}
    for tzname in timezones:
        tz = pytz.timezone(tzname)
        infos = getattr(tz, "_tzinfos", [])
        for info in infos:
            abbr = info[-1]
            res[abbr] = tz
        tzn = getattr(tz, "_tzname", None)
        if tzn is not None:
            res[tzn] = tz
    return res


@lru_cache(maxsize=None)
def abbr_to_timezone(abbr: str) -> pytz.BaseTzInfo:
    return _abbr_to_timezone_map()[abbr]


# Mar 8, 2018, 5:14:40 PM
_TIME_FORMAT = "%b %d, %Y, %I:%M:%S %p"


def parse_html_dt(s: str, *, file_dt: Optional[datetime]) -> datetime:
    fmt = _TIME_FORMAT

    end = s[-3:]
    if end == " PM" or end == " AM":
        # old takeouts (pre-2018?) didn't have timezone, but seems that it was UTC
        return pytz.utc.localize(datetime.strptime(s, fmt))

    s, tzabbr = s.rsplit(maxsplit=1)
    dt = datetime.strptime(s, fmt)

    if tzabbr == "UTC":
        # at some point (between 2018-2020?) were explicitly marked as UTC
        # best to just use it and avoid messing with tzinfo
        return pytz.utc.localize(dt)

    # however after 2020, for some reason takeouts switched to using local offset at the time of the export
    # e.g. Jan 15, 2021, 6:54:12 PM BST -- British Summer Time doesn't make any sense for a January 15 date
    # see https://memex.zulipchat.com/#narrow/stream/279610-data/topic/google.20takeout.20timestamps for more discussion/info
    # so to workaround and parse the dates correctly we have to use the file_dt as well in this case
    tz = abbr_to_timezone(tzabbr)
    if file_dt is None:
        # might result in the wrong timestamp... but it's the best we can do
        return tz.localize(dt)

    # this will computer the correct UTC offset
    export_tzinfo = tz.localize(file_dt).tzinfo
    assert export_tzinfo is not None  # make mypy happy
    return tz.normalize(dt.replace(tzinfo=export_tzinfo))


def test_parse_dt() -> None:
    # hack for the later GMT/BST testcase, need to keep it here because of the lru_cache
    ABBR_TIMEZONES.append("Europe/London")

    assert parse_html_dt("Jun 23, 2015, 2:43:45 PM", file_dt=None) == datetime(
        2015, 6, 23, 14, 43, 45, tzinfo=pytz.utc
    )
    assert parse_html_dt("Jan 25, 2019, 8:23:48 AM GMT", file_dt=None) == datetime(
        2019, 1, 25, 8, 23, 48, tzinfo=pytz.utc
    )
    assert parse_html_dt("Jan 22, 2020, 8:34:00 PM UTC", file_dt=None) == datetime(
        2020, 1, 22, 20, 34, 0, tzinfo=pytz.utc
    )

    assert parse_html_dt("Sep 10, 2019, 8:51:45 PM MSK", file_dt=None) == pytz.timezone(
        "Europe/Moscow"
    ).localize(datetime(2019, 9, 10, 20, 51, 45))

    # without file_dt hints they both will parse into the same (tz-aware) timestamp
    # this is somewhat unfortunate, but not much we can do really
    assert parse_html_dt("Sep 10, 2019, 8:51:45 PM PST", file_dt=None) == parse_html_dt(
        "Sep 10, 2019, 8:51:45 PM PDT", file_dt=None
    )

    # however if we pass proper file_dt (summer/winter correspondingly), they parse correctly (note the 1hr difference)
    assert parse_html_dt(
        "Sep 10, 2019, 8:51:45 PM PST", file_dt=datetime.strptime("20210720", "%Y%m%d")
    ) == parse_html_dt(
        "Sep 10, 2019, 7:51:45 PM PDT", file_dt=datetime.strptime("20201220", "%Y%m%d")
    )

    winter_file_dt = parse_html_dt(
        "Jan 15, 2021, 5:54:12 PM GMT", file_dt=datetime.strptime("20210120", "%Y%m%d")
    )
    summer_file_dt = parse_html_dt(
        "Jan 15, 2021, 6:54:12 PM BST", file_dt=datetime.strptime("20210820", "%Y%m%d")
    )
    assert winter_file_dt == summer_file_dt
    # make sure it's normalized, so the tzinfo property doesn't contain DST tzinfo
    # otherwise it might result in issues, e.g. orjson dumps it with the wrong UTC offset
    assert summer_file_dt.isoformat() == "2021-01-15T17:54:12+00:00"
