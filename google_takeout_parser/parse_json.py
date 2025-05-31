"""
Lots of functions to transform the JSON from the Takeout to useful information
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterator, Any, Dict, Iterable, Optional, List
import warnings

from .http_allowlist import convert_to_https_opt
from .time_utils import parse_datetime_millis
from .log import logger
from .models import (
    Subtitles,
    LocationInfo,
    Activity,
    LikedYoutubeVideo,
    ChromeHistory,
    PlayStoreAppInstall,
    Location,
    PlaceVisit,
    CandidateLocation,
)
from .common import Res
from .time_utils import parse_json_utc_date


def _read_json_data(p: Path) -> Any:
    try:
        import orjson
    except ModuleNotFoundError:
        warnings.warn(
            "orjson not found, it can significantly speed up json parsing. Consider installing via 'pip install orjson'. Falling back onto stdlib json"
        )
        return json.loads(p.read_text(encoding="utf-8"))
    else:
        return orjson.loads(p.read_bytes())


# "YouTube and YouTube Music/history/search-history.json"
# "YouTube and YouTube Music/history/watch-history.json"
# This is also the 'My Activity' JSON format
def _parse_json_activity(p: Path) -> Iterator[Res[Activity]]:
    json_data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(json_data, list):
        yield RuntimeError(f"Activity: Top level item in '{p}' isn't a list")
    for blob in json_data:
        try:
            subtitles: List[Subtitles] = []
            for s in blob.get("subtitles", []):
                if not isinstance(s, dict):
                    continue
                # sometimes it's just empty ("My Activity/Assistant" data circa 2018)
                if "name" not in s:
                    continue
                subtitles.append(Subtitles(name=s["name"], url=s.get("url")))

            # till at least 2017
            old_format = "snippet" in blob
            if old_format:
                blob = blob["snippet"]
                header = "YouTube"  # didn't have header
                time_str = blob["publishedAt"]
            else:
                _header = blob.get("header")
                if _header is None:
                    # some pre-2021 MyActivity/Chrome/MyActivty.json contain a few items without header
                    # they always seem to be originating from viewing page source
                    if blob["title"].startswith("Visited view-source:"):
                        _header = "Chrome"
                assert _header is not None, blob
                header = _header
                time_str = blob["time"]

            yield Activity(
                header=header,
                title=blob["title"],
                titleUrl=convert_to_https_opt(blob.get("titleUrl")),
                description=blob.get("description"),
                time=parse_json_utc_date(time_str),
                subtitles=subtitles,
                details=[
                    d["name"]
                    for d in blob.get("details", [])
                    if isinstance(d, dict) and "name" in d
                ],
                locationInfos=[
                    LocationInfo(
                        name=locinfo.get("name"),
                        url=convert_to_https_opt(locinfo.get("url")),
                        source=locinfo.get("source"),
                        sourceUrl=convert_to_https_opt(locinfo.get("sourceUrl")),
                    )
                    for locinfo in blob.get("locationInfos", [])
                ],
                products=blob.get("products", []),
            )
        except Exception as e:
            yield e


def _parse_likes(p: Path) -> Iterator[Res[LikedYoutubeVideo]]:
    json_data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(json_data, list):
        yield RuntimeError(f"Likes: Top level item in '{p}' isn't a list")
    for jlike in json_data:
        try:
            yield LikedYoutubeVideo(
                title=jlike["snippet"]["title"],
                desc=jlike["snippet"]["description"],
                link="https://youtube.com/watch?v={}".format(
                    jlike["contentDetails"]["videoId"]
                ),
                dt=parse_json_utc_date(jlike["snippet"]["publishedAt"]),
            )
        except Exception as e:
            yield e


def _parse_app_installs(p: Path) -> Iterator[Res[PlayStoreAppInstall]]:
    json_data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(json_data, list):
        yield RuntimeError(f"App installs: Top level item in '{p}' isn't a list")
    for japp in json_data:
        try:
            yield PlayStoreAppInstall(
                title=japp["install"]["doc"]["title"],
                deviceName=japp.get("install", {})
                .get("deviceAttribute", {})
                .get("deviceDisplayName"),
                deviceCarrier=japp.get("install", {})
                .get("deviceAttribute", {})
                .get("carrier"),
                deviceManufacturer=japp.get("install", {})
                .get("deviceAttribute", {})
                .get("manufacturer"),
                lastUpdateTime=parse_json_utc_date(japp["install"]["lastUpdateTime"]),
                firstInstallationTime=parse_json_utc_date(
                    japp["install"]["firstInstallationTime"]
                ),
            )
        except Exception as e:
            yield e


def _parse_timestamp_key(d: Dict[str, Any], key: str) -> datetime:
    if f"{key}Ms" in d:
        return parse_datetime_millis(d[f"{key}Ms"])
    else:
        # else should be the isoformat
        return parse_json_utc_date(d[key])


def _parse_location_history(p: Path) -> Iterator[Res[Location]]:
    ### HMMM, seems that all the locations are right after one another. broken? May just be all the location history that google has on me
    ### see numpy.diff(list(map(lambda yy: y.at, filter(lambda y: isinstance(Location), events()))))
    json_data = _read_json_data(p)
    if "locations" not in json_data:
        yield RuntimeError(f"Locations: no 'locations' key in '{p}'")
    for loc in json_data.get("locations", []):
        accuracy = loc.get("accuracy")
        deviceTag = loc.get("deviceTag")
        source = loc.get("source")
        try:
            yield Location(
                lng=float(loc["longitudeE7"]) / 1e7,
                lat=float(loc["latitudeE7"]) / 1e7,
                dt=_parse_timestamp_key(loc, "timestamp"),
                accuracy=None if accuracy is None else float(accuracy),
                deviceTag=None if deviceTag is None else int(deviceTag),
                source=None if source is None else str(source),
            )
        except Exception as e:
            yield e


_sem_required_keys = ["location", "duration"]
_sem_required_location_keys = [
    "placeId",  # some fairly recent (as of 2023) places might miss it
    "latitudeE7",
    "longitudeE7",
]


def _check_required_keys(
    d: Dict[str, Any], required_keys: Iterable[str]
) -> Optional[str]:
    for k in required_keys:
        if k not in d:
            return k
    return None


def _parse_semantic_location_history(p: Path) -> Iterator[Res[PlaceVisit]]:
    json_data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(json_data, dict):
        yield RuntimeError(f"Locations: Top level item in '{p}' isn't a dict")
    if "timelineObjects" not in json_data:
        yield RuntimeError(f"Locations: no 'timelineObjects' key in '{p}'")
    timelineObjects = json_data.get("timelineObjects", [])
    for timelineObject in timelineObjects:
        if "placeVisit" not in timelineObject:
            # yield RuntimeError(f"PlaceVisit: no 'placeVisit' key in '{p}'")
            continue
        placeVisit = timelineObject["placeVisit"]
        missing_key = _check_required_keys(placeVisit, _sem_required_keys)
        if missing_key is not None:
            yield RuntimeError(f"PlaceVisit: no '{missing_key}' key in '{p}'")
            continue
        try:
            location_json = placeVisit["location"]
            missing_location_key = _check_required_keys(
                location_json, _sem_required_location_keys
            )
            if missing_location_key is not None:
                # handle these fully defensively, since nothing at all we can do if it's missing these properties
                logger.debug(
                    f"CandidateLocation: {p}, no key '{missing_location_key}' in {location_json}"
                )
                continue
            location = CandidateLocation.from_dict(location_json)
            placeId = location.placeId
            assert (
                placeId is not None
            ), location_json  # this is always present for the actual location
            duration = placeVisit["duration"]
            yield PlaceVisit(
                name=location.name,
                address=location.address,
                # separators=(",", ":") removes whitespace from json.dumps
                otherCandidateLocations=[
                    CandidateLocation.from_dict(pv)
                    for pv in placeVisit.get("otherCandidateLocations", [])
                ],
                sourceInfoDeviceTag=location.sourceInfoDeviceTag,
                placeConfidence=placeVisit.get("placeConfidence"),
                placeVisitImportance=placeVisit.get("placeVisitImportance"),
                placeVisitType=placeVisit.get("placeVisitType"),
                visitConfidence=placeVisit.get("visitConfidence"),
                editConfirmationStatus=placeVisit.get("editConfirmationStatus"),
                placeId=placeId,
                lng=location.lng,
                lat=location.lat,
                centerLat=(
                    float(placeVisit["centerLatE7"]) / 1e7
                    if "centerLatE7" in placeVisit
                    else None
                ),
                centerLng=(
                    float(placeVisit["centerLngE7"]) / 1e7
                    if "centerLngE7" in placeVisit
                    else None
                ),
                startTime=_parse_timestamp_key(duration, "startTimestamp"),
                endTime=_parse_timestamp_key(duration, "endTimestamp"),
                locationConfidence=location.locationConfidence,
            )
        except Exception as e:
            if isinstance(e, KeyError):
                yield RuntimeError(f"PlaceVisit: {p}, no key '{e}' in {placeVisit}")
            else:
                yield e


def _parse_chrome_history(p: Path) -> Iterator[Res[ChromeHistory]]:
    json_data = json.loads(p.read_text(encoding="utf-8"))
    if "Browser History" not in json_data:
        yield RuntimeError(f"Chrome/BrowserHistory: no 'Browser History' key in '{p}'")
    for item in json_data.get("Browser History", []):
        try:
            time_naive = datetime.fromtimestamp(
                item["time_usec"] / 10**6, tz=timezone.utc
            )
            yield ChromeHistory(
                title=item["title"],
                # dont convert to https here, this is just the users history
                # and there's likely lots of items that aren't https
                url=item["url"],
                dt=time_naive.replace(tzinfo=timezone.utc),
                pageTransition=item.get("page_transition"),
            )
        except Exception as e:
            yield e
