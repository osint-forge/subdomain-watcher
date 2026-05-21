"""Entry point for the subdomain watcher."""

import asyncio
import contextlib
import logging
import sys
from pathlib import Path

import httpx

from subdomain_watcher.config import load_config
from subdomain_watcher.database import Database
from subdomain_watcher.watcher import run_watcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point for the subdomain watcher."""
    config_path = Path("config.yaml")

    logger.info("Loading configuration...")
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        logger.exception("Configuration file not found: %s", config_path)
        sys.exit(1)
    except Exception:
        logger.exception("Failed to load configuration")
        sys.exit(1)

    logger.info("Loaded configuration with %s domain(s)", len(config.domains))

    logger.info("Initializing database...")
    try:
        db = Database()
        await db.init_db()
    except Exception:
        logger.exception("Failed to initialize database")
        sys.exit(1)

    logger.info("Database initialized")

    # Create shared httpx client with appropriate settings
    async with httpx.AsyncClient(
        timeout=config.http_timeout,
        follow_redirects=True,
        verify=False,  # noqa: S501 # Allow self-signed certs for subdomain checks
    ) as client:
        try:
            await run_watcher(client, config, db)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await db.close()
            logger.info("Shutdown complete")


def run() -> None:
    """Entry point for the console script."""
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())


if __name__ == "__main__":
    run()
