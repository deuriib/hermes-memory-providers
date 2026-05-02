# Hermes Memory Providers

**Plug in memory. Never explain yourself twice.**

A collection of memory provider plugins for [Hermes Agent](https://github.com/Gentleman-Programming/hermes-agent). Swap the backend, keep the workflow.

## The problem

Hermes Agent has a built-in memory, but it's ephemeral. Start a new session, and it's gone. You find yourself re-explaining the architecture, the conventions, the "remember when we fixed that bug three weeks ago" context — over and over.

This repo fixes that.

## How it works

Memory providers implement Hermes's `MemoryProvider` interface. Each one connects to a different storage backend — SQLite, vector DBs, cloud services. The agent doesn't care which one you use. You do.

```
You: "Search my memory for the auth bug we fixed in March"
       ↓
Hermes Agent (with Engram provider)
       ↓
mem_search → engram serve → SQLite
       ↓
Returns the session, the root cause, the fix.
Done in seconds. No re-explaining.
```

## Plugins

### [Engram](engram/) — Stable

Persistent cross-session memory via Engram's HTTP API (Go + SQLite).

- 15 memory tools exposed to the model
- Passive turn capture (non-blocking)
- Background context prefetch
- FTS5 search across all sessions
- Session lifecycle (resume, branch, reset)

[Install Engram →](engram/)

## Why a monorepo?

Memory providers share the same interface. When someone builds a new backend, it should be here — not as a fork, not as a hidden gist. One place to discover, compare, and contribute.

Current providers:

| Plugin | Backend | Notes |
|--------|---------|-------|
| [Engram](engram/) | SQLite + HTTP (Go) | Self-hosted, fast, full-text search |
| _yours?_ | — | [Open an issue](https://github.com/deuriib/hermes-memory-providers/issues/new) to add one |

## Adding a plugin

See [AGENTS.md](AGENTS.md) for the full plugin development guide. Short version:

```bash
# 1. Create plugin directory
mkdir my-memory-plugin && cd my-memory-plugin

# 2. Implement MemoryProvider ABC
# See AGENTS.md for the interface contract

# 3. Add plugin metadata
cat > plugin.yaml << 'EOF'
name: my-memory-plugin
version: 1.0.0
type: memory_provider
EOF

# 4. Open a PR
```

## Quick install (Engram)

```bash
# Install Engram
go install github.com/Gentleman-Programming/engram@latest

# Install the plugin
cp -r engram/ ~/.hermes/hermes-agent/plugins/memory/engram/

# Activate
hermes memory set engram
```

Requires `engram serve` running at `http://127.0.0.1:7437`.

## License

MIT — see [LICENSE](LICENSE).
