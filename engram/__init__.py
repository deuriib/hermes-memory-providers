"""Engram Memory Provider — Hermes Agent plugin.

Provides persistent cross-session memory via the Engram HTTP API (engram serve).
Engram stores structured observations (decisions, bugs, discoveries, patterns)
with FTS5 search and project/scope filtering.

Plugin structure:
  plugins/memory/engram/
  ├── __init__.py      — MemoryProvider + tool handlers + register()
  ├── client.py        — EngramHTTPClient (REST API wrapper)
  ├── schemas.py       — OpenAI tool schemas
  ├── plugin.yaml      — Plugin metadata
  └── README.md        — Setup instructions

Flow:
    Hermes events → this provider → HTTP → engram serve → SQLite

Lifecycle:
    is_available()     — check engram serve is reachable (no network calls)
    initialize()       — start server, detect project, register session
    prefetch()         — background recall before each turn
    sync_turn()        — passive capture after each turn (non-blocking)
    get_tool_schemas() — expose memory tools to the model
    handle_tool_call() — dispatch tool calls
    on_session_end()   — flush passive captures
    shutdown()         — clean exit
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

from . import schemas

logger = logging.getLogger(__name__)


# ─── Memory instructions (injected into system prompt) ────────────────────────

MEMORY_INSTRUCTIONS = """

## Engram Persistent Memory — Protocol

You have access to Engram, a persistent memory system that survives across sessions and compactions.
This is NOT optional — use it proactively.

### WHEN TO SAVE (mandatory — call IMMEDIATELY after these events)

Call `mem_save` after:
- Bug fix completed
- Architecture or design decision made
- Non-obvious discovery about the codebase
- Configuration change or environment setup
- Pattern established (naming, structure, convention)
- User preference or constraint learned

Format for `mem_save`:
- **title**: Verb + what — short, searchable (e.g. "Fixed N+1 query", "Chose Zustand over Redux")
- **type**: bugfix | decision | architecture | discovery | pattern | config | learning
- **scope**: `project` (default) | `personal`
- **topic_key**: stable key like `architecture/auth-model` for evolving decisions
- **content**:
  **What**: One sentence — what was done
  **Why**: What motivated it
  **Where**: Files or paths affected
  **Learned**: Gotchas, edge cases (omit if none)

Topic rules:
- Different topics must not overwrite each other
- Reuse same `topic_key` to update an evolving topic
- If unsure about the key, pick a descriptive kebab-case name (e.g. `arch-auth-model`)

### WHEN TO SEARCH MEMORY

When user asks to recall something — any variation of "remember", "recall",
"what did we do", "how did we solve", "recordar", "qué hicimos":
1. Call `mem_context` — recent session history (fast, cheap)
2. If not found, call `mem_search` with keywords
3. If found, call `mem_get_observation` for full content

Also search PROACTIVELY when:
- Starting work that might have been done before
- User mentions a topic you have no context on
- User's first message references a project, feature, or problem

### SESSION CLOSE PROTOCOL (mandatory)

Before ending a session or saying "done" / "listo" / "that's it":
Call `mem_session_summary` with this structure:

## Goal
[What we were working on]

## Instructions
[User preferences or constraints — skip if none]

## Discoveries
- [Technical findings, gotchas]

## Accomplished
- [Completed items with key details]

## Next Steps
- [What remains — for the next session]

## Relevant Files
- path/to/file — [what it does]

### AFTER COMPACTION

If you see "FIRST ACTION REQUIRED" or context reset message:
1. Call `mem_session_summary` with the compacted content FIRST
2. Then call `mem_context` to recover context
3. Only THEN continue working

