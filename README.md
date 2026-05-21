# Subdomain Watcher

A tool that periodically discovers new subdomains using [subfinder](https://github.com/projectdiscovery/subfinder) and sends notifications to Discord webhooks with ping status information.

## Features

- Periodic subdomain discovery using subfinder
- Discord webhook notifications with rich embeds
- ICMP and HTTP ping status for each discovered subdomain
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

# Enable ICMP ping checks globally (default: true)
icmp_enabled: true

# Enable HTTP ping checks globally (default: true)
http_enabled: true

# List of domains to watch
domains:
  - domain: "example.com"

  - domain: "another.com"
    # Optional per-domain overrides:
    webhook_url: "https://discord.com/api/webhooks/..."
    refresh_interval: 1800
    icmp_enabled: false
    http_enabled: true
```

## Discord Notifications

### New Subdomain

When a new subdomain is discovered, a notification is sent with:
- Parent domain and subdomain
- ICMP ping status (online/offline with latency)
- HTTP status code and protocol (HTTPS/HTTP)
- Green embed color if either ping succeeds, red if both fail

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
