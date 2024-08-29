"""
Wrapper around HTTPX that provides some fedi-specific features.

The API is identical to httpx, but some features has been added:

* Fedi-compatible HTTP signatures
* Blocked IP ranges

(Because Y is next after X).
"""
import asyncio
import ipaddress
import logging
import socket
import typing
from ssl import SSLCertVerificationError, SSLError
from types import EllipsisType

import httpx
from django.conf import settings
from httpx import RequestError
from httpx._types import TimeoutTypes, URLTypes
from idna.core import InvalidCodepoint

from .signatures import HttpSignature

__all__ = (
    "SigningActor",
    "Client",
    "AsyncClient",
    "RequestError",
)

logger = logging.getLogger(__name__)


class SigningActor(typing.Protocol):
    """
    An AP Actor with keys, that can sign requests.

    Both :class:`users.models.identity.Identity`, and
    :class:`users.models.system_actor.SystemActor` implement this protocol.
    """

    #: The private key used for signing, in PEM format
    private_key: str

    # This is pretty much part of the interface, but we don't need it when
    # making requests.
    # public_key: str

    #: The URL we should use to advertise this key
    public_key_id: str


class SignedAuth(httpx.Auth):
    """
    Handles signing the request.
    """

    # Doing it this way so we get automatic sync/async handling
    requires_request_body = True

    def __init__(self, actor: SigningActor):
        self.actor = actor

    def auth_flow(self, request: httpx.Request):
        HttpSignature.sign_request(
            request, self.actor.private_key, self.actor.public_key_id
        )
        yield request


class BlockedIPError(Exception):
    """
    Attempted to make a request that might have hit a blocked IP range.
    """


class IpFilterWrapperTransport(httpx.BaseTransport, httpx.AsyncBaseTransport):
    def __init__(
        self,
        blocked_ranges: list[ipaddress.IPv4Network | ipaddress.IPv6Network | str],
        wrappee: httpx.BaseTransport,
    ):
        self.blocked_ranges = blocked_ranges
        self.wrappee = wrappee

    def __enter__(self):
        self.wrappee.__enter__()
        return self

    def __exit__(self, *exc):
        self.wrappee.__exit__(*exc)

    def close(self):
        self.wrappee.close()

    async def __aenter__(self):
        await self.wrappee.__aenter__()
        return self

    async def __aexit__(self, *exc):
        await self.wrappee.__aexit__(self, *exc)

    async def aclose(self):
        await self.wrappee.close()

    def _request_to_addrinfo(self, request) -> tuple:
        return (
            request.url.raw_host.decode("ascii"),
            request.url.port or request.url.scheme,
        )

    def _check_addrinfo(self, req: httpx.Request, ai: typing.Sequence[tuple]):
        """
        Compare an IP to the blocked ranges
        """
        addr: ipaddress._BaseAddress
        for info in ai:
            match info:
                case (socket.AF_INET, _, _, _, (addr, _)):
                    addr = ipaddress.IPv4Address(addr)
                case (socket.AF_INET6, _, _, _, (addr, _, _, _)):
                    addr = ipaddress.IPv6Address(addr)  # TODO: Do we need the flowinfo?
                case _:
                    continue

            for net in self.blocked_ranges:
                if addr in net:
                    raise BlockedIPError(
                        "Attempted to make a connection to {addr} as {request.url.host} (blocked by {net})"
                    )

    # It would have been nicer to do this at a lower level, so we know what
    # IPs we're _actually_ connecting to, but:
    # * That's really deep in httpcore and ughhhhhh
    # * httpcore just passes the string hostname to the socket API anyway,
    #   and nobody wants to reimplement happy eyeballs, address fallback, etc
    # * If any public name resolves to one of these ranges anyway, it's either
    #   misconfigured or malicious

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        try:
            self._check_addrinfo(
                request, socket.getaddrinfo(*self._request_to_addrinfo(request))
            )
        except socket.gaierror:
            # Some kind of look up error. Gonna assume safe and let farther
            # down the stack handle it.
            pass
        return self.wrappee.handle_request(request)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        try:
            self._check_addrinfo(
                request,
                await asyncio.get_running_loop().getaddrinfo(
                    *self._request_to_addrinfo(request)
                ),
            )
        except socket.gaierror:
            # Some kind of look up error. Gonna assume safe and let farther
            # down the stack handle it.
            pass
        return await self.wrappee.handle_async_request(request)


