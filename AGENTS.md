# Hermes Plugins — Agent Guidelines

## Project Info

| | |
|---|---|
| **Path** | `~/Work/hermes-memory-providers/` |
| **Remote** | `https://github.com/deuriib/hermes-memory-providers.git` |

## What this repo is

A curated monorepo of plugins for [Hermes Agent](https://github.com/NousResearch/hermes-agent). Organized by category to extend Hermes with memory providers, tools, connectors, and workflows.

**Why this matters:** Hermes Agent is designed to be extensible. Instead of hunting scattered repositories, this monorepo provides battle-tested plugins with consistent structure, documentation, and quality standards.

## Plugin Categories

### Memory Providers
| Plugin | Backend | Status |
|--------|---------|--------|
| `memory/engram/` | Engram HTTP API (Go/SQLite) | Stable |

### Tools & Connectors
*Coming soon — submit yours!*

## Adding a new plugin

```
hermes-memory-providers/
  plugins/
    category/              ← memory, tools, connectors, workflows
      plugin-name/         ← one directory per plugin
        __init__.py        ← main class + register() function
        client.py          ← backend client (if needed)
        schemas.py         ← tool/API definitions
        plugin.yaml        ← metadata (name, version, type)
        README.md          ← usage & setup docs
      DESCRIPTION.md       ← category overview
```

### Plugin structure requirements

1. **`__init__.py`** must expose:
   - `register(ctx)` — called by Hermes to register the plugin
   - Main class implementing the appropriate interface

2. **`client.py`** wraps backend APIs (if applicable)

3. **`plugin.yaml`** metadata:
```yaml
name: <plugin-name>
version: 1.0.0
type: memory_provider | tool | connector | workflow
category: memory | tools | connectors | workflows
```

4. **Deploy** with:
```bash
cp -r <category>/<plugin>/ ~/.hermes/hermes-agent/plugins/<category>/<plugin>/
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
mise run install memory/engram      # install by category/name
mise run uninstall memory/engram    # remove
mise run update memory/engram       # pull + reinstall
mise run list                       # show all by category

# Direct bin scripts (don't need mise)
bin/hm-install memory/engram
bin/hm-uninstall memory/engram --purge
bin/hm-update
bin/hm-list
```

## Engram plugin notes

- Requires `engram serve` on `http://127.0.0.1:7437`
- Session ID derived from Hermes session_id
- Project name auto-detected from git remote origin
- Cron guard: skips passive writes for `cron` and `flush` contexts
- Prefetch: background `/context` fetch via daemon thread
