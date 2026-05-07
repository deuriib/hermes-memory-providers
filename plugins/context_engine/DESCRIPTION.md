# Context Engines

**Hermes Agent context management — never lose important conversations to lossy summarization.**

## What Are Context Engines?

Context engines solve the token limit problem by managing what context gets kept, compressed, or recalled. Hermes Agent processes long conversations that exceed context windows, and traditional approaches just _summarize and delete_ information forever.

Context engines take a smarter approach:

- **Protect** what matters most (system prompt, recent context)
- **Preserve** the rest as structured snapshots instead of destroying it
- **Recall** full context on demand when the agent needs it

## How They Work

Context engines intercept Hermes's context compression lifecycle:

```
Long Conversation → ContextEngine.compress() → Structured Snapshot
        ↓                    ↓                      ↓
  Token limit hit      Smart protection          Engram/KB
        ↓                    ↓                      ↓
  Agent needs context  engram_recall()       Full history restored
```

**Key insight:** Instead of summarizing away information, we _relocate_ it to persistent storage where it can be expanded later.

## Available Context Engines

### [Engram](engram/) — **Recommended**

**Backend:** Engram HTTP API + SQLite  
**Status:** ✅ Stable  
**Best for:** Projects with long-running conversations, multi-session workflows

- Preserves all context as `context_snapshot` observations in Engram
- Protects head (system prompt) and tail (recent messages) automatically
- Agent can recall full compressed snapshots via `engram_recall()`
- Search across all snapshots with `engram_search_context()`
- Context survives context window resets entirely

[→ Install Engram](engram/)

---

_Want to add a context engine? Check the [development guide](../../README.md#for-plugin-developers) in the main README._

## Context Engine Interface

All context engines must implement these core methods:

```python
class ContextEngine(ABC):
    @abstractmethod
    async def compress(self, context: list[dict]) -> CompressedContext:
        """Compress context, protecting important parts and preserving the rest."""

    @abstractmethod
    async def recall(self, snapshot_id: str) -> list[dict]:
        """Expand a compressed snapshot back to full context."""

    @abstractmethod
    async def search(self, query: str, **filters) -> list[dict]:
        """Search across all compressed snapshots."""
```

Plus lifecycle hooks for:
- `on_context_start()` — Initialize context for a session
- `on_compress()` — Trigger compression when approaching limits
- `on_recall()` — Restore expanded context when needed

## Why Context Engines Matter

**Without context engines:**
- Long conversations get summarized → details lost forever
- Agent can't reference decisions from 500 messages ago
- Every session starts cold, losing valuable project history

**With context engines:**
- All conversations preserved as recallable snapshots
- Agent can pull in relevant context from any past session
- Project knowledge compounds over time

Context engines transform Hermes from a session-limited assistant into a **project memory system** that grows with your work.

## Context Engine vs Memory Provider

Both connect Hermes to Engram, but serve different purposes:

| Aspect | Context Engine | Memory Provider |
|--------|---------------|-----------------|
| **Purpose** | Manage context compression/recall | Store agent learnings and observations |
| **Trigger** | Token limits, session continuity | Agent tool calls, proactive saves |
| **Storage** | Compressed conversation snapshots | Structured observations (bugs, decisions, patterns) |
| **Access** | Via `engram_recall()` tool | Via `mem_save()`, `mem_search()` tools |

_These are complementary — you can use both together._
