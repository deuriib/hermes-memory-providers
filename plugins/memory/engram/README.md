# Engram Memory Provider

**Persistent cross-session memory for Hermes Agent — remember everything, forget nothing.**

Engram gives your Hermes Agent a long-term memory that survives sessions, restarts, and even complete reinstalls. Every conversation, decision, and discovery gets stored and becomes searchable.

## What You Get

- 🧠 **Cross-session memory** — Agent remembers past conversations and decisions
- 🔍 **Full-text search** — Find any memory with FTS5-powered queries
- 📊 **Session tracking** — Complete conversation history with context
- ⚡ **Fast queries** — SQLite backend with optimized indexes
- 🔄 **Background sync** — Non-blocking memory capture during conversations
- 🎯 **Smart context** — Agent automatically loads relevant memories

## Quick Setup

### 1. Install Engram Server

```bash
# Install from GitHub releases
curl -fsSL https://github.com/deuriib/engram/releases/latest/download/engram-linux-amd64 -o ~/bin/engram
chmod +x ~/bin/engram

# Or build from source
git clone https://github.com/deuriib/engram.git
cd engram && go build -o ~/bin/engram ./cmd/engram
```

### 2. Start Engram Server

```bash
# Start in background (recommended)
engram serve --port 7437 --data ~/.engram &

# Or run in foreground for debugging
engram serve --port 7437 --data ~/.engram
```

### 3. Install Plugin

```bash
# From hermes-memory-providers repo
cd hermes-memory-providers
./bin/hm-install memory/engram

# Or directly copy
cp -r plugins/memory/engram ~/.hermes/hermes-agent/plugins/memory/engram
```

### 4. Verify Setup

```bash
# Check Engram server health
curl http://127.0.0.1:7437/health

# Start Hermes Agent (plugin auto-loads)
hermes chat
```

## Memory Tools Available

Once installed, your agent gets these memory capabilities:

| Tool | Purpose |
|------|---------|
| `mem_save` | Save important observations, decisions, bug fixes |
| `mem_search` | Find memories with keywords or phrases |
| `mem_context` | Get recent session context |
| `mem_session_summary` | End-of-session summaries |
| `mem_timeline` | Chronological view of project memories |
| `mem_get_observation` | Retrieve full memory by ID |

## How It Works

```
Hermes conversation ──→ Engram Plugin ──→ HTTP API ──→ engram serve ──→ SQLite
                                     ↑                              ↓
                          Memory tools & hooks            Persistent storage
```

**Automatic capture:**
- Every tool execution gets passively saved
- Session summaries created on conversation end
- Context automatically injected into new sessions

**Smart retrieval:**
- FTS5 full-text search across all memories
- Project-scoped queries (auto-detected from git remote)
- Timeline browsing by date ranges

## Configuration

### Environment Variables

```bash
# Engram server URL (default: http://127.0.0.1:7437)
export ENGRAM_URL=http://127.0.0.1:7437

# Custom port
export ENGRAM_PORT=8888

# Data directory for engram serve
export ENGRAM_DATA_DIR=~/.engram
```

### Plugin Settings

Edit `~/.hermes/hermes-agent/plugins/memory/engram/plugin.yaml`:

```yaml
name: engram
version: 1.0.0
requires_env:
  - name: ENGRAM_PORT
    description: "Port where engram serve runs (default: 7437)"
    secret: false
```

## Usage Examples

### Save Important Discoveries

```
You: "We decided to use Zustand instead of Redux because our state is simple"
Agent: *automatically calls mem_save with the decision*
```

### Search Past Work

```
You: "How did we handle authentication before?"
Agent: *calls mem_search("authentication auth")*
       *finds previous auth implementation from 2 months ago*
```

### Get Project Context

```
You: "What's the current status?"
Agent: *calls mem_context()*
       *loads recent session summaries and key decisions*
```

## Troubleshooting

### Plugin Not Loading

```bash
# Check plugin installation
ls ~/.hermes/hermes-agent/plugins/memory/engram/

# Should show: __init__.py, plugin.yaml, schemas.py, tools.py

# Check Hermes logs
hermes --debug chat
```

### Engram Server Issues

```bash
# Check if server is running
ps aux | grep engram
curl -v http://127.0.0.1:7437/health

# Check server logs
engram serve --debug

# Reset database (nuclear option)
rm -rf ~/.engram && engram serve
```

### Memory Tools Not Working

```bash
# Test direct API call
curl -X POST http://127.0.0.1:7437/save \
  -H "Content-Type: application/json" \
  -d '{"observation": {"title": "test", "content": "test"}}'

# Check Hermes can reach Engram
hermes tools list | grep mem_
```

### Performance Issues

```bash
# Check database size
du -sh ~/.engram/

# Optimize SQLite (if needed)
engram serve --optimize

# Monitor memory usage
top -p $(pgrep engram)
```

## Advanced Usage

### Custom Project Names

```bash
# Override auto-detected project name
export ENGRAM_PROJECT_NAME="my-special-project"
```

### Multiple Projects

```bash
# Use different data directories per project
cd ~/project-a && engram serve --data ./.engram-a --port 7437 &
cd ~/project-b && engram serve --data ./.engram-b --port 7438 &

# Update plugin config for project B
echo "ENGRAM_PORT=7438" > ~/project-b/.env
```

### Backup and Restore

```bash
# Backup all memories
cp -r ~/.engram ~/backups/engram-$(date +%Y%m%d)

# Or export to JSON
engram export --format json --output memories.json

# Restore from backup
cp -r ~/backups/engram-20240502 ~/.engram
```

## Architecture Notes

**Plugin Structure:**
- `__init__.py` — Main plugin class with event hooks
- `tools.py` — Memory tool implementations
- `schemas.py` — Tool definitions for Hermes
- `plugin.yaml` — Plugin metadata

**Event Hooks:**
- `pre_llm_call` — Injects memory protocol into system prompt
- `post_tool_call` — Captures tool results passively
- `on_session_start` — Registers new sessions
- `on_session_end` — Creates session summaries

**HTTP API:**
- All memory operations go through engram serve
- SQLite backend with FTS5 full-text search
- Non-blocking async calls from plugin
- Auto-retry with exponential backoff

## Contributing

Found a bug? Want a feature? 

1. **Plugin issues** → [hermes-memory-providers](https://github.com/deuriib/hermes-memory-providers/issues)
2. **Server issues** → [engram](https://github.com/deuriib/engram/issues)

## License

MIT — see [LICENSE](../../../LICENSE) in the repo root.
