# MCP Server IMAP

An MCP (Model Context Protocol) server that provides IMAP (Internet Message Access Protocol) capabilities to AI assistants.
This server allows AI assistants to interact with email servers to list folders, search for emails, and fetch email content.

## Features

- **List email folders**: Get a list of all folders on the IMAP server
- **Search emails**: Search for emails in a specified folder using a powerful query DSL (returns headers only)
- **Fetch email content**: Retrieve the body content of specific emails by message ID

## Installation

### Prerequisites

- Python 3.10 or higher
- uv
- An IMAP email account

### Install from source

```bash
# Clone the repository
git clone https://github.com/fgken/mcp-server-imap.git
cd mcp-server-imap

# Create and activate a virtual environment
uv venv

# Install dependencies
uv sync
```

## Usage

### Running the server

```bash
# Set environment variables
export IMAP_USER="your_username"
export IMAP_PASSWORD="your_password"

uv run main.py --server imap.example.com --port 993 --use-starttls
```

Options:

- `--server`: IMAP server hostname (required)
- `--port`: IMAP server port (default: 993 for TLS, 143 for STARTTLS)
- `--user`: IMAP username (can also use IMAP_USER environment variable)
- `--password`: IMAP password (can also use IMAP_PASSWORD environment variable)
- `--use-starttls`: Use STARTTLS instead of direct TLS (optional)

### Configuring in Cline MCP settings

To use this server with Cline or other MCP-compatible assistants, add it to your MCP settings:

```json
{
  "mcpServers": {
    "imap": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to//mcp-server-imap",
        "run",
        "main.py",
        "--server",
        "imap.example.com",
        "--port",
        "993",
        "--use-starttls"
      ],
      "env": {
        "IMAP_USER": "your_username",
        "IMAP_PASSWORD": "your_password"
      }
    }
  }
}
```

### Running Tests

```bash
uv run pytest
```
