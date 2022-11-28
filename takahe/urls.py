from django.conf import settings as djsettings
from django.contrib import admin as djadmin
from django.urls import path, re_path
from django.views.static import serve

from activities.views import explore, posts, search, timelines
from core import views as core
from stator import views as stator
from users.views import activitypub, admin, auth, follows, identity, settings

urlpatterns = [
    path("", core.homepage),
    path("manifest.json", core.AppManifest.as_view()),
    # Activity views
    path("notifications/", timelines.Notifications.as_view(), name="notifications"),
    path("local/", timelines.Local.as_view(), name="local"),
    path("federated/", timelines.Federated.as_view(), name="federated"),
    path("search/", search.Search.as_view(), name="search"),
    path("tags/<hashtag>/", timelines.Tag.as_view(), name="tag"),
    path("explore/", explore.Explore.as_view(), name="explore"),
    path("explore/tags/", explore.ExploreTag.as_view(), name="explore-tag"),
    path(
        "settings/",
        settings.SettingsRoot.as_view(),
        name="settings",
    ),
    path(
        "settings/security/",
        settings.SecurityPage.as_view(),
        name="settings_security",
    ),
    path(
        "settings/profile/",
        settings.ProfilePage.as_view(),
        name="settings_profile",
    ),
    path(
        "settings/follows/",
        follows.FollowsPage.as_view(),
        name="settings_follows",
    ),
    path(
        "settings/interface/",
        settings.InterfacePage.as_view(),
        name="settings_interface",
    ),
    path(
        "admin/",
        admin.AdminRoot.as_view(),
        name="admin",
    ),
    path(
        "admin/basic/",
        admin.BasicSettings.as_view(),
        name="admin_basic",
    ),
    path(
        "admin/domains/",
        admin.Domains.as_view(),
        name="admin_domains",
    ),
    path(
        "admin/domains/create/",
        admin.DomainCreate.as_view(),
        name="admin_domains_create",
    ),
    path(
        "admin/domains/<domain>/",
        admin.DomainEdit.as_view(),
    ),
    path(
        "admin/domains/<domain>/delete/",
        admin.DomainDelete.as_view(),
    ),
    path(
        "admin/federation/",
        admin.FederationRoot.as_view(),
        name="admin_federation",
    ),
    path(
        "admin/federation/<domain>/",
        admin.FederationEdit.as_view(),
        name="admin_federation_edit",
    ),
    path(
        "admin/users/",
        admin.Users.as_view(),
        name="admin_users",
    ),
    path(
        "admin/identities/",
        admin.Identities.as_view(),
        name="admin_identities",
    ),
    path(
        "admin/invites/",
        admin.Invites.as_view(),
        name="admin_invites",
    ),
    path(
        "admin/hashtags/",
        admin.Hashtags.as_view(),
        name="admin_hashtags",
    ),
    path(
        "admin/hashtags/create/",
        admin.HashtagCreate.as_view(),
        name="admin_hashtags_create",
    ),
    path(
        "admin/hashtags/<hashtag>/",
        admin.HashtagEdit.as_view(),
    ),
    path(
        "admin/hashtags/<hashtag>/delete/",
        admin.HashtagDelete.as_view(),
    ),
    # Identity views
    path("@<handle>/", identity.ViewIdentity.as_view()),
    path("@<handle>/inbox/", activitypub.Inbox.as_view()),
    path("@<handle>/action/", identity.ActionIdentity.as_view()),
    # Posts
    path("compose/", posts.Compose.as_view(), name="compose"),
    path("@<handle>/posts/<int:post_id>/", posts.Individual.as_view()),
    path("@<handle>/posts/<int:post_id>/like/", posts.Like.as_view()),
    path("@<handle>/posts/<int:post_id>/unlike/", posts.Like.as_view(undo=True)),
    path("@<handle>/posts/<int:post_id>/boost/", posts.Boost.as_view()),
    path("@<handle>/posts/<int:post_id>/unboost/", posts.Boost.as_view(undo=True)),
    path("@<handle>/posts/<int:post_id>/delete/", posts.Delete.as_view()),
    path("@<handle>/posts/<int:post_id>/edit/", posts.Compose.as_view()),
    # Authentication
    path("auth/login/", auth.Login.as_view(), name="login"),
    path("auth/logout/", auth.Logout.as_view(), name="logout"),
    path("auth/signup/", auth.Signup.as_view(), name="signup"),
    path("auth/reset/", auth.TriggerReset.as_view(), name="trigger_reset"),
    path("auth/reset/<token>/", auth.PerformReset.as_view(), name="password_reset"),
    # Identity selection
    path("@<handle>/activate/", identity.ActivateIdentity.as_view()),
    path("identity/select/", identity.SelectIdentity.as_view()),
    path("identity/create/", identity.CreateIdentity.as_view()),
    # Well-known endpoints and system actor
    path(".well-known/webfinger", activitypub.Webfinger.as_view()),
    path(".well-known/host-meta", activitypub.HostMeta.as_view()),
    path(".well-known/nodeinfo", activitypub.NodeInfo.as_view()),
    path("nodeinfo/2.0/", activitypub.NodeInfo2.as_view()),
    path("actor/", activitypub.SystemActorView.as_view()),
    # Stator
    path(".stator/", stator.RequestRunner.as_view()),
    # Django admin
    path("djadmin/", djadmin.site.urls),
    # Media files
    re_path(
        r"^media/(?P<path>.*)$",
        serve,
        kwargs={"document_root": djsettings.MEDIA_ROOT},
    ),
]
