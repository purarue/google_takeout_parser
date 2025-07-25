import json
import datetime
from pathlib import Path
from typing import Iterator, Any

import pytest
import google_takeout_parser.parse_json as prj
from google_takeout_parser import models


@pytest.fixture(scope="function")
def tmp_path_f(
    request: Any, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Path]:
    """
    Create a new tempdir every time this runs
    """
    # request is a _pytest.fixture.SubRequest, function that called this
    assert isinstance(request.function.__name__, str), str(request)
    assert request.function.__name__.strip(), str(request)
    tmp_dir = tmp_path_factory.mktemp(request.function.__name__, numbered=True)
    yield tmp_dir


def test_parse_activity_json(tmp_path_f: Path) -> None:
    contents = '[{"header": "Discover", "title": "7 cards in your feed", "time": "2021-12-13T03:04:05.007Z", "products": ["Discover"], "locationInfos": [{"name": "At this general area", "url": "https://www.google.com/maps/@?api=1&map_action=map&center=lat,lon&zoom=12", "source": "From your Location History", "sourceUrl": "https://www.google.com/maps/timeline"}], "subtitles": [{"name": "Computer programming"}, {"name": "Computer Science"}, {"name": "PostgreSQL"}, {"name": "Technology"}]}]'
    fp = tmp_path_f / "file"
    fp.write_text(contents)
    res = list(prj._parse_json_activity(fp))
    assert res[0] == models.Activity(
        header="Discover",
        title="7 cards in your feed",
        time=datetime.datetime(
            2021, 12, 13, 3, 4, 5, 7000, tzinfo=datetime.timezone.utc
        ),
        description=None,
        titleUrl=None,
        subtitles=[
            models.Subtitles("Computer programming", None),
            models.Subtitles("Computer Science", None),
            models.Subtitles("PostgreSQL", None),
            models.Subtitles("Technology", None),
        ],
        locationInfos=[
            models.LocationInfo(
                "At this general area",
                "https://www.google.com/maps/@?api=1&map_action=map&center=lat,lon&zoom=12",
                "From your Location History",
                "https://www.google.com/maps/timeline",
            ),
        ],
        details=[],
        products=["Discover"],
    )


def test_parse_likes_json(tmp_path_f: Path) -> None:
    contents = """[{"contentDetails": {"videoId": "J1tF-DKKt7k", "videoPublishedAt": "2015-10-05T17:23:15.000Z"}, "etag": "GbLczUV2gsP6j0YQgTcYropUbdY", "id": "TExBNkR0bmJaMktKY2t5VFlmWE93UU5BLkoxdEYtREtLdDdr", "kind": "youtube#playlistItem", "snippet": {"channelId": "UCA6DtnbZ2KJckyTYfXOwQNA", "channelTitle": "Title", "description": "\\u30b7\\u30e5\\u30ac\\u30fc\\u30bd\\u30f3\\u30b0\\u3068\\u30d3\\u30bf\\u30fc\\u30b9\\u30c6\\u30c3\\u30d7 \\nSugar Song and Bitter Step\\n\\u7cd6\\u6b4c\\u548c\\u82e6\\u5473\\u6b65\\u9a5f\\nUNISON SQUARE GARDEN\\n\\u7530\\u6df5\\u667a\\u4e5f\\n\\u8840\\u754c\\u6226\\u7dda\\n\\u5e7b\\u754c\\u6230\\u7dda\\nBlood Blockade Battlefront ED\\nArranged by Maybe\\nScore:https://drive.google.com/open?id=0B9Jb1ks6rtrWSk1hX1U0MXlDSUE\\nThx~~", "playlistId": "LLA6DtnbZ2KJckyTYfXOwQNA", "position": 4, "publishedAt": "2020-07-05T18:27:32.000Z", "resourceId": {"kind": "youtube#video", "videoId": "J1tF-DKKt7k"}, "thumbnails": {"default": {"height": 90, "url": "https://i.ytimg.com/vi/J1tF-DKKt7k/default.jpg", "width": 120}, "high": {"height": 360, "url": "https://i.ytimg.com/vi/J1tF-DKKt7k/hqdefault.jpg", "width": 480}, "medium": {"height": 180, "url": "https://i.ytimg.com/vi/J1tF-DKKt7k/mqdefault.jpg", "width": 320}, "standard": {"height": 480, "url": "https://i.ytimg.com/vi/J1tF-DKKt7k/sddefault.jpg", "width": 640}}, "title": "[Maybe]Blood Blockade Battlefront ED \\u30b7\\u30e5\\u30ac\\u30fc\\u30bd\\u30f3\\u30b0\\u3068\\u30d3\\u30bf\\u30fc\\u30b9\\u30c6\\u30c3\\u30d7 Sugar Song and Bitter Step"}, "status": {"privacyStatus": "public"}}]"""
    fp = tmp_path_f / "file"
    fp.write_text(contents)
    res = list(prj._parse_likes(fp))
    assert res == [
        models.LikedYoutubeVideo(
            title="[Maybe]Blood Blockade Battlefront ED シュガーソングとビターステップ "
            "Sugar Song and Bitter Step",
            desc="シュガーソングとビターステップ \n"
            "Sugar Song and Bitter Step\n"
            "糖歌和苦味步驟\n"
            "UNISON SQUARE GARDEN\n"
            "田淵智也\n"
            "血界戦線\n"
            "幻界戰線\n"
            "Blood Blockade Battlefront ED\n"
            "Arranged by Maybe\n"
            "Score:https://drive.google.com/open?id=0B9Jb1ks6rtrWSk1hX1U0MXlDSUE\n"
            "Thx~~",
            link="https://youtube.com/watch?v=J1tF-DKKt7k",
            dt=datetime.datetime(2020, 7, 5, 18, 27, 32, tzinfo=datetime.timezone.utc),
        )
    ]


