"""Configuration models and YAML loading for subdomain watcher."""

from pathlib import Path

import yaml
from pydantic import BaseModel, HttpUrl


class DomainConfig(BaseModel):
    """Configuration for a single domain to watch."""

    domain: str
    webhook_url: HttpUrl | None = None
    refresh_interval: int | None = None
    icmp_enabled: bool | None = None
    http_enabled: bool | None = None


class Config(BaseModel):
    """Main configuration for the subdomain watcher."""

    webhook_url: HttpUrl
    error_webhook_url: HttpUrl
    refresh_interval: int = 3600  # seconds
    http_timeout: int = 10  # seconds
    subfinder_timeout: int = 300  # seconds
    icmp_enabled: bool = True
    http_enabled: bool = True
    domains: list[DomainConfig]

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


def load_config(path: Path | str = "config.yaml") -> Config:
    """Load and validate configuration from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open() as f:
        data = yaml.safe_load(f)

    return Config.model_validate(data)
