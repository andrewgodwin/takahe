import asyncio

import pytest
from asgiref.sync import async_to_sync
from pytest_httpx import HTTPXMock

from activities.models import Post, PostStates


@pytest.mark.django_db
def test_fetch_post(httpx_mock: HTTPXMock):
    """
    Tests that a post we don't have locally can be fetched by by_object_uri
    """
    httpx_mock.add_response(
        url="https://example.com/test-post",
        json={
            "@context": [
                "https://www.w3.org/ns/activitystreams",
            ],
            "id": "https://example.com/test-post",
            "type": "Note",
            "published": "2022-11-13T23:20:16Z",
            "url": "https://example.com/test-post",
            "attributedTo": "https://example.com/test-actor",
            "content": "BEEEEEES",
        },
    )
    # Fetch with a HTTP access
    post = Post.by_object_uri("https://example.com/test-post", fetch=True)
    assert post.content == "BEEEEEES"
    assert post.author.actor_uri == "https://example.com/test-actor"
    # Fetch again with a DB hit
    assert Post.by_object_uri("https://example.com/test-post").id == post.id


@pytest.mark.django_db
def test_linkify_mentions_remote(identity, remote_identity):
    """
    Tests that we can linkify post mentions properly for remote use
    """
    # Test a short username (remote)
    post = Post.objects.create(
        content="<p>Hello @test</p>",
        author=identity,
        local=True,
    )
    post.mentions.add(remote_identity)
    assert (
        post.safe_content_remote()
        == '<p>Hello <a href="https://remote.test/@test/">@test</a></p>'
    )
    # Test a full username (local)
    post = Post.objects.create(
        content="<p>@test@example.com, welcome!</p>",
        author=identity,
        local=True,
    )
    post.mentions.add(identity)
    assert (
        post.safe_content_remote()
        == '<p><a href="https://example.com/@test/">@test@example.com</a>, welcome!</p>'
    )
    # Test that they don't get touched without a mention
    post = Post.objects.create(
        content="<p>@test@example.com, welcome!</p>",
        author=identity,
        local=True,
    )
    assert post.safe_content_remote() == "<p>@test@example.com, welcome!</p>"


@pytest.mark.django_db
def test_linkify_mentions_local(identity, remote_identity):
    """
    Tests that we can linkify post mentions properly for local use
    """
    # Test a short username (remote)
    post = Post.objects.create(
        content="<p>Hello @test</p>",
        author=identity,
        local=True,
    )
    post.mentions.add(remote_identity)
    assert (
        post.safe_content_local()
        == '<p>Hello <a href="/@test@remote.test/">@test</a></p>'
    )
    # Test a full username (local)
    post = Post.objects.create(
        content="<p>@test@example.com, welcome!</p>",
        author=identity,
        local=True,
    )
    post.mentions.add(identity)
    assert (
        post.safe_content_local()
        == '<p><a href="/@test@example.com/">@test@example.com</a>, welcome!</p>'
    )
    # Test a full username (remote) with no <p>
    post = Post.objects.create(
        content="@test@remote.test hello!",
        author=identity,
        local=True,
    )
    post.mentions.add(remote_identity)
    assert (
        post.safe_content_local()
        == '<a href="/@test@remote.test/">@test@remote.test</a> hello!'
    )
    # Test that they don't get touched without a mention
    post = Post.objects.create(
        content="<p>@test@example.com, welcome!</p>",
        author=identity,
        local=True,
    )
    assert post.safe_content_local() == "<p>@test@example.com, welcome!</p>"


async def stator_process_tasks(stator):
    """
    Guarded wrapper to simply async_to_sync and ensure all stator tasks are
    run to completion without blocking indefinitely.
    """
    await asyncio.wait_for(stator.fetch_and_process_tasks(), timeout=1)
    for _ in range(100):
        if not stator.tasks:
            break
        stator.remove_completed_tasks()
        await asyncio.sleep(0.01)


@pytest.mark.django_db
def test_post_transitions(identity, stator_runner):

    # Create post
    post = Post.objects.create(
        content="<p>Hello!</p>",
        author=identity,
        local=False,
        visibility=Post.Visibilities.mentioned,
    )
    # Test: | --> new --> fanned_out
    assert post.state == str(PostStates.new)
    async_to_sync(stator_process_tasks)(stator_runner)
    post = Post.objects.get(id=post.id)
    assert post.state == str(PostStates.fanned_out)

    # Test: fanned_out --> (forced) edited --> edited_fanned_out
    Post.transition_perform(post, PostStates.edited)
    async_to_sync(stator_process_tasks)(stator_runner)
    post = Post.objects.get(id=post.id)
    assert post.state == str(PostStates.edited_fanned_out)

    # Test: edited_fanned_out --> (forced) deleted --> deleted_fanned_out
    Post.transition_perform(post, PostStates.deleted)
    async_to_sync(stator_process_tasks)(stator_runner)
    post = Post.objects.get(id=post.id)
    assert post.state == str(PostStates.deleted_fanned_out)