def test_parse_app_installs(tmp_path_f: Path) -> None:
    contents = """[{"install":{"doc":{"documentType":"Android Apps","title":"ClickUp - Manage Teams & Tasks"},"firstInstallationTime":"2022-03-14T07:06:12.070725Z","deviceAttribute":{"model":"SM-S901E","carrier":"Vodafone","manufacturer":"samsung","deviceDisplayName":"samsung SM-S901E"},"lastUpdateTime":"2024-08-27T22:55:15.184610Z"}}]"""

    fp = tmp_path_f / "file"
    fp.write_text(contents)
    res = list(prj._parse_app_installs(fp))
    assert res == [
        models.PlayStoreAppInstall(
            title="ClickUp - Manage Teams \u0026 Tasks",
            lastUpdateTime=datetime.datetime(
                2024, 8, 27, 22, 55, 15, 184610, tzinfo=datetime.timezone.utc
            ),
            firstInstallationTime=datetime.datetime(
                2022, 3, 14, 7, 6, 12, 70725, tzinfo=datetime.timezone.utc
            ),
            deviceName="samsung SM-S901E",
            deviceCarrier="Vodafone",
            deviceManufacturer="samsung",
        )
    ]


def test_location_old(tmp_path_f: Path) -> None:
    contents = '{"locations": [{"timestampMs": "1512947698030", "latitudeE7": 351324213, "longitudeE7": -1122434441, "accuracy": 10}]}'
    fp = tmp_path_f / "file"
    fp.write_text(contents)
    res = list(prj._parse_location_history(fp))
    assert res == [
        models.Location(
            lng=-112.2434441,
            lat=35.1324213,
            dt=datetime.datetime(
                2017, 12, 10, 23, 14, 58, tzinfo=datetime.timezone.utc
            ),
            accuracy=10.0,
            deviceTag=None,
            source=None,
        ),
    ]


def test_location_new(tmp_path_f: Path) -> None:
    contents = '{"locations": [{"latitudeE7": 351324213, "longitudeE7": -1122434441, "accuracy": 10, "deviceTag": -8024144696862913506, "deviceDesignation": "PRIMARY", "timestamp": "2017-12-10T23:14:58.030Z"}]}'
    fp = tmp_path_f / "file"
    fp.write_text(contents)
    res = list(prj._parse_location_history(fp))
    assert res == [
        models.Location(
            lng=-112.2434441,
            lat=35.1324213,
            dt=datetime.datetime(
                2017, 12, 10, 23, 14, 58, 30000, tzinfo=datetime.timezone.utc
            ),
            accuracy=10.0,
            deviceTag=-8024144696862913506,
            source=None,
        ),
    ]


