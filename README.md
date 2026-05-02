# Hermes Memory Providers

> Persistent memory backends for [Hermes Agent](https://github.com/NousResearch/hermes-agent) — because great AI assistants remember everything.

## Why Memory Providers?

Hermes Agent is designed to learn and grow with you across sessions. But where should it store what it learns? This monorepo gives you options:

- **Local-first** with SQLite and file-based storage
- **Cloud-native** with database integrations  
- **Specialized** with vector databases and embedding stores
- **Custom** — build your own following our plugin architecture

## Available Providers

| Provider | Backend | Status | Best For |
|----------|---------|--------|----------|
| [**Engram**](./plugins/engram/) | Go/SQLite HTTP API | ✅ Stable | Local development, fast queries |

## Quick Start

### 1. Choose Your Provider

Browse the `plugins/` directory and pick the memory backend that fits your workflow.

### 2. Install

```bash
# Install a specific provider
./bin/hm-install engram

# Or use mise tasks
mise run install engram
```

### 3. Configure Hermes

Your chosen provider will be automatically registered with Hermes Agent on next startup.

## For Plugin Developers

### Architecture Requirements

Every memory provider must implement the `MemoryProvider` ABC with these methods:

```python
class MemoryProvider(ABC):
    @abstractmethod
    async def save(self, observation: dict) -> str: ...
    
    @abstractmethod
    async def search(self, query: str, **filters) -> list[dict]: ...
    
    @abstractmethod
    async def get(self, id: str) -> dict: ...
```

### Plugin Structure

```
plugins/your-provider/
├── __init__.py       # Provider class + register() function
├── client.py         # Backend client implementation  
├── schemas.py        # Tool definitions for Hermes
├── plugin.yaml       # Metadata (name, version, type)
└── README.md         # Usage docs
```

### Development Workflow

```bash
# Local testing
mise run install your-provider

# Verify installation
mise run list

# Update after changes
mise run update your-provider
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

We welcome new memory providers! The best plugins:

- ✅ **Solve real problems** — address actual memory/storage needs
- ✅ **Follow conventions** — use the established plugin structure
- ✅ **Include great docs** — clear setup, configuration, and troubleshooting
- ✅ **Handle errors gracefully** — network issues, timeouts, auth failures
- ✅ **Use typed interfaces** — full type hints on public methods

---

**Made with ❤️ for the Hermes Agent community**

Need help? Check individual plugin READMEs or open an issue.