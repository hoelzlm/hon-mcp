# hon-mcp

MCP server that lets Claude check and control Haier hOn appliances (washing machine and similar) through [pyhOn](https://github.com/Andre0512/pyhOn). Runs as a Docker container on the home server so every PC on the network can use it.

> **Unofficial.** Not affiliated with or endorsed by Haier. It uses the unofficial hOn cloud API via pyhOn, which can change or break without notice. Use at your own risk.

> **No authentication.** Anyone who can reach the port can start and stop your appliances. Keep it on the LAN or Tailscale, never expose it to the internet.

## Tools

| Tool | What it does |
|------|--------------|
| `list_appliances` | Appliances on the hOn account |
| `get_status` | Current state of an appliance |
| `list_programs` | Valid program names and settings |
| `start_program` | Start a program. **Physical action**, confirm program and settings first |
| `pause_program` | Pause the running program |
| `resume_program` | Resume a paused program |
| `stop_program` | Stop the running program |

`appliance` is optional on every tool. Leave it out when the account has one appliance.

To start a program the machine must be loaded, the door closed, and remote control enabled on the machine itself. Settings override defaults: `{"temp": "40", "spinSpeed": "1200"}`.

## Use it

Add the server to Claude Code on any PC in the network:

```bash
claude mcp add --transport http hon http://<homeserver>:8765/mcp
```

Over Tailscale use the server's Tailscale IP or MagicDNS name instead.

## Deploy (home server)

Prerequisites: Docker with Compose, and an hOn account.

```bash
cp .env.example .env     # fill in HON_EMAIL and HON_PASSWORD
chmod 600 .env
docker compose up -d --build
```

The container listens on port `8765`, endpoint `/mcp`, and restarts automatically. The Homepage labels in `compose.yaml` add a tile to the dashboard.

Run **one instance only**. hOn cloud sessions are per login, and a second instance can log the first one out.

### Environment variables

| Variable | Description |
|----------|-------------|
| `HON_EMAIL` | hOn account email |
| `HON_PASSWORD` | hOn account password |
| `MCP_TRANSPORT` | `stdio` (default) or `streamable-http`. The Dockerfile sets `streamable-http` |
| `MCP_HOST` | Bind address, default `127.0.0.1`. The Dockerfile sets `0.0.0.0` |
| `MCP_PORT` | Port, default `8765` |

## Run locally without Docker

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env     # fill in credentials
claude mcp add hon -- "$PWD/.venv/bin/python" "$PWD/server.py"
```

This uses stdio, so the server only works for the machine it runs on.

## Files

| Path | Purpose |
|------|---------|
| `server.py` | The whole server: hOn login, tools, transport selection |
| `Dockerfile` | `python:3.12-slim`, installs `requirements.txt` |
| `compose.yaml` | Container, port mapping, Homepage labels |
| `.env.example` | Variable names for `.env` (the real `.env` is git-ignored) |

## Gotchas

- **Update the server by copying files.** The home server copy in `/opt/stacks/hon-mcp` is not a git checkout. After a change, copy `server.py` there and run `docker compose up -d --build`.
- **`invalid Content-Type` when testing with curl:** send `Content-Type: application/json` and `Accept: application/json, text/event-stream`.

## License

[MIT](LICENSE)