def test_location_2024(tmp_path_f: Path) -> None:
    contents = '{"locations":[{"latitudeE7":351324213,"longitudeE7":-1122434441,"accuracy":10,"activity":[{"activity":[{"type":"UNKNOWN","confidence":65},{"type":"IN_VEHICLE","confidence":27},{"type":"STILL","confidence":6},{"type":"ON_BICYCLE","confidence":2}],"timestamp":"2014-07-18T15:00:04.403Z"}],"source":"WIFI","deviceTag":1978796627,"timestamp":"2014-07-18T14:59:59.914Z"}]}'
    fp = tmp_path_f / "file"
    fp.write_text(contents)
    res = list(prj._parse_location_history(fp))
    assert res == [
        models.Location(
            lng=-112.2434441,
            lat=35.1324213,
            dt=datetime.datetime(
                2014, 7, 18, 14, 59, 59, 914000, tzinfo=datetime.timezone.utc
            ),
            accuracy=10.0,
            deviceTag=1978796627,
            source="WIFI",
        ),
    ]


def test_chrome_history(tmp_path_f: Path) -> None:
    contents = '{"Browser History": [{"page_transition": "LINK", "title": "title", "url": "https://purarue.xyz", "client_id": "W1vSb98l403jhPeK==", "time_usec": 1617404690134513}]}'
    fp = tmp_path_f / "file"
    fp.write_text(contents)
    res = list(prj._parse_chrome_history(fp))
    assert res == [
        models.ChromeHistory(
            title="title",
            url="https://purarue.xyz",
            dt=datetime.datetime(
                2021, 4, 2, 23, 4, 50, 134513, tzinfo=datetime.timezone.utc
            ),
            pageTransition="LINK",
        ),
    ]


def test_semantic_location_history(tmp_path_f: Path) -> None:
    data = {
        "timelineObjects": [
            {
                "placeVisit": {
                    "location": {
                        "latitudeE7": 555555555,
                        "longitudeE7": -1066666666,
                        "placeId": "JK4E4P",
                        "address": "address",
                        "name": "name",
                        "sourceInfo": {"deviceTag": 987654321},
                        "locationConfidence": 60.45,
                    },
                    "duration": {
                        "startTimestamp": "2017-12-10T23:29:25.026Z",
                        "endTimestamp": "2017-12-11T01:20:06.106Z",
                    },
                    "placeConfidence": "MEDIUM_CONFIDENCE",
                    "centerLatE7": 555555555,
                    "centerLngE7": -1666666666,
                    "visitConfidence": 65.45,
                    "otherCandidateLocations": [
                        {
                            "latitudeE7": 423984239,
                            "longitudeE7": -1565656565,
                            "placeId": "XPRK4E4P",
                            "address": "address2",
                            "name": "name2",
                            "locationConfidence": 24.475897,
                        },
                        {
                            "latitudeE7": 910000000,
                            "longitudeE7": -1000,
                            "semanticType": "TYPE_WORK",
                        },
                    ],
                    "editConfirmationStatus": "NOT_CONFIRMED",
                    "locationConfidence": 55,
                    "placeVisitType": "SINGLE_PLACE",
                    "placeVisitImportance": "MAIN",
                }
            }
        ]
    }
    fp = tmp_path_f / "file"
    fp.write_text(json.dumps(data))
    res = list(prj._parse_semantic_location_history(fp))
    obj = res[0]
    assert not isinstance(obj, Exception)
    # remove JSON, compare manually below
    assert obj == models.PlaceVisit(
        lat=55.5555555,
        lng=-106.6666666,
        centerLat=55.5555555,
        centerLng=-166.6666666,
        name="name",
        address="address",
        locationConfidence=60.45,
        placeId="JK4E4P",
        startTime=datetime.datetime(
            2017, 12, 10, 23, 29, 25, 26000, tzinfo=datetime.timezone.utc
        ),
        endTime=datetime.datetime(
            2017, 12, 11, 1, 20, 6, 106000, tzinfo=datetime.timezone.utc
        ),
        sourceInfoDeviceTag=987654321,
        placeConfidence="MEDIUM_CONFIDENCE",
        placeVisitImportance="MAIN",
        placeVisitType="SINGLE_PLACE",
        visitConfidence=65.45,
        editConfirmationStatus="NOT_CONFIRMED",
        otherCandidateLocations=[
            models.CandidateLocation(
                lat=42.3984239,
                lng=-156.5656565,
                name="name2",
                address="address2",
                locationConfidence=24.475897,
                placeId="XPRK4E4P",
                semanticType=None,
                sourceInfoDeviceTag=None,
            ),
            models.CandidateLocation(
                lat=91.0,
                lng=-0.0001,
                name=None,
                address=None,
                locationConfidence=None,
                placeId=None,
                semanticType="TYPE_WORK",
                sourceInfoDeviceTag=None,
            ),
        ],
    )


