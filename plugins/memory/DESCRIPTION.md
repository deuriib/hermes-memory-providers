# Memory Providers

**Persistent memory backends for Hermes Agent — because great AI assistants never forget.**

## What Are Memory Providers?

Memory providers give Hermes Agent a persistent brain. Without one, every conversation starts from scratch. With one, Hermes remembers:

- **Bugs you've fixed** and their root causes
- **Architecture decisions** and why you made them  
- **Patterns and conventions** you've established
- **User preferences** and coding style
- **Project context** across weeks and months

## How They Work

Memory providers implement Hermes's `MemoryProvider` interface, connecting the agent to different storage backends:

```
Hermes Agent Event → Memory Provider → Storage Backend → Persistence
     ↓                    ↓                 ↓              ↓
  Tool execution      Plugin code       HTTP API        SQLite
  User message        Python client     Database        Vector DB
  Session end         Tool schemas      File system     Cloud storage
```

## Available Providers

### [Engram](engram/) — **Recommended**

**Backend:** Go HTTP server + SQLite  
**Status:** ✅ Stable  
**Best for:** Local development, fast queries, full-text search

- 15 memory tools exposed to the agent
- Passive session capture (non-blocking)
- Background context prefetch
- FTS5 search across all sessions
- Session lifecycle management

[→ Install Engram](engram/)

---

*Want to add a memory provider? Check the [development guide](../../README.md#for-plugin-developers) in the main README.*

## Choosing a Memory Provider

| If you need... | Choose... | Why... |
|---|---|---|
| **Local-first storage** | Engram | Self-hosted, no dependencies, fast |
| **Cloud persistence** | _(coming soon)_ | Sync across devices, team sharing |
| **Vector similarity** | _(coming soon)_ | Semantic search, embedding-based memory |
| **Custom backend** | _(build one)_ | Integrate with existing infrastructure |

## Memory Provider Interface

All memory providers must implement these core methods:

```python
class MemoryProvider(ABC):
    @abstractmethod
    async def save(self, observation: dict) -> str: ...
    
    @abstractmethod
    async def search(self, query: str, **filters) -> list[dict]: ...
    
    @abstractmethod
    async def get(self, id: str) -> dict: ...
    
    @abstractmethod
    async def delete(self, id: str) -> bool: ...
    
    @abstractmethod
    async def context(self, **filters) -> dict: ...
```

Plus lifecycle hooks for session start/end, tool execution, and system events.

## Why Memory Matters

**Without persistent memory:**
- "Remember that bug we fixed last week?" → Agent has no idea
- "Use the same pattern as before" → Which pattern?
- "Don't repeat that mistake" → What mistake?

**With persistent memory:**
- "Search for the auth bug from March" → Returns the session, root cause, and fix
- "What patterns have we established?" → Lists conventions with examples
- "Any similar issues before?" → Finds related problems and solutions

Memory transforms Hermes from a helpful assistant into a **learning partner** that grows with your project.