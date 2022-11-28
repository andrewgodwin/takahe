from datetime import timedelta

from django.utils import timezone

from activities.templatetags.activity_tags import linkify_hashtags, timedeltashort


def test_timedeltashort_regress():
    assert timedeltashort(None) == ""
    assert timedeltashort("") == ""

    value = timezone.now()

    assert timedeltashort(value) == "0s"
    assert timedeltashort(value - timedelta(seconds=2)) == "2s"
    assert timedeltashort(value - timedelta(minutes=2)) == "2m"
    assert timedeltashort(value - timedelta(hours=2)) == "2h"
    assert timedeltashort(value - timedelta(days=2)) == "2d"
    assert timedeltashort(value - timedelta(days=364)) == "364d"
    assert timedeltashort(value - timedelta(days=365)) == "1y"
    assert timedeltashort(value - timedelta(days=366)) == "1y"


def test_linkify_hashtags_regres():
    assert linkify_hashtags(None) == ""
    assert linkify_hashtags("") == ""

    assert (
        linkify_hashtags("#Takahe")
        == '<a class="hashtag" href="/tags/takahe/">#Takahe</a>'
    )
