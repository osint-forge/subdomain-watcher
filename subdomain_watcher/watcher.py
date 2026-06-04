"""Main watcher orchestration for subdomain discovery."""

import asyncio
import logging

import httpx

from subdomain_watcher.config import Config, DomainConfig
from subdomain_watcher.database import Database
from subdomain_watcher.discord import (
    WebhookError,
    send_error_notification,
    send_subdomain_notification,
)
from subdomain_watcher.ping import ping_subdomain
from subdomain_watcher.subfinder import (
    SubfinderError,
    extract_subdomains,
    run_subfinder,
)

logger = logging.getLogger(__name__)


async def watch_domain(
    client: httpx.AsyncClient,
    domain_config: DomainConfig,
    config: Config,
    db: Database,
) -> None:
    """
    Watch a single domain for new subdomains.

    Args:
        client: The httpx client to use for requests.
        domain_config: Configuration for this domain.
        config: Global configuration.
        db: Database instance.
    """
    domain = domain_config.domain
    webhook_url = config.get_webhook_url(domain_config)
    error_webhook_url = str(config.error_webhook_url)
    icmp_enabled = config.get_icmp_enabled(domain_config)
    http_enabled = config.get_http_enabled(domain_config)
    collect_sources = config.get_collect_sources(domain_config)
    recursive = config.get_recursive(domain_config)
    all_sources = config.get_all_sources(domain_config)
    subfinder_request_timeout = config.get_subfinder_request_timeout(domain_config)
    subfinder_max_time = config.get_subfinder_max_time(domain_config)

    logger.info("[%s] Scanning domain", domain)

    try:
        # Run subfinder
        results = await run_subfinder(
            domain,
            process_timeout=config.subfinder_timeout,
            collect_sources=collect_sources,
            recursive=recursive,
            all_sources=all_sources,
            request_timeout=subfinder_request_timeout,
            max_time=subfinder_max_time,
        )
        discovered_subdomains = extract_subdomains(results)

        if not discovered_subdomains:
            logger.info("[%s] No subdomain(s) found", domain)
            return

        # Get known subdomains from database
        known_subdomains = await db.get_known_subdomains(domain)

        # Find new subdomains
        discovered_hosts = set(discovered_subdomains.keys())
        new_subdomains = discovered_hosts - known_subdomains

        if not new_subdomains:
            logger.info("[%s] No new subdomain(s)", domain)
            # Update last_seen for existing subdomains
            existing = list(discovered_hosts & known_subdomains)
            if existing:
                await db.update_last_seen(domain, existing)
            return

        logger.info("[%s] Found %s new subdomain(s)", domain, len(new_subdomains))

        # Process each new subdomain
        for subdomain in new_subdomains:
            try:
                # Ping the subdomain
                ping_result = await ping_subdomain(
                    client,
                    subdomain,
                    config.http_timeout,
                    icmp_enabled=icmp_enabled,
                    http_enabled=http_enabled,
                )

                discovery = discovered_subdomains[subdomain]

                # Send Discord notification FIRST (raises WebhookError on failure)
                await send_subdomain_notification(
                    webhook_url=webhook_url,
                    domain=domain,
                    subdomain=subdomain,
                    ping_result=ping_result,
                    sources=discovery.sources,
                )

                # Only add to database AFTER successful notification
                await db.add_subdomain(domain, subdomain)

                # Small delay to avoid Discord rate limiting
                await asyncio.sleep(0.5)

            except WebhookError as e:
                # Webhook failed - subdomain NOT saved to DB, will retry next scan
                logger.warning(
                    "[%s] Skipping database save for %s due to webhook failure: %s",
                    domain,
                    subdomain,
                    e.message,
                )
                await send_error_notification(
                    webhook_url=error_webhook_url,
                    error_type="WebhookError",
                    message=e.message,
                    domain=domain,
                )
            except Exception as e:
                logger.exception(
                    "[%s] Error processing subdomain %s", domain, subdomain
                )
                await send_error_notification(
                    webhook_url=error_webhook_url,
                    error_type=type(e).__name__,
                    message=str(e),
                    domain=domain,
                )

        # Update last_seen for existing subdomains
        existing = list(discovered_hosts & known_subdomains)
        if existing:
            await db.update_last_seen(domain, existing)

    except SubfinderError as e:
        logger.exception("[%s] Subfinder error", domain)
        await send_error_notification(
            webhook_url=error_webhook_url,
            error_type="SubfinderError",
            message=e.message,
            domain=domain,
        )
    except Exception as e:
        logger.exception("[%s] Unexpected error watching domain", domain)
        await send_error_notification(
            webhook_url=error_webhook_url,
            error_type=type(e).__name__,
            message=str(e),
            domain=domain,
        )


async def domain_watcher_loop(
    client: httpx.AsyncClient,
    domain_config: DomainConfig,
    config: Config,
    db: Database,
) -> None:
    """
    Run an infinite loop watching a single domain.

    This function never raises - all exceptions are caught and logged.
    Each domain runs independently with its own refresh interval.

    Args:
        client: The httpx client to use for requests.
        domain_config: Configuration for this domain.
        config: Global configuration.
        db: Database instance.
    """
    domain = domain_config.domain
    interval = config.get_refresh_interval(domain_config)
    error_webhook_url = str(config.error_webhook_url)

    logger.info("[%s] Starting watcher loop (interval: %ss)", domain, interval)

    while True:
        try:
            await watch_domain(client, domain_config, config, db)
        except Exception as e:
            # Catch-all for anything that escapes watch_domain
            logger.exception("[%s] Unexpected error in watcher loop", domain)
            try:
                await send_error_notification(
                    webhook_url=error_webhook_url,
                    error_type=type(e).__name__,
                    message=str(e),
                    domain=domain,
                )
            except Exception:
                # Can't notify about the error - just log it
                logger.exception(
                    "[%s] Failed to send error notification",
                    domain,
                )

        logger.info("[%s] Sleeping for %s seconds", domain, interval)
        await asyncio.sleep(interval)


async def run_watcher(client: httpx.AsyncClient, config: Config, db: Database) -> None:
    """
    Run independent watcher loops for each domain.

    Each domain runs on its own schedule based on its refresh_interval.
    Uses asyncio.TaskGroup for structured concurrency.

    Args:
        client: The httpx client to use for requests.
        config: Global configuration.
        db: Database instance.
    """
    logger.info("Starting subdomain watcher with %s domain(s)", len(config.domains))

    for domain_config in config.domains:
        interval = config.get_refresh_interval(domain_config)
        logger.info("  %s (interval: %ss)", domain_config.domain, interval)

    async with asyncio.TaskGroup() as tg:
        for domain_config in config.domains:
            tg.create_task(domain_watcher_loop(client, domain_config, config, db))
