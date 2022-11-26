from core.models import Config


def config_context(request):
    return {
        "config": Config.system,
        "config_identity": (
            request.identity.config_identity if request.identity else None
        ),
        "top_section": request.path.strip("/").split("/")[0],
    }
