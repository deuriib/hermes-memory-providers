# Engram Memory Provider for Hermes Agent

Persistent cross-session memory via the [Engram](https://github.com/Gentleman-Programming/engram) HTTP API.

## What it does

- **15 memory tools** exposed to the model: `mem_search`, `mem_save`, `mem_update`, `mem_delete`, `mem_context`, `mem_timeline`, `mem_session_summary`, `mem_get_observation`, `mem_save_prompt`, `mem_session_start`, `mem_session_end`, `mem_judge`, `mem_doctor`, `mem_current_project`, `mem_capture_passive`
- **Passive capture**: conversation turns are automatically synced as observations after each turn (non-blocking, daemon thread)
- **Prefetch**: background recall of relevant context before each turn
- **Memory instructions** injected into the system prompt so the agent always knows the Engram protocol
- **Project detection**: auto-detects project name from git remote origin URL
- **Cron guard**: skips all writes for cron/flush contexts to avoid corrupting user representations
- **Session switch support**: handles `/resume`, `/branch`, `/reset`, `/new` mid-process session rotation

## Requirements

- [Engram](https://github.com/Gentleman-Programming/engram) installed (`go install` or release binary)
- `engram serve` running at `http://127.0.0.1:7437` (auto-started if `ENGRAM_BIN` is set)

## Setup

### 1. Install Engram

```bash
go install github.com/Gentleman-Programming/engram@latest
# or download from https://github.com/Gentleman-Programming/engram/releases
```

### 2. Activate the provider

```bash
hermes memory set engram
```

Or add to your `~/.hermes/config.yaml`:

```yaml
memory:
  provider: engram
```

### 3. Configure (optional)

Create `~/.hermes/engram.json` to override defaults:

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
export ENGRAM_PORT=7437        # default
export ENGRAM_BIN=engram       # path to binary, default: "engram"
export ENGRAM_DISABLED=false   # set to "true" to disable
```

## How it works

```
Hermes turn → EngramMemoryProvider → HTTP → engram serve → SQLite
```

- **Passive capture**: after each turn, user+assistant content is sent to `POST /observations/passive` (best-effort, non-blocking)
- **Prefetch**: before each turn, `GET /context` is called in a background thread and cached for injection
- **Tools**: all 15 Engram tools are routed through `handle_tool_call()` to the HTTP API
- **Session**: each Hermes session registers as an Engram session with project name derived from git remote

## Session lifecycle

1. `initialize()`: detect project, start server if needed, register session
2. `prefetch()`: return cached context for upcoming turn
3. `queue_prefetch()`: background fetch of `/context`
4. `sync_turn()`: passive capture of completed turns (non-blocking)
5. `on_session_end()`: mark session as completed, flush pending syncs
6. `shutdown()`: wait for pending threads

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

## Development

The source is in `~/Work/engram-memory/`. To deploy:

```bash
cp -r ~/Work/engram-memory/engram ~/.hermes/hermes-agent/plugins/memory/engram
```

Or symlink for live development:

```bash
ln -s ~/Work/engram-memory/engram ~/.hermes/hermes-agent/plugins/memory/engram
```
