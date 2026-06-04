# Subdomain Watcher

A tool that periodically discovers new subdomains using [subfinder](https://github.com/projectdiscovery/subfinder) and sends notifications to Discord webhooks with ping status information.

## Features

- Periodic subdomain discovery using subfinder
- Discord webhook notifications with rich embeds
- ICMP and HTTP ping status for each discovered subdomain
- Optional DNS resolution with IP address reporting
- Optional source attribution showing which passive sources found each subdomain
- Recursive and all-source subfinder discovery modes
- Optional subfinder provider config for API-backed sources
- SQLite database for tracking discovered subdomains
- Per-domain webhook and refresh interval overrides
- Parallel scanning of multiple domains
- Error notifications to a separate webhook

## Quick Start

1. Copy the example configuration file:
   ```bash
   cp config.yaml.example config.yaml
   ```

2. Edit `config.yaml` with your Discord webhook URLs and domains to watch.

3. Start with Docker Compose:

   - **Production** (published image):
     ```bash
     docker compose -f compose.prod.yaml up -d
     ```

   - **Development** (source build):
     ```bash
     docker compose -f compose.yaml up -d
     ```

## Configuration

### Configuration File (`config.yaml`)

```yaml
# Discord webhook URL for new subdomain notifications
webhook_url: "https://discord.com/api/webhooks/..."

# Discord webhook URL for error notifications (required)
error_webhook_url: "https://discord.com/api/webhooks/..."

# Global refresh interval in seconds (default: 3600 = 1 hour)
refresh_interval: 3600

# HTTP timeout in seconds for ping checks (default: 10)
http_timeout: 10

# App-level hard timeout for the whole subfinder process (default: 300 seconds)
subfinder_process_timeout: 300

# Enable ICMP ping checks globally (default: true)
icmp_enabled: true

# Enable HTTP ping checks globally (default: true)
http_enabled: true

# Enable DNS resolution globally (default: true)
dns_enabled: true

# Collect data sources for each discovered subdomain (default: false)
# When enabled, the Sources field is included in Discord notifications.
collect_sources: false

# Only use recursive-capable sources (default: false)
recursive: false

# Use all available subfinder sources globally (default: false)
all_sources: false

# Optional subfinder optimization settings.
# These are only passed to subfinder when configured.
# subfinder_request_timeout maps to subfinder -timeout, in seconds.
# subfinder_max_time maps to subfinder -max-time, in minutes.
# subfinder_request_timeout: 30
# subfinder_max_time: 10

# List of domains to watch
domains:
  - domain: "example.com"

  - domain: "another.com"
    # Optional per-domain overrides:
    webhook_url: "https://discord.com/api/webhooks/..."
    refresh_interval: 1800
    icmp_enabled: false
    http_enabled: true
    dns_enabled: true
    collect_sources: true
    recursive: true
    all_sources: true
    subfinder_request_timeout: 30
    subfinder_max_time: 10
```

### Subfinder Provider Config

If you want to use API-backed sources, copy or rename `provider-config.yaml.example` to `provider-config.yaml`, add your API keys, and uncomment this line in `compose.yaml` or `compose.prod.yaml`:

```yaml
# - ./provider-config.yaml:/app/provider-config.yaml:ro
```

For the expected provider config format and example source entries, see Subfinder’s [official documentation](https://docs.projectdiscovery.io/opensource/subfinder/install#example-provider-config).

## Discord Notifications

### New Subdomain

When a new subdomain is discovered, a notification is sent with:
- Parent domain and subdomain
- ICMP ping status (online/offline with latency)
- HTTP status code and protocol (HTTPS/HTTP)
- DNS lookup result with resolved IPs or a short lookup error
- Wildcard status from subfinder metadata
- Green embed color if either ping succeeds, red if both fail
- Data sources that discovered the subdomain (when `collect_sources` is enabled)

### Error Notifications

Errors are sent to the error webhook with:
- Error type
- Affected domain (if applicable)
- Error message
- Timestamp

## Development

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) for dependency management
- [subfinder](https://github.com/projectdiscovery/subfinder) installed and in PATH
- Docker (for running with Docker Compose)

### Local Setup

```bash
# Install dependencies
uv sync

# Run locally
uv run python -m subdomain_watcher.main
```

## License

MIT
