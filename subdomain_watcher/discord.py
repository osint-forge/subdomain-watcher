"""Discord webhook notifications with embeds."""

import logging
from datetime import UTC, datetime

import aiohttp
import discord

from subdomain_watcher.ping import HTTPPingResult, ICMPPingResult, PingResult

logger = logging.getLogger(__name__)


class WebhookError(Exception):
    """Raised when a Discord webhook notification fails."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


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
        return f"✅ {http.protocol} {http.status_code}{latency}"
    error = f" - {http.error}" if http.error else ""
    return f"❌ Unreachable{error}"


def _build_subdomain_embed(
    domain: str,
    subdomain: str,
    ping_result: PingResult,
    sources: list[str],
) -> discord.Embed:
    """Build a Discord embed for a new subdomain notification."""
    colour = discord.Colour.green() if ping_result.is_online else discord.Colour.red()
    embed = discord.Embed(
        title="🌐 New Subdomain Discovered",
        colour=colour,
        timestamp=datetime.now(UTC),
    )
    embed.set_footer(text="Subdomain Watcher")
    embed.add_field(name="Subdomain", value=f"`{subdomain}`", inline=True)
    embed.add_field(name="Domain", value=f"`{domain}`", inline=True)
    embed.add_field(
        name="\u200b", value="\u200b", inline=True
    )  # Spacer to force 2x2 layout

    # Only add ICMP field if enabled
    if ping_result.icmp is not None:
        embed.add_field(
            name="ICMP",
            value=_format_icmp_status(ping_result.icmp),
            inline=True,
        )

    # Only add HTTP field if enabled
    if ping_result.http is not None:
        embed.add_field(
            name="HTTP",
            value=_format_http_status(ping_result.http),
            inline=True,
        )

    # Add second spacer if we have ping fields (for alignment)
    if ping_result.icmp is not None or ping_result.http is not None:
        embed.add_field(name="\u200b", value="\u200b", inline=True)

    # Add sources field if available
    if sources:
        embed.add_field(
            name="Sources",
            value=f"`{', '.join(sources)}`",
            inline=False,
        )

    return embed


def _build_error_embed(
    error_type: str,
    domain: str | None,
    message: str,
) -> discord.Embed:
    """Build a Discord embed for an error notification."""
    embed = discord.Embed(
        title="❌ Error",
        colour=discord.Colour.red(),
        timestamp=datetime.now(UTC),
    )
    embed.set_footer(text="Subdomain Watcher")
    embed.add_field(name="Type", value=f"`{error_type}`", inline=True)

    if domain:
        embed.add_field(name="Domain", value=f"`{domain}`", inline=True)

    embed.add_field(name="Message", value=f"```{message}```", inline=False)

    return embed


async def send_subdomain_notification(
    webhook_url: str,
    domain: str,
    subdomain: str,
    ping_result: PingResult,
    sources: list[str],
) -> None:
    """
    Send a Discord notification for a newly discovered subdomain.

    Args:
        webhook_url: The Discord webhook URL.
        domain: The parent domain.
        subdomain: The discovered subdomain.
        ping_result: The ping result for the subdomain.
        sources: The data sources that discovered this subdomain.

    Raises:
        WebhookError: If the notification fails to send.
    """
    embed = _build_subdomain_embed(domain, subdomain, ping_result, sources)

    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(webhook_url, session=session)
            await webhook.send(embed=embed)
        logger.debug("Sent notification for %s", subdomain)
    except discord.HTTPException as e:
        msg = f"Discord API error: {e.status} - {e.text}"
        logger.exception("Discord API error: %s - %s", e.status, e.text)
        raise WebhookError(msg) from e


async def send_error_notification(
    webhook_url: str,
    error_type: str,
    message: str,
    domain: str | None = None,
) -> bool:
    """
    Send a Discord notification for an error.

    Args:
        webhook_url: The Discord webhook URL for errors.
        error_type: The type/class of the error.
        message: The error message.
        domain: Optional domain associated with the error.

    Returns:
        True if the notification was sent successfully, False otherwise.
    """
    embed = _build_error_embed(error_type, domain, message)

    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(webhook_url, session=session)
            await webhook.send(embed=embed)
        logger.debug("Sent error notification: %s", error_type)
    except discord.HTTPException as e:
        logger.exception(
            "Discord API error (error webhook): %s - %s",
            e.status,
            e.text,
        )
        return False
    else:
        return True
