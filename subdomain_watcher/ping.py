"""Ping utilities for checking subdomain availability."""

import asyncio
import logging
from dataclasses import dataclass

import httpx
from icmplib import NameLookupError, async_ping

logger = logging.getLogger(__name__)


@dataclass
class ICMPPingResult:
    """Result of an ICMP ping."""

    success: bool
    latency_ms: float | None = None
    error: str | None = None


@dataclass
class HTTPPingResult:
    """Result of an HTTP/HTTPS ping."""

    success: bool
    status_code: int | None = None
    protocol: str | None = None  # "HTTPS" or "HTTP"
    latency_ms: float | None = None
    error: str | None = None


@dataclass
class PingResult:
    """Combined result of ICMP and HTTP pings."""

    icmp: ICMPPingResult | None  # None = disabled
    http: HTTPPingResult | None  # None = disabled

    @property
    def is_online(self) -> bool:
        """
        Return True if any enabled ping succeeded.

        If all pings are disabled, returns True (unknown = assume online).
        """
        icmp_success = self.icmp.success if self.icmp else None
        http_success = self.http.success if self.http else None

        # Collect results from enabled pings only
        results = [r for r in (icmp_success, http_success) if r is not None]

        # If no pings enabled, default to True (unknown = assume online)
        if not results:
            return True

        # Online if any enabled ping succeeded
        return any(results)


async def icmp_ping(host: str, ping_timeout: int = 5) -> ICMPPingResult:
    """
    Perform an ICMP ping to the host.

    Args:
        host: The hostname or IP to ping.
        ping_timeout: Timeout in seconds.

    Returns:
        ICMPPingResult with success status and latency.
    """
    try:
        result = await async_ping(host, count=1, timeout=ping_timeout, privileged=True)

        if result.is_alive:
            return ICMPPingResult(success=True, latency_ms=result.avg_rtt)
        return ICMPPingResult(success=False, error="Host unreachable")

    except NameLookupError:
        return ICMPPingResult(success=False, error="DNS lookup failed")
    except PermissionError:
        return ICMPPingResult(success=False, error="Permission denied (requires root)")
    except Exception as e:
        return ICMPPingResult(success=False, error=str(e))


async def http_ping(
    client: httpx.AsyncClient,
    host: str,
    request_timeout: float = 10.0,
) -> HTTPPingResult:
    """
    Perform an HTTP/HTTPS ping to the host.

    Tries HTTPS first, falls back to HTTP if HTTPS fails.
    Any response (including 4xx/5xx) is considered "online".

    Args:
        client: The httpx client to use for the request.
        host: The hostname to ping.
        request_timeout: Timeout in seconds.

    Returns:
        HTTPPingResult with success status, status code, and protocol.
    """
    # Try HTTPS first
    for protocol in ("https", "http"):
        url = f"{protocol}://{host}"
        try:
            start = asyncio.get_event_loop().time()
            response = await client.get(url, timeout=request_timeout)
            end = asyncio.get_event_loop().time()
            latency_ms = (end - start) * 1000

            return HTTPPingResult(
                success=True,
                status_code=response.status_code,
                protocol=protocol.upper(),
                latency_ms=round(latency_ms, 2),
            )

        except httpx.ConnectError:
            continue
        except httpx.TimeoutException:
            continue
        except httpx.RequestError as e:
            logger.debug("HTTP request error for %s: %s", url, e)
            continue
        except Exception as e:
            logger.debug("Unexpected error for %s: %s", url, e)
            continue

    return HTTPPingResult(success=False, error="Connection failed")


async def ping_subdomain(
    client: httpx.AsyncClient,
    host: str,
    http_timeout: float = 10.0,
    icmp_enabled: bool = True,
    http_enabled: bool = True,
) -> PingResult:
    """
    Perform ICMP and/or HTTP pings to a subdomain based on enabled flags.

    Args:
        client: The httpx client to use for HTTP requests.
        host: The subdomain hostname to ping.
        http_timeout: Timeout for HTTP requests in seconds.
        icmp_enabled: Whether to perform ICMP ping.
        http_enabled: Whether to perform HTTP ping.

    Returns:
        PingResult with enabled ping results (None for disabled pings).
    """
    tasks: dict[str, asyncio.Task] = {}

    async with asyncio.TaskGroup() as tg:
        if icmp_enabled:
            tasks["icmp"] = tg.create_task(icmp_ping(host))
        if http_enabled:
            tasks["http"] = tg.create_task(
                http_ping(client, host, request_timeout=http_timeout),
            )

    return PingResult(
        icmp=tasks["icmp"].result() if "icmp" in tasks else None,
        http=tasks["http"].result() if "http" in tasks else None,
    )
