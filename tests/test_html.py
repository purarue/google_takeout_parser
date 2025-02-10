from datetime import datetime, timezone

from google_takeout_parser.models import Activity, LocationInfo
from google_takeout_parser.parse_html.activity import _parse_html_activity

from .common import this_dir


def test_parse_html_activity() -> None:

    activity_html = this_dir / "testdata/HtmlTakeout/My Activity/Chrome/MyActivity.html"

    results = list(_parse_html_activity(activity_html))

    assert results == [
        Activity(
            header="Search",
            title="Visited https://productforums.google.com/forum/",
            time=datetime(2018, 1, 31, 22, 54, 50, tzinfo=timezone.utc),
            description=None,
            titleUrl="https://productforums.google.com/forum/",
            subtitles=[],
            details=[],
            locationInfos=[],
            products=["Search"],
        ),
        Activity(
            header="Search",
            title="Visited http://www.adobe.com/creativecloud.html",
            time=datetime(2017, 2, 8, 0, 32, 39, tzinfo=timezone.utc),
            description=None,
            titleUrl="https://www.google.com/url?q=http://www.adobe.com/creativecloud.html&usg=AFQjCNH6fum5tBw7J0dbmUYKGFPduC0vSg",
            subtitles=[],
            details=[],
            locationInfos=[],
            products=["Search"],
        ),
        Activity(
            header="Search",
            title="Searched for adobe creative cloud",
            time=datetime(2017, 2, 8, 0, 32, 36, tzinfo=timezone.utc),
            description=None,
            titleUrl="https://www.google.com/search?q=adobe+creative+cloud",
            subtitles=[],
            details=[],
            locationInfos=[
                LocationInfo(
                    name="From your home: https://google.com/maps?q=25.800819,",
                    url=None,
                    source="80.186310",
                    sourceUrl="https://google.com/maps?q=25.800819,-80.186310",
                ),
                LocationInfo(name=None, url=None, source="", sourceUrl=None),
            ],
            products=["Search"],
        ),
    ]
