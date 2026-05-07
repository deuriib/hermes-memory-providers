# Engram Context Engine Plugin

Uses **Engram** as a persistent knowledge graph store instead of lossy summarization.

## How It Works

```
Hermes ContextEngine → compress() → saves to Engram → returns compact summary
Agent calls engram_recall() → Engram returns full historical context
```

**Key difference from ContextCompressor:** Instead of destroying information through summarization, this engine preserves everything in Engram and lets you expand context on demand.

## Activation

```yaml
# ~/.hermes/config.yaml
context:
  engine: engram
```

## Requirements

- `engram` binary in PATH (or set `ENGRAM_BIN`)
- `engram serve` running on `http://127.0.0.1:7437` (or set `ENGRAM_PORT`)

## Tools Provided

| Tool | Description |
|------|-------------|
| `engram_recall` | Expand a compressed snapshot back to full context |
| `engram_search_context` | Search Engram across all snapshots for relevant context |

## How Compression Works

1. **Protects head:** First 2 messages (system prompt, initial context)
2. **Protects tail:** Last 8 messages (recent conversation)
3. **Middle messages:** Saved as a `context_snapshot` observation in Engram
4. **Summary inserted:** A system message explains what's compressed and how to recall it

Example summary message inserted after compression:

```json
{
  "role": "system",
  "content": "[Context compressed: 15 messages summarized into snapshot #1]\n\nTopics covered: code, files, testing\n\nFull context available via engram_recall(snapshot_id=42)"
}
```

## Context Snapshot Structure

Snapshots are stored as Engram observations with:

```json
{
  "title": "Context Snapshot #1",
  "type": "context_snapshot",
  "scope": "project",
  "content": {
    "compression_number": 1,
    "turn_count": 15,
    "total_tokens": 45000,
    "focus_topic": "user auth",
    "message_count": 15,
    "turns": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "type": "tool_call", "name": "mem_save", "args": "..."}
    ]
  }
}
```

## Installation

```bash
# Copy to Hermes plugins directory
cp -r plugins/context_engine/engram ~/.hermes/hermes-agent/plugins/context_engine/engram/
```

Or use the install script from the monorepo:

```bash
./bin/hm-install context_engine/engram
```

## Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `ENGRAM_PORT` | `7437` | Engram server port |
| `ENGRAM_BIN` | `engram` | Path to engram binary |

## Architecture

```
plugins/context_engine/engram/
├── __init__.py      # EngramContextEngine implementation
└── plugin.yaml       # Plugin metadata
```

The engine implements:
- `ContextEngine` ABC (required methods)
- Token tracking and threshold management
- Snapshot persistence to Engram
- `engram_recall` and `engram_search_context` tools for the agent