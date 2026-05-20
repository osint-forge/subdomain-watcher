"""Discord webhook notifications with embeds."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from subdomain_watcher.ping import HTTPPingResult, ICMPPingResult, PingResult

logger = logging.getLogger(__name__)

# Max retries for rate-limited requests
MAX_RATE_LIMIT_RETRIES = 3


class WebhookError(Exception):
    """Raised when a Discord webhook notification fails."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


# Discord embed colors
COLOR_GREEN = 0x2ECC71  # Success - at least one ping succeeded
COLOR_RED = 0xE74C3C  # Failure - both pings failed / error


async def _post_webhook(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
) -> httpx.Response:
    """
    Post to a Discord webhook with automatic rate limit handling.

    Retries on 429 responses, waiting for the Retry-After duration.

    Args:
        client: The httpx client to use.
        url: The webhook URL.
        payload: The JSON payload to send.

    Returns:
        The successful response.

    Raises:
        httpx.HTTPStatusError: If the request fails after retries.
        httpx.RequestError: If a network error occurs.
    """
    response: httpx.Response | None = None

    for attempt in range(MAX_RATE_LIMIT_RETRIES):
        response = await client.post(url, json=payload)

        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", 1))
            logger.warning(
                "Rate limited by Discord, retrying after %ss (attempt %s/%s)",
                retry_after,
                attempt + 1,
                MAX_RATE_LIMIT_RETRIES,
            )
            await asyncio.sleep(retry_after)
            continue

        # Not rate limited, return the response (caller handles errors)
        return response

    # Exhausted retries, return last response (will be a 429)
    # This should never be None since MAX_RATE_LIMIT_RETRIES >= 1
    assert response is not None  # noqa: S101
    return response


def _format_icmp_status(icmp: ICMPPingResult) -> str:
    """Format ICMP ping status for embed field."""
    if icmp.success:
        latency = f" ({icmp.latency_ms:.1f}ms)" if icmp.latency_ms else ""
        return f"✅ Online{latency}"
    error = f" - {icmp.error}" if icmp.error else ""
    return f"❌ Offline{error}"


def _format_http_status(http: HTTPPingResult) -> str:
    """Format HTTP ping status for embed field."""
    if http.success:
        latency = f" ({http.latency_ms:.1f}ms)" if http.latency_ms else ""
        return f"✅ {http.status_code} ({http.protocol}){latency}"
    error = f" - {http.error}" if http.error else ""
    return f"❌ Unreachable{error}"


def _build_subdomain_embed(
    domain: str,
    subdomain: str,
    ping_result: PingResult,
) -> dict[str, Any]:
    """Build a Discord embed for a new subdomain notification."""
    color = COLOR_GREEN if ping_result.is_online else COLOR_RED
    timestamp = datetime.now(UTC).isoformat()

    fields = [
        {"name": "Domain", "value": f"`{domain}`", "inline": True},
        {"name": "Subdomain", "value": f"`{subdomain}`", "inline": True},
        {"name": "\u200b", "value": "\u200b", "inline": True},  # Spacer
    ]

    # Only add ICMP field if enabled
    if ping_result.icmp is not None:
        fields.append(
            {
                "name": "ICMP",
                "value": _format_icmp_status(ping_result.icmp),
                "inline": True,
            },
        )

    # Only add HTTP field if enabled
    if ping_result.http is not None:
        fields.append(
            {
                "name": "HTTP",
                "value": _format_http_status(ping_result.http),
                "inline": True,
            },
        )

    # Add spacer if we have ping fields (for alignment)
    if ping_result.icmp is not None or ping_result.http is not None:
        fields.append({"name": "\u200b", "value": "\u200b", "inline": True})

    return {
        "title": "🌐 New Subdomain Discovered",
        "color": color,
        "fields": fields,
        "timestamp": timestamp,
        "footer": {"text": "Subdomain Watcher"},
    }


def _build_error_embed(
    error_type: str,
    domain: str | None,
    message: str,
) -> dict[str, Any]:
    """Build a Discord embed for an error notification."""
    timestamp = datetime.now(UTC).isoformat()

    fields = [
        {"name": "Type", "value": f"`{error_type}`", "inline": True},
    ]

    if domain:
        fields.append({"name": "Domain", "value": f"`{domain}`", "inline": True})

    fields.append({"name": "Message", "value": f"```{message}```", "inline": False})

    return {
        "title": "❌ Error",
        "color": COLOR_RED,
        "fields": fields,
        "timestamp": timestamp,
        "footer": {"text": "Subdomain Watcher"},
    }


async def send_subdomain_notification(
    client: httpx.AsyncClient,
    webhook_url: str,
    domain: str,
    subdomain: str,
    ping_result: PingResult,
) -> None:
    """
    Send a Discord notification for a newly discovered subdomain.

    Args:
        client: The httpx client to use for the request.
        webhook_url: The Discord webhook URL.
        domain: The parent domain.
        subdomain: The discovered subdomain.
        ping_result: The ping result for the subdomain.

    Raises:
        WebhookError: If the notification fails to send.
    """
    embed = _build_subdomain_embed(domain, subdomain, ping_result)
    payload = {"embeds": [embed]}

    try:
        response = await _post_webhook(client, webhook_url, payload)
        response.raise_for_status()
        logger.debug("Sent notification for %s", subdomain)
    except httpx.HTTPStatusError as e:
        msg = f"Discord API error: {e.response.status_code} - {e.response.text}"
        logger.exception("Discord API error: %s - %s", e.response.status_code, e.response.text)
        raise WebhookError(msg) from e
    except httpx.RequestError:
        logger.exception("Failed to send Discord notification")
        raise WebhookError("Failed to send Discord notification") from None


async def send_error_notification(
    client: httpx.AsyncClient,
    webhook_url: str,
    error_type: str,
    message: str,
    domain: str | None = None,
) -> bool:
    """
    Send a Discord notification for an error.

    Args:
        client: The httpx client to use for the request.
        webhook_url: The Discord webhook URL for errors.
        error_type: The type/class of the error.
        message: The error message.
        domain: Optional domain associated with the error.

    Returns:
        True if the notification was sent successfully, False otherwise.
    """
    embed = _build_error_embed(error_type, domain, message)
    payload = {"embeds": [embed]}

    try:
        response = await _post_webhook(client, webhook_url, payload)
        response.raise_for_status()
        logger.debug("Sent error notification: %s", error_type)
    except httpx.HTTPStatusError as e:
        logger.exception(
            "Discord API error (error webhook): %s - %s",
            e.response.status_code,
            e.response.text,
        )
        return False
    except httpx.RequestError:
        logger.exception("Failed to send Discord error notification")
        return False
    else:
        return True
