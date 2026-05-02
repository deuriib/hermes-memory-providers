# Hermes Memory Providers — Agent Guidelines

## Project Info

| | |
|---|---|
| **Path** | `~/Work/hermes-memory-providers/` |
| **Remote** | `https://github.com/deuriib/hermes-memory-providers.git` |

## What this repo is

A curated collection of memory provider plugins for [Hermes Agent](https://github.com/NousResearch/hermes-agent). Each plugin implements the `MemoryProvider` abstract base class to integrate different memory backends, enabling persistent memory across Hermes sessions with your preferred storage solution.

**Why this matters:** Hermes Agent's memory system is pluggable by design. Whether you prefer local SQLite, cloud databases, or specialized vector stores, this monorepo provides battle-tested integrations that just work.

## Current plugins

| Plugin | Backend | Status |
|--------|---------|--------|
| `engram/` | Engram HTTP API (Go/SQLite) | Stable |

## Adding a new plugin

```
hermes-memory-providers/
  plugins/
    engram/         ← one directory per plugin
    __init__.py     ← implements MemoryProvider
    client.py       ← backend client
    schemas.py      ← tool definitions
    plugin.yaml     ← plugin metadata
    README.md       ← plugin-specific docs
```

### Plugin structure requirements

1. **`__init__.py`** must expose:
   - `register(ctx)` — called by Hermes to register the provider
   - `EngramMemoryProvider` — class implementing `MemoryProvider` ABC

2. **`client.py`** wraps the backend HTTP API

3. **`plugin.yaml`** frontmatter:
```yaml
name: <plugin-name>
version: 1.0.0
type: memory_provider
```

4. **Deploy** with:
```bash
cp -r <plugin>/ ~/.hermes/hermes-agent/plugins/memory/<plugin>/
```

## Code style

- Python 3.11+
- Type hints on all public methods
- No `print()` for debugging — use the logging module
- Passive sync operations must be non-blocking (daemon threads)
- All HTTP calls need timeout=5 and proper error handling

## Testing locally

```bash
# Via mise tasks
mise run install engram      # install
mise run uninstall engram    # remove
mise run update engram       # pull + reinstall
mise run list                # show all

# Direct bin scripts (don't need mise)
bin/hm-install engram
bin/hm-uninstall engram --purge
bin/hm-update
bin/hm-list
```

## Engram plugin notes

- Requires `engram serve` on `http://127.0.0.1:7437`
- Session ID derived from Hermes session_id
- Project name auto-detected from git remote origin
- Cron guard: skips passive writes for `cron` and `flush` contexts
- Prefetch: background `/context` fetch via daemon thread
