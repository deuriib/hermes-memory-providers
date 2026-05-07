"""
Engram Memory Provider Plugin for Hermes Agent

Implements the MemoryProvider ABC to provide persistent memory across sessions.
Connects to the Engram Go binary running as a local HTTP server.

Flow:
    Hermes MemoryProvider → HTTP calls → engram serve → SQLite
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional

from agent.memory_provider import MemoryProvider
from . import schemas, tools

logger = logging.getLogger(__name__)


class EngramMemoryProvider(MemoryProvider):
    """
    Engram persistent memory provider implementation.
    
    Connects to 'engram serve' running locally and provides tools for
    memory search, save, update, and session management.
    """

    def __init__(self):
        self._session_id: Optional[str] = None
        self._hermes_home: Optional[Path] = None
        self._config: Dict = {}
        self._sync_thread: Optional[threading.Thread] = None

    @property
    def name(self) -> str:
        return "engram"

    def is_available(self) -> bool:
        """Check if Engram is available. No network calls."""
        # Check if engram binary exists in PATH
        import shutil
        return shutil.which(os.environ.get("ENGRAM_BIN", "engram")) is not None

    def initialize(self, session_id: str, **kwargs) -> None:
        """Called once at agent startup."""
        self._session_id = session_id
        self._hermes_home = Path(kwargs.get("hermes_home", "~/.hermes")).expanduser()
        
        # Load config if it exists
        config_path = self._hermes_home / "engram.json"
        if config_path.exists():
            try:
                self._config = json.loads(config_path.read_text())
            except Exception as e:
                logger.warning("Failed to load engram config: %s", e)
        
        # Set up session context
        cwd = os.getcwd()
        tools.set_session_context(cwd)
        
        # Ensure engram server is running
        tools._ensure_server()
        
        # Register session
        tools.ensure_session(session_id)
        
        logger.info("Engram memory provider initialized for session: %s", session_id)

    def get_config_schema(self) -> List[Dict]:
        """Return config schema for 'hermes memory setup'."""
        return [
            {
                "key": "port",
                "description": "Engram server port",
                "default": "7437",
                "env_var": "ENGRAM_PORT",
            },
            {
                "key": "binary_path",
                "description": "Path to engram binary",
                "default": "engram", 
                "env_var": "ENGRAM_BIN",
            },
        ]

    def save_config(self, values: Dict, hermes_home: str) -> None:
        """Write non-secret config to engram.json."""
        config_path = Path(hermes_home) / "engram.json"
        config_path.write_text(json.dumps(values, indent=2))

    def get_tool_schemas(self) -> List[Dict]:
        """Return tool schemas in OpenAI function-calling format."""
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
            schemas.MEM_JUDGE,
            schemas.MEM_DOCTOR,
            schemas.MEM_CURRENT_PROJECT,
            schemas.MEM_CAPTURE_PASSIVE,
            schemas.MEM_STATS,
        ]

    def handle_tool_call(self, tool_name: str, args: Dict) -> str:
        """Handle tool calls by routing to appropriate handler."""
        handlers = {
            "mem_search": tools.mem_search,
            "mem_save": tools.mem_save,
            "mem_update": tools.mem_update,
            "mem_delete": tools.mem_delete,
            "mem_context": tools.mem_context,
            "mem_session_summary": tools.mem_session_summary,
            "mem_get_observation": tools.mem_get_observation,
            "mem_save_prompt": tools.mem_save_prompt,
            "mem_session_start": tools.mem_session_start,
            "mem_session_end": tools.mem_session_end,
            "mem_timeline": tools.mem_timeline,
            "mem_judge": tools.mem_judge,
            "mem_doctor": tools.mem_doctor,
            "mem_current_project": tools.mem_current_project,
            "mem_capture_passive": tools.mem_capture_passive,
            "mem_stats": tools.mem_stats,
        }
        
        handler = handlers.get(tool_name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        
        try:
            return handler(args)
        except Exception as e:
            logger.exception("Error handling tool %s", tool_name)
            return json.dumps({"error": str(e)})

    def system_prompt_block(self) -> str:
        """Return memory protocol instructions for system prompt."""
        return """
## Engram Persistent Memory — Protocol

You have access to Engram, a persistent memory system that survives across sessions and compactions.
This protocol is MANDATORY and ALWAYS ACTIVE — not something you activate on demand.