Do not skip step 1 — without it, everything before compaction is lost.
"""


# ─── Trivial-prompt filter ────────────────────────────────────────────────────

# Prompts that carry no semantic signal — skip passive capture for these.
_TRIVIAL_PROMPT_RE = re.compile(
    r"^(yes|no|ok|okay|sure|thanks|thank you|y|n|yep|nope|yeah|nah|"
    r"continue|go ahead|do it|proceed|got it|cool|nice|great|done|next|lgtm|k)$",
    re.IGNORECASE,
)


def _is_trivial(text: str) -> bool:
    if not text:
        return True
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.startswith("/"):
        return True
    return bool(_TRIVIAL_PROMPT_RE.match(stripped))


# ─── Project detection ────────────────────────────────────────────────────────


def _extract_project(directory: str) -> str:
    """Extract project name from git remote origin URL."""
    try:
        result = subprocess.run(
            ["git", "-C", directory, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            if url:
                name = os.path.basename(url).replace(".git", "")
                if name:
                    return name
    except Exception:
        pass

    # Fallback: git root directory name
    try:
        result = subprocess.run(
            ["git", "-C", directory, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            root = result.stdout.strip()
            if root:
                return root.split("/")[-1]
    except Exception:
        pass

    return directory.split("/")[-1] or "unknown"


def _default_session_id(project: str) -> str:
    """Generate default session ID from project name."""
    safe = "".join(c if c.isalnum() else "_" for c in project)
    return f"hermes-{safe}" if safe else "hermes-default"


def _strip_private(s: str) -> str:
    """Strip <private>...</private> tags before sending to engram."""
    return re.sub(r"<private>[\s\S]*?</private>", "[REDACTED]", s).strip()


def _truncate(s: str, max_chars: int) -> str:
    return s[:max_chars] + "..." if len(s) > max_chars else s


# ─── MemoryProvider ───────────────────────────────────────────────────────────


class EngramMemoryProvider(MemoryProvider):
    """Engram persistent memory for Hermes Agent.

    Uses the Engram HTTP API (engram serve) for all operations.
    Passive capture syncs conversation turns as observations.
    FTS5 search provides cross-session recall.
    """

    def __init__(self):
        # HTTP client — initialized lazily in initialize()
        self._client: Optional["EngramHTTPClient"] = None

        # Session state
        self._session_id: str = ""
        self._project: str = "unknown"
        self._directory: str = ""
        self._initialized: bool = False

        # Threading
        self._sync_thread: Optional[threading.Thread] = None
        self._prefetch_thread: Optional[threading.Thread] = None
        self._prefetch_result: str = ""
        self._prefetch_lock = threading.Lock()

        # Config
        self._port: int = 7437
        self._bin_path: str = "engram"
        self._passive_capture_enabled: bool = True
        self._prefetch_enabled: bool = True

    @property
    def name(self) -> str:
        return "engram"

    # ─── Availability ───────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if engram serve is reachable.

        No network calls — only checks if the port/binary config exists.
        Actual connectivity is verified in initialize().
        """
        # Check for explicit disable
        if os.environ.get("ENGRAM_DISABLED", "").lower() in ("1", "true", "yes"):
            return False

        # Read config from hermes_home/engram.json if it exists
        try:
            from hermes_constants import get_hermes_home
            config_path = Path(str(get_hermes_home())) / "engram.json"
            if config_path.exists():
                data = json.loads(config_path.read_text())
                if data.get("enabled") is False:
                    return False
        except Exception:
            pass

        # Available if we can reach the port or have a binary to start it
        port = int(os.environ.get("ENGRAM_PORT", "7437"))
        import socket
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            pass

        # Can we start it?
        return bool(os.environ.get("ENGRAM_BIN", "engram"))
        # Actually, we should just check if engram binary is available
        # If port is not open, we can try to start it in initialize()
        # So return True if there's any chance it can work
        return True

    # ─── Config ─────────────────────────────────────────────────────────────

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "port",
                "description": "Port where engram serve runs",
                "default": "7437",
            },
            {
                "key": "passive_capture",
                "description": "Automatically capture turns as observations (default: true)",
                "default": "true",
            },
            {
                "key": "prefetch",
                "description": "Pre-fetch context before each turn (default: true)",
                "default": "true",
            },
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        """Write non-secret config to $HERMES_HOME/engram.json."""
        config_path = Path(hermes_home) / "engram.json"
        existing = {}
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text())
            except Exception:
                pass
        existing.update(values)
        config_path.write_text(json.dumps(existing, indent=2))

    # ─── Lifecycle ─────────────────────────────────────────────────────────

    def initialize(self, session_id: str, **kwargs) -> None:
        """Initialize Engram connection and register session.

        Handles:
          - cron guard (skip writes for cron/flush contexts)
          - project detection from git remote
          - server startup if not running
          - session registration in engram
          - pre-fetch of recent context
        """
        from .client import EngramHTTPClient

        # Cron guard — skip all writes for cron/flush contexts
        agent_context = kwargs.get("agent_context", "")
        platform = kwargs.get("platform", "cli")
        if agent_context in ("cron", "flush") or platform == "cron":
            logger.debug("Engram skipped: cron/flush context")
            self._initialized = False
            return

        # Load config from environment and config file
        self._port = int(os.environ.get("ENGRAM_PORT", "7437"))
        self._bin_path = os.environ.get("ENGRAM_BIN", "engram")

        hermes_home = kwargs.get("hermes_home", "")
        if hermes_home and not os.environ.get("ENGRAM_PORT"):
            try:
                config_path = Path(hermes_home) / "engram.json"
                if config_path.exists():
                    cfg = json.loads(config_path.read_text())
                    if "port" in cfg:
                        self._port = int(cfg["port"])
                    self._passive_capture_enabled = cfg.get("passive_capture", True)
                    self._prefetch_enabled = cfg.get("prefetch", True)
            except Exception as e:
                logger.debug("Could not load engram config: %s", e)

        # Detect project from working directory
        cwd = kwargs.get("agent_workspace", os.getcwd())
        self._directory = cwd
        self._project = _extract_project(cwd)

        # Resolve session ID
        self._session_id = session_id or _default_session_id(self._project)

        # Create HTTP client
        self._client = EngramHTTPClient(
            port=self._port,
            bin_path=self._bin_path,
        )

        # Try to start server if not running
        if not self._client.ensure_running():
            logger.warning(
                "Engram server not reachable and could not be started. "
                "Run 'engram serve' or set ENGRAM_BIN to enable memory."
            )
            self._initialized = False
            return

        # Register session in engram (idempotent)
        # Check for subagent — don't register subagent sessions
        parent_id = kwargs.get("parent_session_id") or kwargs.get("parent_id")
        if not parent_id:
            self._client.ensure_session(self._session_id, self._project, self._directory)

        self._initialized = True
        logger.debug(
            "Engram initialized: session=%s project=%s directory=%s",
            self._session_id, self._project, self._directory,
        )

    # ─── Session switch ────────────────────────────────────────────────────

    def on_session_switch(
        self,
        new_session_id: str,
        *,
        parent_session_id: str = "",
        reset: bool = False,
        **kwargs,
    ) -> None:
        """Handle session_id rotation mid-process (/resume, /branch, /reset, /new)."""
        if reset:
            # New conversation — flush and start fresh
            if self._sync_thread and self._sync_thread.is_alive():
                self._sync_thread.join(timeout=5.0)
            self._session_id = new_session_id or _default_session_id(self._project)
            if self._client and self._initialized:
                self._client.clear_session_cache(self._session_id)
                self._client.ensure_session(self._session_id, self._project, self._directory)
        else:
            # /resume or /branch — continue tracking under new ID
            self._session_id = new_session_id or self._session_id

    # ─── System prompt ─────────────────────────────────────────────────────

    def system_prompt_block(self) -> str:
        """Return memory instructions for the system prompt."""
        return MEMORY_INSTRUCTIONS

    # ─── Prefetch ──────────────────────────────────────────────────────────

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Pre-fetch relevant context for the upcoming turn.

        Called before each API call. Uses cached result from queue_prefetch()
        when available. Fast — returns immediately if result is cached.
        """
        with self._prefetch_lock:
            if self._prefetch_result:
                result = self._prefetch_result
                self._prefetch_result = ""
                return result
        return ""

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        """Queue background recall for the next turn.

        Fetches /context from engram asynchronously.
        Trivial prompts (single-word acknowledgements) are skipped.
        """
        if not self._initialized or not self._client:
            return
        if not self._prefetch_enabled:
            return
        if _is_trivial(query):
            return

        # Don't fire if a prefetch thread is already running
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            return

        def _fetch():
            try:
                result = self._client.get_context(project=self._project)
                if result and result.get("context"):
                    context = result["context"]
                    if context.strip():
                        with self._prefetch_lock:
                            self._prefetch_result = context
            except Exception as e:
                logger.debug("Engram prefetch failed: %s", e)

        self._prefetch_thread = threading.Thread(
            target=_fetch, daemon=True, name="engram-prefetch"
        )
        self._prefetch_thread.start()

    # ─── Turn sync ─────────────────────────────────────────────────────────

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """Persist a completed turn via passive capture (non-blocking).

        Trivial prompts are skipped. Uses a daemon thread to avoid blocking
        the main conversation loop.
        """
        if not self._initialized or not self._client:
            return
        if not self._passive_capture_enabled:
            return
        if _is_trivial(user_content):
            return

        # Don't fire if a sync thread is already running
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=5.0)

        # Strip private tags and truncate
        clean_user = _strip_private(_truncate(user_content, 2000))
        clean_assistant = _strip_private(_truncate(assistant_content, 2000))

        if len(clean_user) <= 10:
            return

        def _sync():
            try:
                # Capture user message
                self._client.passive_capture(
                    session_id=self._session_id,
                    content=clean_user,
                    project=self._project,
                    source="turn_user",
                )
                # Capture assistant response (abbreviated)
                if clean_assistant and len(clean_assistant) > 10:
                    summary = clean_assistant[:500] + ("..." if len(clean_assistant) > 500 else "")
                    self._client.passive_capture(
                        session_id=self._session_id,
                        content=f"[assistant] {summary}",
                        project=self._project,
                        source="turn_assistant",
                    )
            except Exception as e:
                logger.debug("Engram sync_turn failed: %s", e)

        self._sync_thread = threading.Thread(
            target=_sync, daemon=True, name="engram-sync"
        )
        self._sync_thread.start()

    # ─── Memory write mirror ───────────────────────────────────────────────

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mirror built-in memory writes to Engram.

        When the agent saves a memory entry via the built-in tool,
        also persist it to Engram for cross-session recall.
        """
        if action != "add":
            return
        if not self._initialized or not self._client:
            return

        # Determine type from metadata
        obs_type = "learning"
        if metadata:
            tool_name = metadata.get("tool_name", "")
            if "preference" in tool_name.lower():
                obs_type = "preference"
            elif "decision" in tool_name.lower():
                obs_type = "decision"

        def _mirror():
            try:
                self._client.add_observation(
                    session_id=self._session_id,
                    title=f"Memory write: {target}",
                    content=content[:4000],
                    project=self._project,
                    obs_type=obs_type,
                    scope="project",
                )
            except Exception as e:
                logger.debug("Engram memory mirror failed: %s", e)

        t = threading.Thread(target=_mirror, daemon=True, name="engram-memwrite")
        t.start()

    # ─── Session end ────────────────────────────────────────────────────────

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """Flush pending sync on session end."""
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=10.0)
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=5.0)

        # Mark session as completed in engram
        if self._initialized and self._client:
            self._client.end_session(self._session_id)

    # ─── Tools ─────────────────────────────────────────────────────────────

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return all Engram tool schemas."""
        return [
            schemas.MEM_SEARCH,
            schemas.MEM_SAVE,
            schemas.MEM_UPDATE,
            schemas.MEM_DELETE,
            schemas.MEM_CONTEXT,
            schemas.MEM_SESSION_SUMMARY,
            schemas.MEM_GET_OBSERVATION,
            schemas.MEM_SAVE_PROMPT,
            schemas.MEM_SESSION_START,
            schemas.MEM_SESSION_END,
            schemas.MEM_TIMELINE,
            schemas.MEM_CURRENT_PROJECT,
            schemas.MEM_CAPTURE_PASSIVE,
        ]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        """Dispatch a tool call to the appropriate handler."""
        if not self._initialized or not self._client:
            # Try to re-initialize
            session_id = kwargs.get("session_id", "")
            self.initialize(session_id, **kwargs)
            if not self._initialized:
                return tool_error("Engram is not active. Run 'engram serve' first.")

        handler = _TOOL_HANDLERS.get(tool_name)
        if not handler:
            return tool_error(f"Unknown Engram tool: {tool_name}")

        try:
            return handler(self, args, **kwargs)
        except Exception as e:
            logger.error("Engram tool %s failed: %s", tool_name, e)
            return tool_error(f"Engram {tool_name} failed: {e}")

    # ─── Shutdown ──────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        """Clean shutdown — wait for pending threads."""
        for t in (self._sync_thread, self._prefetch_thread):
            if t and t.is_alive():
                t.join(timeout=5.0)


# ─── Tool Handlers ────────────────────────────────────────────────────────────
# Each receives (provider, args, **kwargs) → JSON string


def _ensure_client(provider: EngramMemoryProvider) -> Any:
    if not provider._client:
        return None
    return provider._client


def _tool_json(result: Any, indent: bool = True) -> str:
    if result is None:
        return json.dumps({"error": "Engram server not reachable. Is 'engram serve' running?"})
    if isinstance(result, dict) and "error" in result:
        return json.dumps(result)
    return json.dumps(result, indent=2) if indent else json.dumps(result)


def _tool_error(msg: str) -> str:
    return tool_error(msg)


# ── mem_search ────────────────────────────────────────────────────────────────

def _mem_search(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Search persistent memory. GET /search"""
    client = _ensure_client(provider)
    if not client:
        return _tool_error("Engram not connected.")

    params = {"q": args.get("query", "")}
    if args.get("project"):
        params["project"] = args["project"]
    if args.get("scope"):
        params["scope"] = args["scope"]
    if args.get("type"):
        params["type"] = args["type"]
    if args.get("limit"):
        params["limit"] = str(args["limit"])

    result = client.search(
        query=params["q"],
        project=params.get("project", ""),
        scope=params.get("scope", ""),
        obs_type=params.get("type", ""),
        limit=int(params.get("limit", 10)),
    )
    return _tool_json(result)


