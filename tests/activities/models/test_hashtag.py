from activities.models import Hashtag


def test_hashtag_from_content():
    assert Hashtag.hashtags_from_content("#hashtag") == ["hashtag"]
    assert Hashtag.hashtags_from_content("a#hashtag") == []
    assert Hashtag.hashtags_from_content("Text #with #hashtag in it") == [
        "hashtag",
        "with",
    ]
    assert Hashtag.hashtags_from_content("#hashtag.") == ["hashtag"]
    assert Hashtag.hashtags_from_content("More text\n#one # two ##three #hashtag;") == [
        "hashtag",
        "one",
        "three",
    ]


def test_linkify_hashtag():
    linkify = Hashtag.linkify_hashtags

    assert linkify("# hashtag") == "# hashtag"
    assert (
        linkify('<a href="/url/with#anchor">Text</a>')
        == '<a href="/url/with#anchor">Text</a>'
    )
    assert (
        linkify("#HashTag") == '<a class="hashtag" href="/tags/hashtag/">#HashTag</a>'
    )
    assert (
        linkify(
            """A longer text #bigContent
with #tags, linebreaks, and
maybe a few <a href="https://awesome.sauce/about#spicy">links</a>
#allTheTags #AllTheTags #ALLTHETAGS"""
        )
        == """A longer text <a class="hashtag" href="/tags/bigcontent/">#bigContent</a>
with <a class="hashtag" href="/tags/tags/">#tags</a>, linebreaks, and
maybe a few <a href="https://awesome.sauce/about#spicy">links</a>
<a class="hashtag" href="/tags/allthetags/">#allTheTags</a> <a class="hashtag" href="/tags/allthetags/">#AllTheTags</a> <a class="hashtag" href="/tags/allthetags/">#ALLTHETAGS</a>"""
    )
