"""Configuration models and YAML loading for subdomain watcher."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, PositiveInt


class DomainConfig(BaseModel):
    """Configuration for a single domain to watch."""

    model_config = ConfigDict(extra="forbid")

    domain: str
    webhook_url: HttpUrl | None = None
    refresh_interval: PositiveInt | None = None
    icmp_enabled: bool | None = None
    http_enabled: bool | None = None
    collect_sources: bool | None = None
    recursive: bool | None = None
    all_sources: bool | None = None
    dns_enabled: bool | None = None
    subfinder_request_timeout: PositiveInt | None = None
    subfinder_max_time: PositiveInt | None = None


class Config(BaseModel):
    """Main configuration for the subdomain watcher."""

    model_config = ConfigDict(extra="forbid")

    webhook_url: HttpUrl
    error_webhook_url: HttpUrl
    refresh_interval: PositiveInt = 3600  # seconds
    http_timeout: PositiveInt = 10  # seconds
    subfinder_process_timeout: PositiveInt = 300  # seconds
    icmp_enabled: bool = True
    http_enabled: bool = True
    collect_sources: bool = False
    recursive: bool = False
    all_sources: bool = False
    dns_enabled: bool = True
    subfinder_request_timeout: PositiveInt | None = None
    subfinder_max_time: PositiveInt | None = None
    domains: list[DomainConfig] = Field(min_length=1)

    def get_webhook_url(self, domain_config: DomainConfig) -> str:
        """Get the effective webhook URL for a domain (with fallback to global)."""
        url = domain_config.webhook_url or self.webhook_url
        return str(url)

    def get_refresh_interval(self, domain_config: DomainConfig) -> int:
        """Get the effective refresh interval for a domain (with fallback to global)."""
        return domain_config.refresh_interval or self.refresh_interval

    def get_icmp_enabled(self, domain_config: DomainConfig) -> bool:
        """Get the effective ICMP enabled setting for a domain (with fallback to global)."""
        if domain_config.icmp_enabled is not None:
            return domain_config.icmp_enabled
        return self.icmp_enabled

    def get_http_enabled(self, domain_config: DomainConfig) -> bool:
        """Get the effective HTTP enabled setting for a domain (with fallback to global)."""
        if domain_config.http_enabled is not None:
            return domain_config.http_enabled
        return self.http_enabled

    def get_collect_sources(self, domain_config: DomainConfig) -> bool:
        """Get the effective collect_sources setting for a domain (with fallback to global)."""
        if domain_config.collect_sources is not None:
            return domain_config.collect_sources
        return self.collect_sources

    def get_recursive(self, domain_config: DomainConfig) -> bool:
        """Get the effective recursive setting for a domain (with fallback to global)."""
        if domain_config.recursive is not None:
            return domain_config.recursive
        return self.recursive

    def get_all_sources(self, domain_config: DomainConfig) -> bool:
        """Get the effective all_sources setting for a domain (with fallback to global)."""
        if domain_config.all_sources is not None:
            return domain_config.all_sources
        return self.all_sources

    def get_dns_enabled(self, domain_config: DomainConfig) -> bool:
        """Get the effective DNS enabled setting for a domain (with fallback to global)."""
        if domain_config.dns_enabled is not None:
            return domain_config.dns_enabled
        return self.dns_enabled

    def get_subfinder_request_timeout(
        self,
        domain_config: DomainConfig,
    ) -> int | None:
        """Get the effective subfinder request timeout for a domain."""
        if domain_config.subfinder_request_timeout is not None:
            return domain_config.subfinder_request_timeout
        return self.subfinder_request_timeout

    def get_subfinder_max_time(self, domain_config: DomainConfig) -> int | None:
        """Get the effective subfinder max time for a domain."""
        if domain_config.subfinder_max_time is not None:
            return domain_config.subfinder_max_time
        return self.subfinder_max_time


def load_config(path: Path | str = "config.yaml") -> Config:
    """Load and validate configuration from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open() as f:
        data = yaml.safe_load(f)

    return Config.model_validate(data)