# ── mem_save ─────────────────────────────────────────────────────────────────

def _mem_save(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Save an observation. POST /observations"""
    client = _ensure_client(provider)
    if not client:
        return _tool_error("Engram not connected.")

    result = client.add_observation(
        session_id=provider._session_id,
        title=args.get("title", ""),
        content=args.get("content", ""),
        project=args.get("project") or provider._project,
        obs_type=args.get("type", "learning"),
        scope=args.get("scope", "project"),
        topic_key=args.get("topic_key"),
    )
    return _tool_json(result)


# ── mem_update ───────────────────────────────────────────────────────────────

def _mem_update(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Update an observation. PATCH /observations/{id}"""
    client = _ensure_client(provider)
    if not client:
        return _tool_error("Engram not connected.")

    obs_id = args.get("id")
    if not obs_id:
        return _tool_error("id is required")

    patch_body = {}
    for field in ("title", "content", "type", "scope", "topic_key"):
        if field in args and args[field] is not None:
            patch_body[field] = args[field]

    result = client.update_observation(obs_id, **patch_body)
    return _tool_json(result)


# ── mem_delete ───────────────────────────────────────────────────────────────

def _mem_delete(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Delete an observation. DELETE /observations/{id}"""
    client = _ensure_client(provider)
    if not client:
        return _tool_error("Engram not connected.")

    obs_id = args.get("id")
    if not obs_id:
        return _tool_error("id is required")

    result = client.delete_observation(obs_id)
    return _tool_json(result)


# ── mem_context ───────────────────────────────────────────────────────────────

def _mem_context(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Get recent memory context. GET /context"""
    client = _ensure_client(provider)
    if not client:
        return _tool_error("Engram not connected.")

    result = client.get_context(
        project=args.get("project") or provider._project,
        scope=args.get("scope", ""),
    )
    return _tool_json(result)


# ── mem_session_summary ──────────────────────────────────────────────────────

def _mem_session_summary(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Save end-of-session summary. POST /observations (type=session_summary)"""
    client = _ensure_client(provider)
    if not client:
        return _tool_error("Engram not connected.")

    project = args.get("project") or provider._project
    session_id = args.get("session_id") or _default_session_id(project)
    content = args.get("content", "")

    result = client.add_observation(
        session_id=session_id,
        title=f"Session summary: {project}",
        content=content,
        project=project,
        obs_type="session_summary",
        scope="project",
    )
    return _tool_json(result)


# ── mem_get_observation ─────────────────────────────────────────────────────

def _mem_get_observation(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Get a single observation by ID. GET /observations/{id}"""
    client = _ensure_client(provider)
    if not client:
        return _tool_error("Engram not connected.")

    obs_id = args.get("id")
    if not obs_id:
        return _tool_error("id is required")

    result = client.get_observation(obs_id)
    return _tool_json(result)


# ── mem_save_prompt ─────────────────────────────────────────────────────────

def _mem_save_prompt(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Save a user prompt. POST /observations (type=prompt)"""
    client = _ensure_client(provider)
    if not client:
        return _tool_error("Engram not connected.")

    project = args.get("project") or provider._project
    session_id = args.get("session_id") or _default_session_id(project)

    result = client.add_observation(
        session_id=session_id,
        title="User prompt",
        content=args.get("content", ""),
        project=project,
        obs_type="prompt",
        scope="project",
    )
    return _tool_json(result)


# ── mem_session_start ───────────────────────────────────────────────────────

def _mem_session_start(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Register session start. POST /sessions"""
    client = _ensure_client(provider)
    if not client:
        return _tool_error("Engram not connected.")

    project = args.get("project") or provider._project
    session_id = args.get("id") or _default_session_id(project)
    directory = args.get("directory", "")

    result = client.create_session(session_id, project, directory)
    if result is None:
        return json.dumps({
            "id": None,
            "message": f"Session registered locally (engram server may be offline). ID={session_id}",
        })
    return _tool_json(result)


# ── mem_session_end ─────────────────────────────────────────────────────────

def _mem_session_end(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Mark session as completed. POST /sessions/{id}/end"""
    client = _ensure_client(provider)
    if not client:
        return _tool_error("Engram not connected.")

    session_id = args.get("id") or provider._session_id
    summary = args.get("summary", "")

    result = client.end_session(session_id, summary)
    if result is None:
        return json.dumps({"message": f"Session end noted locally. ID={session_id}"})
    return _tool_json(result)


# ── mem_timeline ─────────────────────────────────────────────────────────────

def _mem_timeline(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Get project activity timeline. GET /timeline"""
    client = _ensure_client(provider)
    if not client:
        return _tool_error("Engram not connected.")

    result = client.timeline(
        project=args.get("project") or provider._project,
        scope=args.get("scope", ""),
        limit=int(args.get("limit", 20)),
    )
    return _tool_json(result)


# ── mem_current_project ─────────────────────────────────────────────────────

def _mem_current_project(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Detect current project."""
    return json.dumps({
        "project": provider._project,
        "directory": provider._directory,
        "source": "engram-memory-provider",
    })


# ── mem_capture_passive ─────────────────────────────────────────────────────

def _mem_capture_passive(provider: EngramMemoryProvider, args: dict, **kwargs) -> str:
    """Extract learnings from text output. POST /observations/passive"""
    client = _ensure_client(provider)
    if not client:
        return _tool_error("Engram not connected.")

    project = args.get("project") or provider._project
    session_id = args.get("session_id") or provider._session_id

    result = client.passive_capture(
        session_id=session_id,
        content=args.get("content", ""),
        project=project,
        source=args.get("source", "passive_capture"),
    )
    return _tool_json(result)


# ─── Tool registry ───────────────────────────────────────────────────────────

_TOOL_HANDLERS: Dict[str, callable] = {
    "mem_search": _mem_search,
    "mem_save": _mem_save,
    "mem_update": _mem_update,
    "mem_delete": _mem_delete,
    "mem_context": _mem_context,
    "mem_session_summary": _mem_session_summary,
    "mem_get_observation": _mem_get_observation,
    "mem_save_prompt": _mem_save_prompt,
    "mem_session_start": _mem_session_start,
    "mem_session_end": _mem_session_end,
    "mem_timeline": _mem_timeline,
    "mem_current_project": _mem_current_project,
    "mem_capture_passive": _mem_capture_passive,
}


# ─── Plugin entry point ───────────────────────────────────────────────────────


def register(ctx) -> None:
    """Register Engram as a memory provider plugin."""
    ctx.register_memory_provider(EngramMemoryProvider())
