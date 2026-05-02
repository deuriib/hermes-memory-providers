# Engram Memory Provider

> Local-first persistent memory for Hermes Agent using Go/SQLite HTTP API

## What is Engram?

**Engram is your Hermes Agent's local memory vault.** It stores everything your AI assistant learns across sessions — decisions, discoveries, patterns, and preferences — in a fast, reliable SQLite database accessed via a clean HTTP API.

**Perfect for:**
- 🏠 **Local development** — keep your data on your machine
- ⚡ **Fast queries** — SQLite performance with HTTP convenience
- 🔒 **Privacy-first** — no cloud dependencies, full data control
- 🚀 **Zero config** — works out of the box

## Quick Start

### 1. Install Engram Server

```bash
# Install the Engram binary
go install github.com/deuriib/engram@latest

# Start the server (runs on :7437)
engram serve
```

### 2. Install Memory Provider

```bash
# From the hermes-memory-providers repo
./bin/hm-install engram

# Or using mise
mise run install engram
```

### 3. Restart Hermes

Your Hermes Agent will automatically discover and use the Engram memory provider on next startup.

## How It Works

```
┌─────────────────┐    HTTP API     ┌──────────────┐    SQLite     ┌─────────────┐
│                 │   (port 7437)   │              │               │             │
│  Hermes Agent   │◄────────────────►│    Engram    │◄─────────────►│   Database  │
│                 │                  │    Server    │               │             │
└─────────────────┘                  └──────────────┘               └─────────────┘
```

**The flow:**
1. Hermes learns something important (bug fix, user preference, etc.)
2. Engram provider sends it to the HTTP API (:7437)
3. Engram server stores it in SQLite with full-text search
4. Future sessions can search and retrieve this knowledge

## Configuration

### Server Settings

```bash
# Default: http://127.0.0.1:7437
engram serve --port 8080 --host 0.0.0.0

# Custom database location
engram serve --db-path /custom/path/memory.db
```

### Provider Settings

The plugin auto-detects your project from git remote and creates session IDs from Hermes context. No manual config needed.

## Features

### 🧠 Smart Memory Management
- **Automatic categorization** — decisions, bugs, patterns, discoveries
- **Project-scoped storage** — memories tied to specific codebases
- **Session tracking** — full context of when and why something was learned

### 🔍 Powerful Search
- **Full-text search** across all stored memories
- **Semantic filtering** by type, project, timeframe
- **Context retrieval** — get the full story, not just fragments

### ⚡ Performance Optimized
- **Background sync** — non-blocking memory writes
- **Connection pooling** — efficient HTTP client management
- **Cron guards** — skips writes during automated tasks

### 🛡️ Reliability
- **Graceful degradation** — Hermes works even if Engram is down
- **Error recovery** — automatic retries with backoff
- **Health monitoring** — startup checks ensure connectivity

## API Reference

The Engram server exposes these endpoints:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/save` | Store new memory observation |
| `GET` | `/search` | Search memories with filters |
| `GET` | `/get/{id}` | Retrieve specific observation |
| `GET` | `/context` | Get recent session context |
| `GET` | `/health` | Server health check |

## Troubleshooting

### "Connection refused" errors

```bash
# Check if Engram server is running
curl http://127.0.0.1:7437/health

# If not, start it
engram serve
```

### Memory not persisting

- Verify Hermes detected the plugin: check startup logs for "Engram memory provider registered"
- Check Engram server logs for incoming requests
- Ensure your project has a git remote (used for project detection)

### Performance issues

- **Large databases**: Consider periodic cleanup of old memories
- **Network latency**: Run Engram on localhost for best performance
- **High memory usage**: SQLite handles most datasets efficiently; check for runaway queries

### Plugin not loading

```bash
# Reinstall the provider
./bin/hm-uninstall engram --purge
./bin/hm-install engram

# Check Hermes plugin directory
ls ~/.hermes/hermes-agent/plugins/memory/
```

## Advanced Usage

### Multiple Projects

Engram automatically scopes memories by project (detected from git remote). No additional setup needed for multi-project workflows.

### Custom Schemas

Extend the memory schema by modifying `schemas.py` to include project-specific memory types or search filters.

### Backup & Restore

```bash
# Backup your memory database
cp ~/.engram/memory.db /backup/location/

# Restore from backup
cp /backup/location/memory.db ~/.engram/memory.db
engram serve
```

## Development

### Local Testing

```bash
# Start Engram server in dev mode
engram serve --verbose

# Install plugin locally
./bin/hm-install engram

# Test with Hermes
hermes "Remember: I prefer TypeScript over JavaScript"
```

### Plugin Architecture

- **`__init__.py`** — `EngramMemoryProvider` class + `register()` function
- **`client.py`** — HTTP client with connection pooling and retries
- **`schemas.py`** — Hermes tool definitions for memory operations
- **`plugin.yaml`** — Metadata for plugin discovery

---

**Questions?** Check the [main repository](../../README.md) or open an issue.

**Ready to remember everything?** Install Engram and never lose context again.