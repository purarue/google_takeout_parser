from .common import (
    HandlerMap,
    _parse_html_activity,
    _parse_html_comment_file,
    _parse_json_activity,
    _parse_likes,
    _parse_youtube_comments_csv,
    _parse_youtube_live_chats_csv,
    _parse_app_installs,
    _parse_location_history,
    _parse_semantic_location_history,
    _parse_chrome_history,
    _parse_keep,
)


# If parsed, should mention:
# Google Help Communities
#   - Select JSON as Output
# Google Play Books
#   - Select JSON as Output
# Google Play Games Services
#   - Select JSON as Output
# Google Play Movies & TV options
#   - Select JSON as Output
# Profile
#   - Select JSON as Output
#
# Note: when I say 'no info here' or 'not useful', is just how the
# data appears in my export. It might be useful for you -- if so
# feel free to make a PR or an issue to parse it
#
# Can also extend or overwrite these functions by passing
# 'None' if you don't want a certain part to be parsed,
# or by passing your own function which parses the file something from models.py

# Reminder that dicts are ordered, so order here can matter
# If you want to parse one file from a folder with lot of files, can
# specify that file, and then on the next line specify 'None'
# for the folder, ignoring the rest of files

# Setting 'None' in the handler map specifies that we should ignore this file
#
HANDLER_MAP: HandlerMap = {
    r"Chrome/BrowserHistory.json": _parse_chrome_history,
    r"Chrome/History.json": _parse_chrome_history,  # Seems to have been renamed from BrowserHistory.json to History.json sometime between Oct 2023 to Sep 2024
    r"Chrome": None,  # Ignore rest of Chrome stuff
    r"Google Play Store/Installs.json": _parse_app_installs,
    r"Google Play Store/": None,  # ignore anything else in Play Store
    # optional space to handle pre-2017 data
    r"Location History/Location( )?History.json": _parse_location_history,  # old path to Location History
    r"Location History( \(Timeline\))?/Records.json": _parse_location_history,
    r"Location History( \(Timeline\))?/Semantic Location History/.*/.*.json": _parse_semantic_location_history,
    r"Location History( \(Timeline\))?/": None,  # ignore anything else in Location History
    # HTML/JSON activity-like files which aren't in 'My Activity'
    # optional " and Youtube Music" to handle pre-2017 data
    r"YouTube( and YouTube Music)?/history/.*?.html": _parse_html_activity,
    r"YouTube( and YouTube Music)?/history/.*?.json": _parse_json_activity,
    # basic list item files which have chat messages/comments
    r"YouTube( and YouTube Music)?/my-comments/.*?.html": _parse_html_comment_file,
    r"YouTube( and YouTube Music)?/comments/comments.csv": _parse_youtube_comments_csv,
    r"YouTube( and YouTube Music)?/live\s*chats/live\s*chats.csv": _parse_youtube_live_chats_csv,
    r"YouTube( and YouTube Music)?/my-live-chat-messages/.*?.html": _parse_html_comment_file,
    r"YouTube( and YouTube Music)?/playlists/likes.json": _parse_likes,
    r"YouTube( and YouTube Music)?/playlists/": None,
    r"YouTube( and YouTube Music)?/subscriptions": None,
    r"YouTube( and YouTube Music)?/videos": None,
    r"YouTube( and YouTube Music)?/music-uploads": None,
    r"YouTube( and YouTube Music)?/channels/": None,
    r"My Activity/Assistant/.*.mp3": None,  # might be interesting to extract timestamps
    r"My Activity/Voice and Audio/.*.mp3": None,
    r"My Activity/Takeout": None,  # activity for when you made takeouts, dont need
    # HTML 'My Activity' Files
    # the \d+ is for split html files, see the ./split_html directory
    r"My Activity/.*?My\s*Activity(-\d+)?.html": _parse_html_activity,
    r"My Activity/.*?My\s*Activity.json": _parse_json_activity,
    # Maybe parse these?
    r"Access Log Activity": None,
    r"Assistant Notes and Lists/.*.csv": None,
    r"Blogger/Comments/.*?feed.atom": None,
    r"Blogger/Blogs/": None,
    # Fit has possibly interesting data
    # Fit/Daily activity metrics/2015-07-27.csv
    # Fit/Activities/2017-10-29T23_08_59Z_PT2M5.699S_Other.tcx
    # Fit/All Data/derived_com.google.calories.bmr_com.google.and.json
    r"Fit/": None,
    r"Groups": None,
    r"Google Play Games Services/Games/.*/(Achievements|Activity|Experience|Scores).html": None,
    r"Hangouts": None,
    r"Keep/.*?.json": _parse_keep,
    r"Keep/": None,
    r"Maps (your places)": None,
    r"My Maps/.*.kmz": None,  # custom KML maps
    r"Saved/.*.csv": None,  # lists with saved places from Google Maps
    r"Shopping Lists/.*.csv": None,
    r"Tasks": None,
    # Files to ignore
    r"Android Device Configuration Service/": None,
    r"Blogger/Albums/": None,
    r"Blogger/Profile/": None,
    r"Calendar/": None,
    r"Cloud Print/": None,
    r"Contacts/": None,
    r"Drive/": None,
    r"Google Account/": None,
    r"Google Business Profile/": None,
    r"Google My Business/": None,
    r"Google Pay/": None,
    r"Google Photos/": None,  # has images/some metadata on each of them
    r"Google Play Books/.*.pdf": None,
    r"Google Play Games Services/Games/.*/(Data.bin|Metadata.html)": None,
    r"Google Play Movies.*?/": None,
    r"Google Shopping/": None,
    r"Google Store/": None,
    r"Google Translator Toolkit/": None,
    r"Google Workspace Marketplace/": None,
    r"Home App/": None,
    r"Mail/": None,
    r"Maps/": None,
    r"News/": None,
    r"Profile/Profile.json": None,
    r"Saved/Favorite places.csv": None,
    r"Search Contributions/": None,
    r"archive_browser.html": None,  # description of takeout, not that useful
}
