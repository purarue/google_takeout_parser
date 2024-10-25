# google_takeout_parser

Parses data out of your [Google Takeout](https://takeout.google.com/) (History, Activity, Youtube, Locations, etc...). This:

- parses both the Historical HTML and new JSON format for Google Takeouts
- caches individual takeout results behind [`cachew`](https://github.com/karlicoss/cachew)
- merges multiple takeouts into unique events

---

- [Installation](#installation)
- [Usage](#usage)
  - [CLI Usage](#cli-usage)
  - [Library Usage](#library-usage)
- [Legacy HTML Parsing](#legacy-html-parsing)
- [Contributing](#contributing)
- [Testing](#testing)

This doesn't handle all cases, but I have yet to find a parser that does, so here is my attempt at parsing what I see as the most useful info from it. The Google Takeout is pretty particular, and the contents of the directory depend on what you select while exporting. Unhandled files will warn, though feel free to [PR a parser](#contributing) or [create an issue](https://github.com/purarue/google_takeout_parser/issues/new?title=add+parser+for) if this doesn't parse some part you want.

This can take a few minutes to parse depending on what you have in your Takeout (especially while using the old HTML format), so this uses [cachew](https://github.com/karlicoss/cachew) to cache the function result for each Takeout you may have. That means this'll take a few minutes the first time parsing a takeout, but then only a few seconds every subsequent time.

Since google slowly removes your old data over time, I would recommend periodically backing up your data (personally I do it once every few months), to not lose any old events and get access to data from new ones. To do that, go to [takeout.google.com](https://takeout.google.com/); For Reference, once on that page, I hit `Deselect All`, then select:

- Chrome
- Google Play Store
- Location History
- My Activity
  - Select JSON as format
- Youtube and Youtube Music
  - Select JSON as format
  - In options, deselect `music-library-songs`, `music-uploads` and `videos`

**Be sure to select JSON instead of HTML whenever possible**. Code to parse the HTML format is included here, but it is treated as legacy code and comes with worse performance and a myriad of other issues. See [legacy html parsing](#legacy-html-parsing)

The process for obtaining these isn't that great -- you have to manually go to [takeout.google.com](https://takeout.google.com) every few months, select what you want to export info for, and then it puts the zipped file into your google drive. You can tell it to run it at specific intervals, but I personally haven't found that to be that reliable.

This currently parses:

- Activity (from dozens of Google Services) - `My Activity/*.html|*.json`)
- Chrome History - `Chrome/BrowserHistory.json`
- Google Play Installs - `Google Play Store/Installs.json`
- Location History:
  - Semantic Location History`Location History/Semantic Location History/*`
  - Location History `Location History/Location History.json`, `Location History/Records.json`
- Youtube:
  - History - `YouTube and YouTube Music/history/*.html|*.json`
  - Comments:
    - Legacy HTML Comment/Live chats: `YouTube and YouTube Music/my-comments/*.html` and `YouTube and YouTube Music/my-live-chat-messages/*.html`
    - CSV/JSON (comment text is stored as a JSON blob, [see below](#youtube-comment-json)
      - `Youtube/comments/comments.csv`
      - `Youtube/live chats/live chats.csv`
  - Likes: `YouTube and YouTube Music/playlists/likes.json`

This was extracted out of [my HPI](https://github.com/purarue/HPI/tree/4bb1f174bdbd693ab29e744413424d18b8667b1f/my/google) modules, which was in turn modified from the google files in [karlicoss/HPI](https://github.com/karlicoss/HPI/blob/4a04c09f314e10a4db8f35bf1ecc10e4d0203223/my/google/takeout/html.py)

## Installation

Requires `python3.8+`

To install with pip, run:

    pip install google-takeout-parser

## Usage

The directory structure of the google takeout changes depending on your Google accounts main language. If this doesn't support your language, see [contributing](#contributing). This currently supports:

- `EN`: English
- `DE`: German (thanks to [@parthux1](https://github.com/parthux1))

### CLI Usage

Can be accessed by either `google_takeout_parser` or `python -m google_takeout_parser`. Offers a basic interface to list/clear the cache directory, and/or parse/merge a takeout and interact with it in a REPL:

```
Usage: google_takeout_parser parse [OPTIONS] TAKEOUT_DIR

  Parse a takeout directory takeout

Options:
  -f, --filter [Activity|LikedYoutubeVideo|PlayStoreAppInstall|Location|ChromeHistory|YoutubeComment|PlaceVisit]
                                  Filter to only show events of this type
  -l, --locale [EN|DE]            Locale to use for matching filenames [default: EN]  [env var:
                                  GOOGLE_TAKEOUT_PARSER_LOCALE]
  -a, --action [repl|summary|json]
                                  What to do with the parsed result  [default: repl]
  --cache / --no-cache            [default: no-cache]
  -h, --help                      Show this message and exit.
```

If you use a language this doesn't support, see [contributing](#contributing).

To clear the `cachew` cache: `google_takeout_parser cache_dir clear`

A few examples of parsing takeouts:

```
$ google_takeout_parser --quiet parse ~/data/Unpacked_Takout --cache
Interact with the export using res

In [1]: res[-2]
Out[1]: PlayStoreAppInstall(title='Hangouts', device_name='motorola moto g(7) play', dt=datetime.datetime(2020, 8, 2, 15, 51, 50, 180000, tzinfo=datetime.timezone.utc))

In [2]: len(res)
Out[2]: 236654
```

`$ google_takeout_parser --quiet merge ./Takeout-Old ./Takeout-New --action summary --no-cache`

```python
Counter({'Activity': 366292,
         'Location': 147581,
         'YoutubeComment': 131,
         'PlayStoreAppInstall': 122,
         'LikedYoutubeVideo': 100,
         'ChromeHistory': 4})
```

Can also dump the info to JSON; e.g. to filter YouTube-related stuff from your Activity using [jq](https://jqlang.github.io/jq/):

```bash
google_takeout_parser --quiet parse -a json -f Activity --no-cache ./Takeout-New |
  # select stuff like Youtube, m.youtube.com, youtube.com using jq
  jq '.[] | select(.header | ascii_downcase | test("youtube"))' |
  # grab the titleUrl, ignoring nulls
  jq 'select(.titleUrl) | .titleUrl' -r
```

Also contains a small utility command to help move/extract the google takeout:

```bash
$ google_takeout_parser move --from ~/Downloads/takeout*.zip --to-dir ~/data/google_takeout --extract
Extracting /home/username/Downloads/takeout-20211023T070558Z-001.zip to /tmp/tmp07ua_0id
Moving /tmp/tmp07ua_0id/Takeout to /home/username/data/google_takeout/Takeout-1634993897
$ ls -1 ~/data/google_takeout/Takeout-1634993897
archive_browser.html
Chrome
'Google Play Store'
'Location History'
'My Activity'
'YouTube and YouTube Music'
```

### Library Usage

Assuming you maintain an unpacked view, e.g. like:

```
 $ tree -L 1 ./Takeout-1599315526
./Takeout-1599315526
├── Google Play Store
├── Location History
├── My Activity
└── YouTube and YouTube Music
```

To parse one takeout:

```python
from google_takeout.path_dispatch import TakeoutParser
tp = TakeoutParser("/full/path/to/Takeout-1599315526")
# to check if files are all handled
tp.dispatch_map()
# to parse without caching the results in ~/.cache/google_takeout_parser
uncached = list(tp.parse())
# to parse with cachew cache https://github.com/karlicoss/cachew
cached = list(tp.parse(cache=True))
```

To parse a locale this doesn't support yet, you can create a dictionary which maps the names of the files to functions, see [`locales/en.py`](google_takeout_parser/locales/en.py) for an example. That can be passed as `handlers` to `TakeoutParser`

To cache and merge takeouts (maintains a single dependency on the paths you pass -- so if you change the input paths, it does a full recompute)

```python
from google_takeout.merge import cached_merge_takeouts
results = list(cached_merge_takeouts(["/full/path/to/Takeout-1599315526", "/full/path/to/Takeout-1634971143"]))
```

If you don't want to cache the results but want to merge results from multiple takeouts, can do something custom by directly using the `merge_events` function:

```python
from google_takeout_parser.merge import merge_events, TakeoutParser
itrs = []  # list of iterators of google events
for path in ['path/to/Takeout-1599315526' 'path/to/Takeout-1616796262']:
    # ignore errors, error_policy can be 'yield', 'raise' or 'drop'
    tk = TakeoutParser(path, error_policy="drop")
    itrs.append(tk.parse(cache=False))
res = list(merge_events(*itrs))
```

The events this returns is a combination of all types in the [`models.py`](google_takeout_parser/models.py), to filter to a particular type you can provide that to skip parsing other files:

```python
from google_takeout_parser.models import Location
from google_takeout_parser.path_dispatch import TakeoutParser
# filter_type can be a list to filter multiple types
locations = list(TakeoutParser("path/to/Takeout").parse(filter_type=Location))
len(locations)
99913
```

I personally exclusively use this through the [HPI google takeout](https://github.com/karlicoss/HPI/blob/master/my/google/takeout/parser.py) file, as a configuration layer to locate where my takeouts are on disk, and since that 'automatically' unzips the takeouts (I store them as the zips), i.e., doesn't require me to maintain an unpacked view

#### Youtube Comment JSON

The CSV youtube comment files' content are stored as a JSON blob, which look like:

```json
{
  "takeoutSegments": [
    {
      "text": "I symlink /bin/sh to dash, its a very minimal/posix compliant implementation. see "
    },
    {
      "text": "https://wiki.archlinux.org/index.php/Dash",
      "link": {
        "linkUrl": "https://wiki.archlinux.org/index.php/Dash"
      }
    }
  ]
}
```

This exposes some functions to help parse those, into text, markdown, or just extract the links:

```python
from google_takeout_parser.path_dispatch import TakeoutParser
from google_takeout_parser.models import CSVYoutubeComment
from google_takeout_parser.parse_csv import extract_comment_links, reconstruct_comment_content


path = "./Takeout-1599315526"
comments = list(
    TakeoutParser(path, error_policy="raise").parse(
        cache=False, filter_type=CSVYoutubeComment
    )
)
for e in comments:
    print(extract_comment_links(e.contentJSON))
    print(reconstruct_comment_content(e.contentJSON, "text"))
    print(reconstruct_comment_content(e.contentJSON, "markdown"))
```

### Legacy HTML Parsing

I would _heavily recommend against_ using the HTML format for `My Activity`. It is not always possible to properly parse the metadata, is more prone to errors parsing dates due to local timezones, and takes much longer to parse than the JSON format.

On certain machines, the giant HTML files may even take so much memory that the process is eventually killed for using too much memory. For a workaround, see [split_html](./split_html).

### Contributing

Just to give a brief overview, to add new functionality (parsing some new folder that this doesn't currently support), you'd need to:

- Add a `model` for it in [`models.py`](google_takeout_parser/models.py) subclassing `BaseEvent` and adding it to the Union at the bottom of the file. That should have a [`key` property function](https://github.com/purarue/google_takeout_parser/blob/a8aefac76d8e1474ca2275b4a7c78bbb962c7a04/google_takeout_parser/models.py#L185-L187) which describes each event uniquely (this is used to remove duplicate items when merging takeouts)
- Write a function which takes the `Path` to the file you're trying to parse and converts it to the model you created (See examples in [`parse_json.py`](google_takeout_parser/parse_json.py)). Ideally extract a single raw item from the takeout file add a test for it so its obvious when/if the format changes.
- Add a regex match for the file path to the handler map in [`google_takeout_parser/locales/en.py`](google_takeout_parser/locales/en.py).

Dont feel required to add support for all locales, its somewhat annoying to swap languages on google, request a takeout, wait for it to process and then swap back.

Though, if your takeout is in some language this doesn't support, you can [create an issue](https://github.com/purarue/google_takeout_parser/issues/new?title=support+new+locale) with the file structure (run `find Takeout` and/or `tree Takeout`), or contribute a locale file by creating a `path -> function mapping` ([see locales](https://github.com/purarue/google_takeout_parser/tree/master/google_takeout_parser/locales)), and adding it to the global `LOCALES` variables in `locales/all.py` and `locales/main.py`

This is a pretty difficult to maintain, as it requires a lot of manual testing from people who have access to these takeouts, and who actively use the language that the takeout is in. My google accounts main language is English, so I upkeep that locale whenever I notice changes, but its not trivial to port those changes to other locales without swapping my language, making an export, waiting, and then switching back. I keep track of mismatched changes [in this board](https://github.com/users/purarue/projects/1/views/1)

Ideally, when first creating a locale file, you would select everything when doing a takeout (not just the `My Activity`/`Chrome`/`Location History` like I suggested above), so [paths that are not parsed can be ignored properly](https://github.com/purarue/google_takeout_parser/blob/4981c241c04b5b37265710dcc6ca00f19d1eafb4/google_takeout_parser/locales/en.py#L105C1-L113).

### Testing

```bash
git clone 'https://github.com/purarue/google_takeout_parser'
cd ./google_takeout_parser
pip install '.[testing]'
mypy ./google_takeout_parser
flake8 ./google_takeout_parser
pytest
```
