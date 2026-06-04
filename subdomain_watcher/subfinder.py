"""Subfinder integration for subdomain discovery."""

import asyncio
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_PROVIDER_CONFIG_PATH = "/app/provider-config.yaml"


@dataclass
class SubfinderResult:
    """Result from a subfinder scan."""

    host: str
    input_domain: str
    sources: list[str]
    wildcard_certificate: bool = False


@dataclass
class SubdomainDiscovery:
    """Merged discovery metadata for a subdomain."""

    sources: list[str]
    wildcard_certificate: bool


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
    collect_sources: bool = False,
    recursive: bool = False,
    all_sources: bool = False,
    request_timeout: int | None = None,
    max_time: int | None = None,
) -> list[SubfinderResult]:
    """
    Run subfinder for a domain and return discovered subdomains.

    Args:
        domain: The domain to scan for subdomains.
        process_timeout: Maximum time in seconds to wait for subfinder to complete.
        collect_sources: Whether to collect the data sources for each subdomain.
        recursive: Whether to use recursive subdomain discovery.
        all_sources: Whether to use all available sources.
        request_timeout: Seconds to wait before timing out source requests.
        max_time: Minutes to wait for enumeration results.

    Returns:
        List of SubfinderResult objects with discovered subdomains.

    Raises:
        SubfinderError: If subfinder fails or times out.
    """
    cmd = [
        "subfinder",
        "-d",
        domain,
        "-silent",
        "-json",
        "-pc",
        _PROVIDER_CONFIG_PATH,
    ]
    if collect_sources:
        cmd.append("-collect-sources")
    if recursive:
        cmd.append("-recursive")
    if all_sources:
        cmd.append("-all")
    if request_timeout is not None:
        cmd.extend(("-timeout", str(request_timeout)))
    if max_time is not None:
        cmd.extend(("-max-time", str(max_time)))

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
                        sources=_extract_sources(data),
                        wildcard_certificate=bool(
                            data.get("wildcard_certificate", False),
                        ),
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


def _extract_sources(data: dict[str, object]) -> list[str]:
    """Extract source values from subfinder JSON output."""
    sources: set[str] = set()

    raw_sources = data.get("sources")
    if isinstance(raw_sources, list):
        sources.update(str(source) for source in raw_sources if source)

    raw_source = data.get("source")
    if isinstance(raw_source, str) and raw_source:
        sources.add(raw_source)

    return sorted(sources)


def extract_subdomains(
    results: list[SubfinderResult],
) -> dict[str, SubdomainDiscovery]:
    """Extract unique subdomain hostnames and their discovery metadata."""
    subdomains: dict[str, SubdomainDiscovery] = {}
    for r in results:
        if r.host in subdomains:
            discovery = subdomains[r.host]
            existing = set(discovery.sources)
            existing.update(r.sources)
            subdomains[r.host] = SubdomainDiscovery(
                sources=sorted(existing),
                wildcard_certificate=(
                    discovery.wildcard_certificate or r.wildcard_certificate
                ),
            )
        else:
            subdomains[r.host] = SubdomainDiscovery(
                sources=r.sources.copy(),
                wildcard_certificate=r.wildcard_certificate,
            )
    return subdomains
