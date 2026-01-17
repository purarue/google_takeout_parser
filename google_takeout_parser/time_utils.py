import sys
from datetime import datetime, timezone


def parse_datetime_sec(d: str | float | int) -> datetime:
    return datetime.fromtimestamp(int(d), tz=timezone.utc)


def parse_datetime_millis(d: str | float | int) -> datetime:
    return parse_datetime_sec(int(d) / 1000)


if sys.version_info[:2] >= (3, 11):
    # from 3.11, it supports parsing strings ending with Z
    parse_json_utc_date = datetime.fromisoformat
else:

    def parse_json_utc_date(ds: str) -> datetime:
        utc_naive = datetime.fromisoformat(ds.rstrip("Z"))
        return utc_naive.replace(tzinfo=timezone.utc)


def test_parse_utc_date() -> None:
    expected = datetime(2021, 9, 30, 1, 44, 33, tzinfo=timezone.utc)
    assert parse_json_utc_date("2021-09-30T01:44:33.000Z") == expected

    assert parse_json_utc_date("2023-01-27T22:46:47.389352Z") == datetime(
        2023, 1, 27, 22, 46, 47, 389352, tzinfo=timezone.utc
    )