def test_semantic_location_history_2024(tmp_path_f: Path) -> None:
    data = {
        "timelineObjects": [
            {
                "placeVisit": {
                    "location": {
                        "latitudeE7": 555555555,
                        "longitudeE7": -1066666666,
                        "placeId": "JK4E4P",
                        "address": "address",
                        "name": "name",
                        "sourceInfo": {"deviceTag": 987654321},
                        "locationConfidence": 60.45,
                    },
                    "duration": {
                        "startTimestamp": "2017-12-10T23:29:25.026Z",
                        "endTimestamp": "2017-12-11T01:20:06.106Z",
                    },
                    "placeConfidence": "MEDIUM_CONFIDENCE",
                    "centerLatE7": 555555555,
                    "centerLngE7": -1666666666,
                    "visitConfidence": 65.45,
                    "otherCandidateLocations": [
                        {
                            "latitudeE7": 423984239,
                            "longitudeE7": -1565656565,
                            "placeId": "XPRK4E4P",
                            "address": "address2",
                            "name": "name2",
                            "locationConfidence": 24.475897,
                        },
                        {
                            "latitudeE7": 910000000,
                            "longitudeE7": -1000,
                            "semanticType": "TYPE_WORK",
                        },
                    ],
                    "editConfirmationStatus": "NOT_CONFIRMED",
                    "locationConfidence": 55,
                    "placeVisitType": "SINGLE_PLACE",
                    "placeVisitImportance": "MAIN",
                }
            },
            {
                "activitySegment": {
                    "startLocation": {
                        "latitudeE7": 555555555,
                        "longitudeE7": -1066666666,
                    },
                    "endLocation": {
                        "latitudeE7": 555555567,
                        "longitudeE7": -1066666678,
                    },
                    "duration": {
                        "startTimestamp": "2017-12-11T01:20:06.106Z",
                        "endTimestamp": "2017-12-11T01:40:06.106Z",
                    },
                    "distance": 13071,
                    "activityType": "IN_PASSENGER_VEHICLE",
                    "confidence": "MEDIUM",
                    "activities": [
                        {
                            "activityType": "IN_PASSENGER_VEHICLE",
                            "probability": 85.514968640442,
                        },
                        {
                            "activityType": "MOTORCYCLING",
                            "probability": 8.858836042221917,
                        },
                        {"activityType": "WALKING", "probability": 4.7803567526550035},
                    ],
                    "waypointPath": {
                        "waypoints": [
                            {"latE7": 123456789, "lngE7": 1210000000},
                            {"latE7": 123456089, "lngE7": 1210000200},
                            {"latE7": 123456289, "lngE7": 1210000500},
                        ],
                        "source": "INFERRED",
                    },
                    "simplifiedRawPath": {
                        "points": [
                            {
                                "latE7": 123456489,
                                "lngE7": 1210000240,
                                "accuracyMeters": 10,
                                "timestamp": "2017-12-11T01:35:04Z",
                            }
                        ]
                    },
                    "editConfirmationStatus": "NOT_CONFIRMED",
                    "parkingEvent": {
                        "location": {
                            "latitudeE7": 123456289,
                            "longitudeE7": 1210000500,
                            "accuracyMetres": 163,
                        },
                        "method": "END_OF_ACTIVITY_SEGMENT",
                        "locationSource": "UNKNOWN",
                        "timestamp": "2017-12-11T01:40:06Z",
                    },
                }
            },
        ]
    }
    fp = tmp_path_f / "file"
    fp.write_text(json.dumps(data))
    res = list(prj._parse_semantic_location_history(fp))
    obj = res[0]
    assert not isinstance(obj, Exception)
    # remove JSON, compare manually below
    assert obj == models.PlaceVisit(
        lat=55.5555555,
        lng=-106.6666666,
        centerLat=55.5555555,
        centerLng=-166.6666666,
        name="name",
        address="address",
        locationConfidence=60.45,
        placeId="JK4E4P",
        startTime=datetime.datetime(
            2017, 12, 10, 23, 29, 25, 26000, tzinfo=datetime.timezone.utc
        ),
        endTime=datetime.datetime(
            2017, 12, 11, 1, 20, 6, 106000, tzinfo=datetime.timezone.utc
        ),
        sourceInfoDeviceTag=987654321,
        placeConfidence="MEDIUM_CONFIDENCE",
        placeVisitImportance="MAIN",
        placeVisitType="SINGLE_PLACE",
        visitConfidence=65.45,
        editConfirmationStatus="NOT_CONFIRMED",
        otherCandidateLocations=[
            models.CandidateLocation(
                lat=42.3984239,
                lng=-156.5656565,
                name="name2",
                address="address2",
                locationConfidence=24.475897,
                placeId="XPRK4E4P",
                semanticType=None,
                sourceInfoDeviceTag=None,
            ),
            models.CandidateLocation(
                lat=91.0,
                lng=-0.0001,
                name=None,
                address=None,
                locationConfidence=None,
                placeId=None,
                semanticType="TYPE_WORK",
                sourceInfoDeviceTag=None,
            ),
        ],
    )


