"""
Models for the data parsed by this module

Each top-level dataclass here has a 'key' property
which determines unique events while merging
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Union, Protocol, NamedTuple, Iterator
from dataclasses import dataclass

from .common import Res

Url = str


def get_union_args(cls: Any) -> tuple[type] | None:  # type: ignore[type-arg]
    if getattr(cls, "__origin__", None) != Union:
        return None

    args = cls.__args__
    args = [e for e in args if e != type(None)]  # noqa: E721
    assert len(args) > 0
    return args  # type: ignore


class Subtitles(NamedTuple):
    name: str
    url: Url | None


class LocationInfo(NamedTuple):
    name: str | None
    url: Url | None
    source: str | None
    sourceUrl: Url | None


class KeepListContent(NamedTuple):
    textHtml: str
    text: str
    isChecked: bool


class KeepAnnotation(NamedTuple):
    description: str
    source: str
    title: str
    url: str


# fmt: off
class BaseEvent(Protocol):
    @property
    def key(self) -> Any:
        ...
# fmt: on


@dataclass
class Activity(BaseEvent):
    header: str
    title: str
    time: datetime
    description: str | None
    titleUrl: Url | None
    # note: in HTML exports, there is no way to tell the difference between
    # a description and a subtitle, so they end up as subtitles
    # more lines of text describing this
    subtitles: list[Subtitles]
    details: list[str]
    locationInfos: list[LocationInfo]
    products: list[str]

    @property
    def dt(self) -> datetime:
        return self.time

    @property
    def products_desc(self) -> str:
        return ", ".join(sorted(self.products))

    @property
    def key(self) -> tuple[str, str, int]:
        return self.header, self.title, int(self.time.timestamp())


@dataclass
class YoutubeComment(BaseEvent):
    """
    NOTE: this was the old format, the takeout.google.com returns a CSV file now instead, which is the model CSVYoutubeComment below
    """

    content: str
    dt: datetime
    urls: list[Url]

    @property
    def key(self) -> int:
        return int(self.dt.timestamp())


@dataclass
class CSVYoutubeComment(BaseEvent):
    commentId: str
    channelId: str
    dt: datetime
    price: str | None
    parentCommentId: str | None
    videoId: str
    contentJSON: str

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.videoId}&lc={self.commentId}"

    @property
    def video_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.videoId}"

    @property
    def key(self) -> int:
        return int(self.dt.timestamp())


# considered reusing model above, but might be confusing
# and its useful to know if a message was from a livestream
# or a VOD
@dataclass
class CSVYoutubeLiveChat(BaseEvent):
    """
    this is very similar to CSVYoutubeComment, but chatId instead of commentId
    and it can't have a parentCommentId
    """

    liveChatId: str
    channelId: str
    dt: datetime
    price: str | None
    videoId: str
    contentJSON: str

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.videoId}&lc={self.liveChatId}"

    @property
    def video_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.videoId}"

    @property
    def key(self) -> int:
        return int(self.dt.timestamp())


@dataclass
class LikedYoutubeVideo(BaseEvent):
    title: str
    desc: str
    link: str
    dt: datetime

    @property
    def key(self) -> int:
        return int(self.dt.timestamp())


@dataclass
class PlayStoreAppInstall(BaseEvent):
    title: str
    lastUpdateTime: datetime  # timestamp for when the installation event occurred
    # timestamp for when you first installed the app on the given device
    firstInstallationTime: datetime
    deviceName: str | None
    deviceCarrier: str | None
    deviceManufacturer: str | None

    # noticed that lastUpdateTime was more accurate timestamp for the dt field
    # since different installation events of the same app had pretty close firstInstallation times
    # but the lastUpdate time was always at a later timestamp so I assumed it was the installation event
    @property
    def dt(self) -> datetime:
        return self.lastUpdateTime  # previously returned the firstInstallationTime

    @property
    def key(self) -> int:
        return int(self.lastUpdateTime.timestamp())


@dataclass
class Location(BaseEvent):
    lat: float
    lng: float
    accuracy: float | None
    deviceTag: int | None
    source: str | None
    dt: datetime

    @property
    def key(self) -> tuple[float, float, float | None, int]:
        return self.lat, self.lng, self.accuracy, int(self.dt.timestamp())


# this is not cached as a model, its saved as JSON -- its a helper class that placevisit uses
@dataclass
class CandidateLocation:
    lat: float
    lng: float
    address: str | None
    name: str | None

    placeId: str | None
    """
    Sometimes missing, in this case semanticType is set
    """

    semanticType: str | None
    """
    Something like TYPE_HOME or TYPE_WORK or TYPE_ALIAS
    """

    locationConfidence: float | None  # missing in older (around 2014/15) history
    sourceInfoDeviceTag: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateLocation:
        placeId = data.get("placeId")
        semanticType = data.get("semanticType")
        if placeId is None:
            # at least one of them should be present
            assert semanticType is not None, data

        return cls(
            address=data.get("address"),
            name=data.get("name"),
            placeId=placeId,
            semanticType=semanticType,
            locationConfidence=data.get("locationConfidence"),
            lat=data["latitudeE7"] / 1e7,
            lng=data["longitudeE7"] / 1e7,
            sourceInfoDeviceTag=data.get("sourceInfo", {}).get("deviceTag"),
        )


@dataclass
class PlaceVisit(BaseEvent):
    # these are part of the 'location' key
    lat: float
    lng: float
    centerLat: float | None
    centerLng: float | None
    address: str | None
    name: str | None
    locationConfidence: float | None  # missing in older (around 2014/15) history
    placeId: str
    startTime: datetime
    endTime: datetime
    sourceInfoDeviceTag: int | None
    otherCandidateLocations: list[CandidateLocation]
    # TODO: parse these into an enum of some kind? may be prone to breaking due to new values from google though...
    placeConfidence: str | None  # older semantic history (pre-2018 didn't have it)
    placeVisitType: str | None
    visitConfidence: float | None  # missing in older (around 2014/15) history
    editConfirmationStatus: str | None  # missing in older (around 2014/15) history
    placeVisitImportance: str | None = None

    @property
    def dt(self) -> datetime:  # type: ignore[override]
        return self.startTime

    @property
    def key(self) -> tuple[float, float, int, float | None]:
        return self.lat, self.lng, int(self.startTime.timestamp()), self.visitConfidence


@dataclass
class ChromeHistory(BaseEvent):
    title: str
    url: Url
    dt: datetime
    pageTransition: str | None

    @property
    def key(self) -> tuple[str, int]:
        return self.url, int(self.dt.timestamp())


@dataclass
class Keep(BaseEvent):
    title: str
    updated_dt: datetime
    created_dt: datetime
    listContent: list[KeepListContent] | None
    textContent: str | None
    # i guess this is good to have, found it in some of the json files
    textContentHtml: str | None
    color: str
    annotations: list[KeepAnnotation] | None
    isTrashed: bool
    isPinned: bool
    isArchived: bool

    @property
    def key(self) -> int:
        return int(self.created_dt.timestamp())


# can't compute this dynamically -- have to write it out
# if you want to override, override both global variable types with new types
DEFAULT_MODEL_TYPE = Union[
    Activity,
    LikedYoutubeVideo,
    PlayStoreAppInstall,
    Location,
    ChromeHistory,
    YoutubeComment,
    CSVYoutubeComment,
    CSVYoutubeLiveChat,
    PlaceVisit,
    Keep,
]

CacheResults = Iterator[Res[DEFAULT_MODEL_TYPE]]
