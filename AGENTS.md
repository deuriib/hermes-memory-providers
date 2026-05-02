# Hermes Memory Providers — Agent Guidelines

## What this repo is

Monorepo of memory provider plugins for [Hermes Agent](https://github.com/Gentleman-Programming/hermes-agent). Each plugin implements the `MemoryProvider` ABC and integrates a different memory backend.

## Current plugins

| Plugin | Backend | Status |
|--------|---------|--------|
| `engram/` | Engram HTTP API (Go/SQLite) | Stable |

## Adding a new plugin

```
hermes-memory-providers/
  engram/           ← one directory per plugin
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
# Symlink for live development
ln -s ~/Work/engram-memory/<plugin>/ \
  ~/.hermes/hermes-agent/plugins/memory/<plugin>/

# Verify registration
hermes memory list
```

## Engram plugin notes

- Requires `engram serve` on `http://127.0.0.1:7437`
- Session ID derived from Hermes session_id
- Project name auto-detected from git remote origin
- Cron guard: skips passive writes for `cron` and `flush` contexts
- Prefetch: background `/context` fetch via daemon thread
