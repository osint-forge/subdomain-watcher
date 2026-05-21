"""Subfinder integration for subdomain discovery."""

import asyncio
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SubfinderResult:
    """Result from a subfinder scan."""

    host: str
    input_domain: str
    source: str


class SubfinderError(Exception):
    """Error running subfinder."""

    def __init__(
        self,
        domain: str,
        message: str,
        return_code: int | None = None,
    ) -> None:
        self.domain = domain
        self.message = message
        self.return_code = return_code
        super().__init__(f"Subfinder error for {domain}: {message}")


async def run_subfinder(
    domain: str,
    process_timeout: int = 300,
) -> list[SubfinderResult]:
    """
    Run subfinder for a domain and return discovered subdomains.

    Args:
        domain: The domain to scan for subdomains.
        process_timeout: Maximum time in seconds to wait for subfinder to complete.

    Returns:
        List of SubfinderResult objects with discovered subdomains.

    Raises:
        SubfinderError: If subfinder fails or times out.
    """
    cmd = ["subfinder", "-d", domain, "-silent", "-json"]

    logger.info("[%s] Running subfinder", domain)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=process_timeout,
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            raise SubfinderError(
                domain=domain,
                message=f"Timed out after {process_timeout} seconds",
                return_code=None,
            ) from None

        if process.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else "Unknown error"
            raise SubfinderError(
                domain=domain,
                message=error_msg,
                return_code=process.returncode,
            )
    except FileNotFoundError:
        raise SubfinderError(
            domain=domain,
            message="subfinder binary not found. Is it installed?",
            return_code=None,
        ) from None
    else:
        results: list[SubfinderResult] = []
        for line in stdout.decode().strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                results.append(
                    SubfinderResult(
                        host=data["host"],
                        input_domain=data["input"],
                        source=data.get("source", "unknown"),
                    ),
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(
                    "[%s] Failed to parse subfinder output line: %s - %s",
                    domain,
                    line,
                    e,
                )
                continue

        logger.info("[%s] Found %s subdomain(s)", domain, len(results))
        return results


def extract_subdomains(results: list[SubfinderResult]) -> set[str]:
    """Extract unique subdomain hostnames from subfinder results."""
    return {r.host for r in results}
