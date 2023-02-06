from asgiref.sync import sync_to_async
from django.db import models

from stator.models import State, StateField, StateGraph, StatorModel


class InboxMessageStates(StateGraph):
    received = State(try_interval=300, delete_after=86400 * 3)
    processed = State(externally_progressed=True, delete_after=86400)
    purge = State(delete_after=24 * 60 * 60)  # Delete after release (back compat)

    received.transitions_to(processed)
    processed.transitions_to(purge)  # Delete after release (back compat)

    @classmethod
    async def handle_received(cls, instance: "InboxMessage"):
        from activities.models import Post, PostInteraction, TimelineEvent
        from users.models import Block, Follow, Identity, Report
        from users.services import IdentityService

        match instance.message_type:
            case "follow":
                await sync_to_async(Follow.handle_request_ap)(instance.message)
            case "block":
                await sync_to_async(Block.handle_ap)(instance.message)
            case "announce":
                await sync_to_async(PostInteraction.handle_ap)(instance.message)
            case "like":
                await sync_to_async(PostInteraction.handle_ap)(instance.message)
            case "create":
                match instance.message_object_type:
                    case "note":
                        if instance.message_object_has_content:
                            await sync_to_async(Post.handle_create_ap)(instance.message)
                        else:
                            # Notes without content are Interaction candidates
                            await sync_to_async(PostInteraction.handle_ap)(
                                instance.message
                            )
                    case "question":
                        pass  # Drop for now
                    case unknown:
                        if unknown in Post.Types.names:
                            await sync_to_async(Post.handle_create_ap)(instance.message)
                        else:
                            raise ValueError(
                                f"Cannot handle activity of type create.{unknown}"
                            )
            case "update":
                match instance.message_object_type:
                    case "note":
                        await sync_to_async(Post.handle_update_ap)(instance.message)
                    case "person":
                        await sync_to_async(Identity.handle_update_ap)(instance.message)
                    case "service":
                        await sync_to_async(Identity.handle_update_ap)(instance.message)
                    case "group":
                        await sync_to_async(Identity.handle_update_ap)(instance.message)
                    case "organization":
                        await sync_to_async(Identity.handle_update_ap)(instance.message)
                    case "application":
                        await sync_to_async(Identity.handle_update_ap)(instance.message)
                    case "question":
                        pass  # Drop for now
                    case unknown:
                        if unknown in Post.Types.names:
                            await sync_to_async(Post.handle_update_ap)(instance.message)
                        else:
                            raise ValueError(
                                f"Cannot handle activity of type update.{unknown}"
                            )
            case "accept":
                match instance.message_object_type:
                    case "follow":
                        await sync_to_async(Follow.handle_accept_ap)(instance.message)
                    case None:
                        # It's a string object, but these will only be for Follows
                        await sync_to_async(Follow.handle_accept_ap)(instance.message)
                    case unknown:
                        raise ValueError(
                            f"Cannot handle activity of type accept.{unknown}"
                        )
            case "reject":
                match instance.message_object_type:
                    case "follow":
                        await sync_to_async(Follow.handle_reject_ap)(instance.message)
                    case None:
                        # It's a string object, but these will only be for Follows
                        await sync_to_async(Follow.handle_reject_ap)(instance.message)
                    case unknown:
                        raise ValueError(
                            f"Cannot handle activity of type reject.{unknown}"
                        )
            case "undo":
                match instance.message_object_type:
                    case "follow":
                        await sync_to_async(Follow.handle_undo_ap)(instance.message)
                    case "block":
                        await sync_to_async(Block.handle_undo_ap)(instance.message)
                    case "like":
                        await sync_to_async(PostInteraction.handle_undo_ap)(
                            instance.message
                        )
                    case "announce":
                        await sync_to_async(PostInteraction.handle_undo_ap)(
                            instance.message
                        )
                    case "http://litepub.social/ns#emojireact":
                        # We're ignoring emoji reactions for now
                        pass
                    case unknown:
                        raise ValueError(
                            f"Cannot handle activity of type undo.{unknown}"
                        )
            case "delete":
                # If there is no object type, we need to see if it's a profile or a post
                if not isinstance(instance.message["object"], dict):
                    if await Identity.objects.filter(
                        actor_uri=instance.message["object"]
                    ).aexists():
                        await sync_to_async(Identity.handle_delete_ap)(instance.message)
                    elif await Post.objects.filter(
                        object_uri=instance.message["object"]
                    ).aexists():
                        await sync_to_async(Post.handle_delete_ap)(instance.message)
                    else:
                        # It is presumably already deleted
                        pass
                else:
                    match instance.message_object_type:
                        case "tombstone":
                            await sync_to_async(Post.handle_delete_ap)(instance.message)
                        case "note":
                            await sync_to_async(Post.handle_delete_ap)(instance.message)
                        case unknown:
                            raise ValueError(
                                f"Cannot handle activity of type delete.{unknown}"
                            )
            case "add":
                # We are ignoring these right now (probably pinned items)
                pass
            case "remove":
                # We are ignoring these right now (probably pinned items)
                pass
            case "move":
                # We're ignoring moves for now
                pass
            case "http://litepub.social/ns#emojireact":
                # We're ignoring emoji reactions for now
                pass
            case "flag":
                # Received reports
                await sync_to_async(Report.handle_ap)(instance.message)
            case "__internal__":
                match instance.message_object_type:
                    case "fetchpost":
                        await sync_to_async(Post.handle_fetch_internal)(
                            instance.message["object"]
                        )
                    case "cleartimeline":
                        await sync_to_async(TimelineEvent.handle_clear_timeline)(
                            instance.message["object"]
                        )
                    case "addfollow":
                        await sync_to_async(IdentityService.handle_internal_add_follow)(
                            instance.message["object"]
                        )
                    case unknown:
                        raise ValueError(
                            f"Cannot handle activity of type __internal__.{unknown}"
                        )
            case unknown:
                raise ValueError(f"Cannot handle activity of type {unknown}")
        return cls.processed


class InboxMessage(StatorModel):
    """
    an incoming inbox message that needs processing.

    Yes, this is kind of its own message queue built on the state graph system.
    It's fine. It'll scale up to a decent point.
    """

    message = models.JSONField()

    state = StateField(InboxMessageStates)

    @classmethod
    def create_internal(cls, payload):
        """
        Creates an internal action message
        """
        cls.objects.create(
            message={
                "type": "__internal__",
                "object": payload,
            }
        )

    @property
    def message_type(self):
        return self.message["type"].lower()

    @property
    def message_object_type(self) -> str | None:
        if isinstance(self.message["object"], dict):
            return self.message["object"]["type"].lower()
        else:
            return None

    @property
    def message_type_full(self):
        if isinstance(self.message.get("object"), dict):
            return f"{self.message_type}.{self.message_object_type}"
        else:
            return f"{self.message_type}"

    @property
    def message_actor(self):
        return self.message.get("actor")

    @property
    def message_object_has_content(self):
        return "content" in self.message.get("object", {})