### PROACTIVE SAVE TRIGGERS (mandatory — do NOT wait for user to ask)

Call `mem_save` IMMEDIATELY and WITHOUT BEING ASKED after any of these:
- Architecture or design decision made
- Team convention documented or established
- Workflow change agreed upon
- Tool or library choice made with tradeoffs
- Bug fix completed (include root cause)
- Feature implemented with non-obvious approach
- Configuration change or environment setup done
- Non-obvious discovery about the codebase
- Gotcha, edge case, or unexpected behavior found
- Pattern established (naming, structure, convention)
- User preference or constraint learned

Format for `mem_save`:
- **title**: Verb + what — short, searchable (e.g. "Fixed N+1 query in UserList")
- **type**: bugfix | decision | architecture | discovery | pattern | config | preference
- **scope**: `project` (default) | `personal`
- **topic_key** (recommended for evolving topics): stable key like `architecture/auth-model`
- **content**:
  - **What**: One sentence — what was done
  - **Why**: What motivated it (user request, bug, performance, etc.)
  - **Where**: Files or paths affected
  - **Learned**: Gotchas, edge cases, things that surprised you (omit if none)

### WHEN TO SEARCH MEMORY

On any variation of "remember", "recall", "what did we do", "how did we solve", "recordar", "qué hicimos", or references to past work:
1. Call `mem_context` — checks recent session history (fast, cheap)
2. If not found, call `mem_search` with relevant keywords
3. If found, use `mem_get_observation` for full untruncated content

Also search PROACTIVELY when:
- Starting work on something that might have been done before
- User mentions a topic you have no context on
- User's FIRST message references the project, a feature, or a problem — call `mem_search` with keywords from their message to check for prior work before responding

### SESSION CLOSE PROTOCOL (mandatory)

Before ending a session or saying "done" / "listo" / "that's it", call `mem_session_summary` with this structure:

## Goal
[What we were working on this session]

## Instructions
[User preferences or constraints discovered — skip if none]

## Discoveries
- [Technical findings, gotchas, non-obvious learnings]

## Accomplished
- [Completed items with key details]

## Next Steps
- [What remains to be done — for the next session]

## Relevant Files
- path/to/file — [what it does or what changed]

This is NOT optional. If you skip this, the next session starts blind.
"""

    def prefetch(self, query: str) -> str:
        """Called before each API call - return recalled context."""
        try:
            # Quick context fetch
            context_data = tools._engram_fetch(
                "/context", params={"project": tools._current_project}
            )
            if context_data and context_data.get("context"):
                return context_data["context"]
        except Exception as e:
            logger.debug("Prefetch failed: %s", e)
        return ""

    def queue_prefetch(self, query: str) -> None:
        """Queue pre-warming for next turn (non-blocking)."""
        def _prefetch():
            try:
                # Pre-warm with search based on query
                tools._engram_fetch(
                    "/search", 
                    params={"q": query[:100], "project": tools._current_project, "limit": "5"}
                )
            except Exception as e:
                logger.debug("Queue prefetch failed: %s", e)
        
        thread = threading.Thread(target=_prefetch, daemon=True)
        thread.start()

    def sync_turn(self, user_content: str, assistant_content: str, **kwargs) -> None:
        """MUST be non-blocking. Persist conversation turn."""
        def _sync():
            try:
                if self._session_id:
                    # Save user prompt
                    tools.capture_prompt(self._session_id, user_content)
            except Exception as e:
                logger.warning("Turn sync failed: %s", e)
        
        # Wait for previous sync to complete
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=5.0)
        
        self._sync_thread = threading.Thread(target=_sync, daemon=True)
        self._sync_thread.start()

    def on_session_end(self, messages: List[Dict]) -> None:
        """Called when conversation ends."""
        try:
            if self._session_id:
                tools.clear_session(self._session_id)
        except Exception as e:
            logger.warning("Session end cleanup failed: %s", e)

    def shutdown(self) -> None:
        """Clean up connections."""
        try:
            if self._sync_thread and self._sync_thread.is_alive():
                self._sync_thread.join(timeout=10.0)
        except Exception as e:
            logger.warning("Shutdown cleanup failed: %s", e)


def register(ctx) -> None:
    """Called by the memory plugin discovery system."""
    ctx.register_memory_provider(EngramMemoryProvider())
