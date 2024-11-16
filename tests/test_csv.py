from io import StringIO
from datetime import datetime, timezone
from google_takeout_parser.parse_csv import (
    _parse_youtube_comments_buffer,
    _parse_youtube_live_chats_buffer,
    reconstruct_comment_content,
)
from google_takeout_parser.models import CSVYoutubeComment, CSVYoutubeLiveChat


def test_parse_youtube_comment_buffer_old() -> None:
    """Old format, pre June 2024"""

    # deliberately add some new lines at the end -- real takeout also has them
    text_content = """\
Comment ID,Channel ID,Comment Create Timestamp,Price,Parent Comment ID,Video ID,Comment Text
UgxtiXQkY7gqHbldJ1F4AaABAg,UCA6DtnbZ2KJckyTYfXOwQNA,2023-09-19T17:42:53.434647+00:00,0,,WtOskFeLmr4,"{""takeoutSegments"":[{""text"":""coalowl the legend""}]}"
UgwDN8UeMxW4NDFbvY54AaABAg.9iwJkUYNcXa9u0lv3j3Abh,UCA6DtnbZ2KJckyTYfXOwQNA,2023-08-30T01:54:46.801024+00:00,0,UgwDN8UeMxW4NDFbvY54AaABAg,jH39c5-y6kg,"{""takeoutSegments"":[{""text"":""Ah, this is the reason why Ive never seen concurrent write failures myself, python's default timeout value is 5s, so it just waits in a busy loop if I have 'concurrent writers'""}]}"




"""

    buf = StringIO(text_content)

    res = list(_parse_youtube_comments_buffer(buf))
    assert len(res) == 2, res
    [res0, res1] = res

    assert not isinstance(res0, Exception)
    assert res0 == CSVYoutubeComment(
        commentId="UgxtiXQkY7gqHbldJ1F4AaABAg",
        channelId="UCA6DtnbZ2KJckyTYfXOwQNA",
        dt=datetime(2023, 9, 19, 17, 42, 53, 434647, tzinfo=timezone.utc),
        price="0",
        parentCommentId=None,
        videoId="WtOskFeLmr4",
        contentJSON='{"takeoutSegments":[{"text":"coalowl the legend"}]}',
    )
    assert (
        reconstruct_comment_content(res0.contentJSON, format="text")
        == "coalowl the legend"
    )

    assert not isinstance(res1, Exception)
    assert res1 == CSVYoutubeComment(
        commentId="UgwDN8UeMxW4NDFbvY54AaABAg.9iwJkUYNcXa9u0lv3j3Abh",
        channelId="UCA6DtnbZ2KJckyTYfXOwQNA",
        dt=datetime(2023, 8, 30, 1, 54, 46, 801024, tzinfo=timezone.utc),
        price="0",
        parentCommentId="UgwDN8UeMxW4NDFbvY54AaABAg",
        videoId="jH39c5-y6kg",
        contentJSON='{"takeoutSegments":[{"text":"Ah, this is the reason why Ive never seen concurrent write failures myself, python\'s default timeout value is 5s, so it just waits in a busy loop if I have \'concurrent writers\'"}]}',
    )
    assert (
        reconstruct_comment_content(res1.contentJSON, format="text")
        == "Ah, this is the reason why Ive never seen concurrent write failures myself, python's default timeout value is 5s, so it just waits in a busy loop if I have 'concurrent writers'"
    )


def test_parse_youtube_comment_buffer_new() -> None:
    """New format, post June 2024"""

    text_content = """\
Channel ID,Comment Create Timestamp,Price,Comment ID,Parent Comment ID,Video ID,Comment Text
UCYnl1cugi7Lw1h8j6JNqNEg,2023-04-14T07:39:35.956042+00:00,0,UgytHqobEtqoKm_-pYB4AaABAg,,rWVAzS6duAs,"{""text"":""\u003e I am about to get buried in the concrete""},{""text"":""\n""},{""text"":""the most normal  Veritasium video!""}"
UCYnl1cugi7Lw1h8j6JNqNEg,2016-01-29T18:26:53.255+00:00,0,UgiNMzGz_nAsjXfCoAEC,,ZuvK-oe647c,"{""text"":""Great illustration of Bell inequality!""}"


"""

    buf = StringIO(text_content)
    res = list(_parse_youtube_comments_buffer(buf))
    assert len(res) == 2, res
    [res0, res1] = res

    assert not isinstance(res0, Exception)
    assert res0 == CSVYoutubeComment(
        commentId="UgytHqobEtqoKm_-pYB4AaABAg",
        channelId="UCYnl1cugi7Lw1h8j6JNqNEg",
        dt=datetime(2023, 4, 14, 7, 39, 35, 956042, tzinfo=timezone.utc),
        price="0",
        parentCommentId=None,
        videoId="rWVAzS6duAs",
        contentJSON='{"text":"> I am about to get buried in the concrete"},{"text":"\n"},{"text":"the most normal  Veritasium video!"}',
    )
    assert (
        reconstruct_comment_content(res0.contentJSON, format="text")
        == "> I am about to get buried in the concrete\nthe most normal  Veritasium video!"
    )

    assert not isinstance(res1, Exception)
    assert res1 == CSVYoutubeComment(
        commentId="UgiNMzGz_nAsjXfCoAEC",
        channelId="UCYnl1cugi7Lw1h8j6JNqNEg",
        dt=datetime(2016, 1, 29, 18, 26, 53, 255000, tzinfo=timezone.utc),
        price="0",
        parentCommentId=None,
        videoId="ZuvK-oe647c",
        contentJSON='{"text":"Great illustration of Bell inequality!"}',
    )
    assert (
        reconstruct_comment_content(res1.contentJSON, format="text")
        == "Great illustration of Bell inequality!"
    )


def test_parse_youtube_live_chat_buffer() -> None:
    text_content = """UgwsSD8yrDW7_h6F5vZ4AaABDqgB5OC1kgI,UCA6DtnbZ2KJckyTYfXOwQNA,2018-09-02T05:16:35.510381+00:00,0,0vGCh85obuI,"{""takeoutSegments"":[{""text"":""\""think the right thing\"" jeez""}]}"

    """

    buf = StringIO(text_content)

    res = list(_parse_youtube_live_chats_buffer(buf, skip_first=False))
    assert len(res) == 1

    assert res[0] == CSVYoutubeLiveChat(
        liveChatId="UgwsSD8yrDW7_h6F5vZ4AaABDqgB5OC1kgI",
        channelId="UCA6DtnbZ2KJckyTYfXOwQNA",
        dt=datetime(2018, 9, 2, 5, 16, 35, 510381, tzinfo=timezone.utc),
        price="0",
        videoId="0vGCh85obuI",
        contentJSON='{"takeoutSegments":[{"text":""think the right thing" jeez"}]}',
    )
