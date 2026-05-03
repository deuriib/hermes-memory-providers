# Engram Memory Provider

**Persistent cross-session memory for Hermes Agent — remember everything, forget nothing.**

Engram gives your Hermes Agent a long-term memory that survives sessions, restarts, and even complete reinstalls. Every conversation, decision, and discovery gets stored and becomes searchable.

> **Note**: This plugin has been updated to use Hermes Agent's new **MemoryProvider** architecture. If you're upgrading from v1.x, run `hermes memory setup` to configure the provider.

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

### 3. Install and Configure Plugin

```bash
# Install plugin
cd hermes-memory-providers
./bin/hm-install memory/engram

# Configure as active memory provider
hermes memory setup
# → Select "engram" from the list
# → Enter port (default: 7437) 
# → Enter binary path (default: engram)
```

### 4. Verify Setup

```bash
# Check provider status
hermes engram status

# Test connection  
hermes engram test

# Start using Hermes with persistent memory
hermes chat
```

## Memory Tools Available

Once configured, your agent gets these memory capabilities:

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
Hermes MemoryProvider ──→ Engram Plugin ──→ HTTP API ──→ engram serve ──→ SQLite
                       ↑                               ↓
            Tools & lifecycle hooks          Persistent storage
```

**Automatic capture:**
- Memory protocol injected into system prompt
- Context prefetched before each API call
- Conversations synced after each turn
- Session summaries created on conversation end

**Smart retrieval:**
- FTS5 full-text search across all memories
- Project-scoped queries (auto-detected from git remote)
- Timeline browsing by date ranges
- Cross-session context recovery

## CLI Commands

The plugin provides CLI commands when active:

```bash
# Check server status and current project
hermes engram status

# Show configuration
hermes engram config

# Start engram server  
hermes engram server

# Test connection and functionality
hermes engram test
```

## Configuration

### Memory Provider Setup

```bash
# Configure Engram as your memory provider
hermes memory setup

# View current memory provider
hermes memory status

# Switch to a different provider
hermes memory switch <provider-name>
```

### Environment Variables

```bash
# Engram server port (default: 7437)
export ENGRAM_PORT=7437

# Path to engram binary (default: engram)  
export ENGRAM_BIN=/usr/local/bin/engram
```

### Config File

After setup, configuration is stored in `~/.hermes/engram.json`:

```json
{
  "port": "7437",
  "binary_path": "engram"
}
```

## Usage Examples

### Automatic Memory Saving

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

### Session Summaries

At the end of each session, the agent automatically saves:

```
## Goal
Built user authentication with JWT tokens

## Discoveries
- JWT tokens must have httpOnly and secure flags
- Refresh token rotation needed for security

## Accomplished
- Implemented login/logout endpoints
- Added JWT middleware for protected routes

## Relevant Files
- src/auth/middleware.ts — JWT verification logic
- src/routes/auth.ts — Login/logout handlers
```

## Troubleshooting

### Provider Not Available

```bash
# Check if engram binary is in PATH
which engram

# Check if server is running
hermes engram status

# Start server if needed
hermes engram server
```

### Memory Tools Not Working

```bash
# Verify provider is active
hermes memory status

# Test connectivity
hermes engram test

# Check server logs
engram serve --debug
```

### Performance Issues

```bash
# Check database size
du -sh ~/.engram/

# Monitor server performance
top -p $(pgrep engram)

# Optimize if needed
engram doctor --optimize
```

## Upgrading from v1.x

If you were using the old hook-based plugin:

1. **Remove old plugin**:
   ```bash
   rm -rf ~/.hermes/hermes-agent/plugins/memory/engram
   ```

2. **Install new plugin**:
   ```bash
   ./bin/hm-install memory/engram
   ```

3. **Configure as memory provider**:
   ```bash
   hermes memory setup
   # → Select "engram"
   ```

4. **Verify everything works**:
   ```bash
   hermes engram test
   ```

Your existing memories in `~/.engram` will be preserved.

## Architecture Notes

**MemoryProvider Implementation:**
- `__init__.py` — MemoryProvider class with lifecycle methods
- `tools.py` — Memory tool handlers  
- `schemas.py` — Tool definitions
- `cli.py` — CLI command handlers
- `plugin.yaml` — Provider metadata

**Lifecycle Hooks:**
- `system_prompt_block()` — Injects memory protocol
- `prefetch()` — Loads context before API calls
- `sync_turn()` — Saves conversations (non-blocking)
- `on_session_end()` — Creates session summaries

**HTTP API:**
- All memory operations go through engram serve
- SQLite backend with FTS5 full-text search
- Non-blocking async calls from provider
- Auto-retry with exponential backoff

## Contributing

Found a bug? Want a feature?

1. **Plugin issues** → [hermes-memory-providers](https://github.com/deuriib/hermes-memory-providers/issues)
2. **Server issues** → [engram](https://github.com/deuriib/engram/issues)

## License

MIT — see [LICENSE](../../../LICENSE) in the repo root.
