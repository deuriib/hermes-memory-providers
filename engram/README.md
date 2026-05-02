# Hermes Engram Memory Provider

Persistent cross-session memory for [Hermes Agent](https://github.com/Gentleman-Programming/hermes-agent) via the [Engram](https://github.com/Gentleman-Programming/engram) HTTP API.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## About

Hermes Agent has a built-in ephemeral memory. This plugin replaces it with Engram — a persistent, searchable memory layer backed by SQLite and an HTTP API. The agent remembers what it learned across sessions, can search its own memory, and gets relevant context injected before each turn.

**What makes it different from alternatives:** Engram is designed specifically for AI agent memory workflows — observations, conflict resolution, project-scoped sessions, and FTS5 search are first-class concepts. The plugin exposes all of this through Hermes's native tool-calling interface.

## Features

- **15 memory tools** exposed to the model: `mem_search`, `mem_save`, `mem_update`, `mem_delete`, `mem_context`, `mem_timeline`, `mem_session_summary`, `mem_get_observation`, `mem_save_prompt`, `mem_session_start`, `mem_session_end`, `mem_judge`, `mem_doctor`, `mem_current_project`, `mem_capture_passive`
- **Passive capture**: turns are automatically synced as observations after each exchange (non-blocking daemon thread)
- **Prefetch**: relevant context is fetched in the background before each turn
- **Project detection**: auto-detects project name from `git remote origin`
- **Cron guard**: skips passive writes for `cron` and `flush` contexts to avoid corrupting user representations
- **Session lifecycle**: full support for `/resume`, `/branch`, `/reset`, `/new` mid-process session rotation

## Requirements

- [Engram](https://github.com/Gentleman-Programming/engram) installed (`go install github.com/Gentleman-Programming/engram@latest`)
- `engram serve` running at `http://127.0.0.1:7437` (auto-started if `ENGRAM_BIN` is set)
- Hermes Agent

## Installation

### 1. Install Engram

```bash
go install github.com/Gentleman-Programming/engram@latest
# or download from https://github.com/Gentleman-Programming/engram/releases
```

### 2. Install the plugin

```bash
mise run bootstrap    # install tools + deps + plugin in one step
```

Or step by step:

```bash
mise install
uv sync
mise run install engram   # or: bin/hm-install engram
```

### 3. Activate

```bash
hermes memory set engram
```

Or add to `~/.hermes/config.yaml`:

```yaml
memory:
  provider: engram
```

### 4. Configure (optional)

Create `~/.hermes/engram.json`:

```json
{
  "enabled": true,
  "port": 7437,
  "passive_capture": true,
  "prefetch": true
}
```

Or via environment variables:

```bash
export ENGRAM_PORT=7437      # default
export ENGRAM_BIN=engram     # path to binary; default: "engram"
export ENGRAM_DISABLED=false # set to "true" to disable
```

## Usage

Once active, the agent automatically:

1. **Prefetches** relevant memory context before each turn
2. **Captures** turns passively as observations after each exchange
3. **Exposes** all 15 tools so you can query memory explicitly

Example agent prompts:

```
Search my memory for anything about the auth system
Remember that the database schema uses UUIDs
What did we work on in the last session?
```

## How it works

```
Hermes turn → EngramMemoryProvider → HTTP → engram serve → SQLite
```

- **Passive capture**: after each turn, user+assistant content is sent to `POST /observations/passive` (best-effort, non-blocking daemon thread)
- **Prefetch**: before each turn, `GET /context` is called in a background thread and cached for injection
- **Tools**: all 15 Engram tools are routed through `handle_tool_call()` to the HTTP API
- **Session**: each Hermes session registers as an Engram session with project name derived from `git remote origin`

## Session lifecycle

| Hook | What it does |
|------|-------------|
| `initialize()` | Detect project, start server if needed, register session |
| `prefetch()` | Return cached context for upcoming turn |
| `queue_prefetch()` | Background fetch of `/context` |
| `sync_turn()` | Passive capture of completed turns (non-blocking) |
| `on_session_end()` | Mark session as completed, flush pending syncs |
| `shutdown()` | Wait for pending threads |

## Tools reference

| Tool | Description | Endpoint |
|------|-------------|----------|
| `mem_search` | FTS5 full-text search across sessions | `GET /search` |
| `mem_save` | Save structured observation | `POST /observations` |
| `mem_update` | Update observation by ID | `PATCH /observations/{id}` |
| `mem_delete` | Delete observation by ID | `DELETE /observations/{id}` |
| `mem_context` | Recent session context for injection | `GET /context` |
| `mem_timeline` | Project activity timeline | `GET /timeline` |
| `mem_session_summary` | Save end-of-session summary | `POST /observations` |
| `mem_get_observation` | Get full observation by ID | `GET /observations/{id}` |
| `mem_save_prompt` | Capture user prompt | `POST /observations` |
| `mem_session_start` | Register session start | `POST /sessions` |
| `mem_session_end` | Mark session completed | `POST /sessions/{id}/end` |
| `mem_judge` | Record memory conflict verdict | `POST /judge` |
| `mem_doctor` | Operational diagnostics | `GET /doctor` |
| `mem_current_project` | Detect current project | local |
| `mem_capture_passive` | Passive content capture | `POST /observations/passive` |

## Contributing

Contributions for new plugins or improvements to existing ones are welcome. See [AGENTS.md](AGENTS.md) for plugin development guidelines.

## License

MIT — see [`LICENSE`](LICENSE).
