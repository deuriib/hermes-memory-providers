# Hermes Plugins

**Extend Hermes Agent with curated plugins — memory, tools, connectors, and workflows.**

## What this is

A monorepo of high-quality plugins for [Hermes Agent](https://github.com/NousResearch/hermes-agent). Instead of searching scattered repositories, find everything here:

- **🧠 Memory** — Persistent storage backends (SQLite, cloud, vector DBs)
- **🛠 Tools** — Custom functionality and integrations
- **🔗 Connectors** — APIs, databases, external services
- **⚡ Workflows** — Multi-step automations and patterns

## Plugin Categories

### Memory Providers

Persistent memory across sessions. [Browse memory plugins →](./plugins/memory/)

| Plugin | Backend | Status |
|--------|---------|--------|
| [**Engram**](./plugins/memory/engram/) | Go/SQLite HTTP API | ✅ Stable |

### Tools & Connectors

*Coming soon — submit yours!*

## Quick Start

### 1. Browse Plugins

Explore by category:
- `plugins/memory/` — Persistent storage backends
- `plugins/tools/` — Custom functionality (coming soon)
- `plugins/connectors/` — External integrations (coming soon)
- `plugins/workflows/` — Automation patterns (coming soon)

### 2. Install

```bash
# Install by category and name
./bin/hm-install memory/engram

# Or use mise tasks
mise run install memory/engram
```

### 3. Configure

Plugins auto-register with Hermes Agent on startup. See individual plugin READMEs for configuration.

## For Plugin Developers

### Plugin Types & APIs

**Memory Providers** implement `MemoryProvider` ABC:
```python
class MemoryProvider(ABC):
    @abstractmethod
    async def save(self, observation: dict) -> str: ...
    @abstractmethod
    async def search(self, query: str, **filters) -> list[dict]: ...
```

**Tool Plugins** register functions via schemas:
```python
def register(ctx):
    ctx.register_tools([search_tool, analyze_tool])
```

**Connector Plugins** integrate external APIs:
```python
class SlackConnector:
    async def send_message(self, channel: str, text: str): ...
```

### Plugin Structure

```
plugins/category/plugin-name/
├── __init__.py       # Main class + register() function
├── client.py         # Backend client (if needed)
├── schemas.py        # Tool/API definitions
├── plugin.yaml       # Metadata (name, version, type)
└── README.md         # Usage & setup docs
```

### Development Workflow

```bash
# Test locally
mise run install category/plugin-name

# Verify
mise run list

# Update after changes
mise run update category/plugin-name
```

## Management Scripts

| Command | Purpose |
|---------|---------|
| `bin/hm-install <provider>` | Install provider to Hermes |
| `bin/hm-uninstall <provider>` | Remove provider |
| `bin/hm-update [provider]` | Update one or all providers |
| `bin/hm-list` | Show installed providers |

## Requirements

- **Python 3.11+** — for type hints and modern async
- **Hermes Agent** — this is a plugin collection, not standalone
- **Provider-specific deps** — see individual plugin READMEs

## Contributing

We welcome all types of Hermes plugins! The best ones:

- ✅ **Solve real problems** — fill gaps in Hermes Agent's capabilities
- ✅ **Follow conventions** — use the established plugin structure
- ✅ **Include great docs** — clear setup, configuration, and troubleshooting
- ✅ **Handle errors gracefully** — network issues, timeouts, auth failures
- ✅ **Use typed interfaces** — full type hints on public methods
- ✅ **Pick the right category** — Memory, Tools, Connectors, or Workflows

---

**Made with ❤️ for the Hermes Agent community**

Need help? Check individual plugin READMEs or open an issue.