def _wrap_transport(
    blocked_ranges: list[ipaddress.IPv4Network | ipaddress.IPv6Network | str]
    | None
    | EllipsisType,
    transport,
):
    """
    Gets an (Async)Transport that blocks the given IP ranges
    """
    if blocked_ranges is ...:
        blocked_ranges = settings.HTTP_BLOCKED_RANGES

    if not blocked_ranges:
        return transport

    blocked_ranges = [
        ipaddress.ip_network(net) if isinstance(net, str) else net
        for net in typing.cast(typing.Iterable, blocked_ranges)
    ]
    return IpFilterWrapperTransport(blocked_ranges, transport)


class BaseClient(httpx._client.BaseClient):
    def __init__(
        self,
        *,
        actor: SigningActor | None = None,
        blocked_ranges: list[ipaddress.IPv4Network | ipaddress.IPv6Network | str]
        | None
        | EllipsisType = ...,
        timeout: TimeoutTypes = settings.SETUP.REMOTE_TIMEOUT,
        **opts,
    ):
        """
        Params:
          actor: Actor to sign requests as, or None to not sign requests.
          blocked_ranges: IP address to refuse to connect to. Either a list of
                         Networks, None to disable the feature, or Ellipsis to
                         pull the Django setting.
        """
        if actor:
            opts["auth"] = SignedAuth(actor)
        self._blocked_ranges = blocked_ranges

        super().__init__(timeout=timeout, **opts)

    def _init_transport(self, *p, **kw):
        transport = super()._init_transport(*p, **kw)
        return _wrap_transport(self._blocked_ranges, transport)

    def build_request(self, *pargs, **kwargs):
        request = super().build_request(*pargs, **kwargs)

        # GET requests get implicit accept headers added
        if request.method == "GET" and "Accept" not in request.headers:
            request.headers["Accept"] = "application/ld+json"

        # TODO: Move this to __init__
        request.headers["User-Agent"] = settings.TAKAHE_USER_AGENT
        return request


# BaseClient before (Async)Client because __init__


class Client(BaseClient, httpx.Client):
    def request(self, method: str, url: URLTypes, **params) -> httpx.Response:
        """
        Wraps some errors up nicer
        """
        if method.lower == "get":
            if params["follow_redirects"] is httpx._client.USE_CLIENT_DEFAULT:
                params["follow_redirects"] = True

        try:
            response = super().request(method, url, **params)
        except SSLError as invalid_cert:
            # Not our problem if the other end doesn't have proper SSL
            logger.info("Invalid cert on %s %s", url, invalid_cert)
            raise SSLCertVerificationError(invalid_cert) from invalid_cert
        except InvalidCodepoint as ex:
            # Convert to a more generic error we handle
            raise httpx.HTTPError(f"InvalidCodepoint: {str(ex)}") from None
        else:
            return response

    # Deliberately not doing the above to stream() because those use cases don't
    # want that handling

    def get(
        self, url: URLTypes, *, accept: str | None = "application/ld+json", **params
    ):
        """
        Args:
          accept: Accept header, set to None to get the open option
        """
        if accept:
            params.setdefault("headers", {})["Accept"] = accept
        return super().get(url, **params)

    def post2(self, url: URLTypes, *, activity=None, **params):
        """
        Like .post() but:

        * Adds activity which is like json but for activities
        * Handles response errors a bit
        """
        if activity is not None:
            params["json"] = activity
            params.setdefault("headers", {}).setdefault(
                "Content-Type", "application/activity+json"
            )

        response = self.post(url, **params)

        if (
            response.status_code >= 400
            and response.status_code < 500
            and response.status_code != 404
        ):
            raise ValueError(
                f"POST error to {url}: {response.status_code} {response.content!r}"
            )
        return response


class AsyncClient(BaseClient, httpx.AsyncClient):
    # FIXME: Add the fancy methods the sync version has.
    # (I'm being lazy because I don't think anyone's making async requests)
    pass