def test_keep(tmp_path_f: Path) -> None:
    data = {
        "title": "Grocery List",
        "userEditedTimestampUsec": 1649291142757000,
        "createdTimestampUsec": 1649291142757000,
        "listContent": [
            {
                "textHtml": "<li>Apples</li>",
                "text": "Apples",
                "isChecked": False
            },
            {
                "textHtml": "<li>Milk</li>",
                "text": "Milk",
                "isChecked": True
            }
        ],
        "textContent": "Don't forget to buy snacks too.",
        "textContentHtml": "<p>Don't forget to buy snacks too.</p>",
        "color": "yellow",
        "annotations": [
            {
                "description": "Weekly grocery run",
                "source": "Keep",
                "title": "Shopping Note",
                "url": "https://keep.google.com/"
            }
        ],
        "isTrashed": False,
        "isPinned": True,
        "isArchived": False
    }

    fp = tmp_path_f / "file"
    fp.write_text(json.dumps(data))
    res = list(prj._parse_keep(fp))
    obj = res[0]
    assert not isinstance(obj, Exception)
    assert obj == models.Keep(
        title="Grocery List",
        updated_dt=datetime.datetime(
            2022, 4, 7, 0, 25, 42, 757000, tzinfo=datetime.timezone.utc,
        ),
        created_dt=datetime.datetime(
            2022, 4, 7, 0, 25, 42, 757000, tzinfo=datetime.timezone.utc,
        ),
        listContent=[
            models.KeepListContent(
                textHtml="<li>Apples</li>",
                text="Apples",
                isChecked=False
            ),
            models.KeepListContent(
                textHtml="<li>Milk</li>",
                text="Milk",
                isChecked=True
            )
        ],
        textContent="Don't forget to buy snacks too.",
        textContentHtml="<p>Don't forget to buy snacks too.</p>",
        color="yellow",
        annotations=[
            models.KeepAnnotation(
                description="Weekly grocery run",
                source="Keep",
                title="Shopping Note",
                url="https://keep.google.com/"
            )
        ],
        isTrashed=False,
        isPinned=True,
        isArchived=False
    )


def test_keep_2021(tmp_path_f: Path) -> None:
    """
    Check that pre-April 2022 (or earler) Keep entries which didn't have createdTimestampUsec are parsed gracefully
    """
    fp = tmp_path_f / "file"
    fp.write_text(r"""
        {
            "color":"DEFAULT",
            "isTrashed":false,
            "isPinned":true,
            "isArchived":false,
            "textContent":"some content",
            "title":"note title",
            "userEditedTimestampUsec":1518606205722000
        }
    """)
    res = list(prj._parse_keep(fp))
    obj = res[0]
    assert not isinstance(obj, Exception)
    assert obj == models.Keep(
        title="note title",
        updated_dt=datetime.datetime(
            2018, 2, 14, 11, 3, 25, 722000, tzinfo=datetime.timezone.utc,
        ),
        created_dt=datetime.datetime(
            2018, 2, 14, 11, 3, 25, 722000, tzinfo=datetime.timezone.utc,
        ),
        listContent=[],
        textContent="some content",
        textContentHtml=None,
        color="DEFAULT",
        annotations=[],
        isTrashed=False,
        isPinned=True,
        isArchived=False,
    )
