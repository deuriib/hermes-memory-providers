"""Engram Context Engine Plugin for Hermes Agent.

Implements the ContextEngine ABC using Engram as a persistent knowledge graph
for conversation context management. Instead of lossy summarization, this
engine preserves conversation history as structured observations in Engram,
allowing the agent to retrieve and expand relevant context on demand.

Flow:
    Hermes ContextEngine → compress() → save to Engram → return compressed summary
    Agent calls engram_recall() → Engram returns relevant historical context
"""

from typing import Any, Dict, List, Optional
import json
import logging
import os
import threading
from pathlib import Path

import requests
from agent.context_engine import ContextEngine

logger = logging.getLogger(__name__)

# ─── Engram HTTP Client ──────────────────────────────────────────────────────

ENGRAM_PORT = int(os.environ.get("ENGRAM_PORT", "7437"))
ENGRAM_URL = f"http://127.0.0.1:{ENGRAM_PORT}"
ENGRAM_BIN = os.environ.get("ENGRAM_BIN", "engram")

_session_lock = threading.Lock()
_session: Optional["requests.Session"] = None


def _get_session() -> "requests.Session":
    """Get or create a shared requests session."""
    global _session
    if _session is None:
        import requests as _requests
        _session = _requests.Session()
        _session.headers.update({"Content-Type": "application/json"})
    return _session


def _engram_fetch(
    path: str,
    method: str = "GET",
    body: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: float = 5.0,
) -> Optional[dict]:
    """Call engram serve HTTP API.

    Returns None only when the server is completely unreachable.
    For HTTP errors, returns a dict describing the error.
    """
    try:
        import requests
        url = f"{ENGRAM_URL}{path}"
        resp = _get_session().request(
            method, url, json=body, params=params, timeout=timeout
        )
        if resp.status_code >= 400:
            try:
                payload = resp.json()
                return {
                    "error": payload.get("error") or payload.get("message") or str(resp.status_code),
                    "status": resp.status_code,
                }
            except Exception:
                return {"error": resp.text or str(resp.status_code), "status": resp.status_code}
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        logger.warning("engram fetch error %s %s: %s", method, path, e)
        return None


def _is_engram_running() -> bool:
    """Check if engram serve is running."""
    try:
        resp = _get_session().get(f"{ENGRAM_URL}/health", timeout=1.0)
        return resp.status_code == 200
    except Exception:
        return False


def _ensure_server() -> bool:
    """Try to start engram serve if not running. Returns True if running."""
    if _is_engram_running():
        return True

    try:
        import subprocess
        subprocess.Popen(
            [ENGRAM_BIN, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        import time
        for _ in range(10):
            time.sleep(0.3)
            if _is_engram_running():
                return True
    except Exception as e:
        logger.debug("Could not start engram serve: %s", e)

    return False


def _extract_project(directory: str) -> str:
    """Extract project name from git remote origin URL."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "-C", directory, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            name = os.path.basename(result.stdout.strip()).replace(".git", "")
            if name:
                return name
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["git", "-C", directory, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            root = result.stdout.strip()
            if root:
                return os.path.basename(os.path.normpath(root))
    except Exception:
        pass

    return os.path.basename(os.path.normpath(directory)) or "unknown"


def _truncate(s: str, max_chars: int) -> str:
    return s[:max_chars] + "..." if len(s) > max_chars else s


# ─── Engine Implementation ───────────────────────────────────────────────────

class EngramContextEngine(ContextEngine):
    """
    Context engine that uses Engram as a persistent knowledge graph store.

    Instead of losing information through summarization, this engine:
    1. Saves conversation turns as observations in Engram
    2. On compress(), creates a "snapshot" observation with summary + metadata
    3. On recall, queries Engram for relevant historical context

    The agent can call `engram_recall` to expand a compressed snapshot back
    into full context when needed.
    """

    # Class attributes (required by ContextEngine ABC)
    last_prompt_tokens: int = 0
    last_completion_tokens: int = 0
    last_total_tokens: int = 0
    threshold_tokens: int = 0
    context_length: int = 0
    compression_count: int = 0

    # Override defaults from ABC
    threshold_percent: float = 0.80  # Slightly higher - we don't lose info
    protect_first_n: int = 2       # Keep system + first user message
    protect_last_n: int = 8        # Keep recent context

    def __init__(self):
        self._session_id: Optional[str] = None
        self._project: str = "unknown"
        self._directory: str = ""
        self._hermes_home: Optional[Path] = None
        self._snapshot_id: Optional[int] = None  # ID of last snapshot in Engram
        self._turn_count: int = 0
        self._total_tokens_seen: int = 0
        self._initialized: bool = False

    @property
    def name(self) -> str:
        """Short identifier - must match config.yaml value."""
        return "engram"

    def is_available(self) -> bool:
        """Check if Engram is available. No network calls."""
        import shutil
        return shutil.which(os.environ.get("ENGRAM_BIN", "engram")) is not None

    # ─── Core ContextEngine interface ────────────────────────────────────────

    def update_from_response(self, usage: Dict[str, Any]) -> None:
        """Update tracked token usage from an API response."""
        self.last_prompt_tokens = usage.get("prompt_tokens", 0)
        self.last_completion_tokens = usage.get("completion_tokens", 0)
        self.last_total_tokens = usage.get("total_tokens", 0)
        self._total_tokens_seen += self.last_total_tokens

        # Update context_length if provided
        if "context_length" in usage:
            self.context_length = usage["context_length"]
            self.threshold_tokens = int(self.context_length * self.threshold_percent)

    def should_compress(self, prompt_tokens: int = None) -> bool:
        """Return True if compaction should fire this turn."""
        if self.context_length <= 0:
            return False

        tokens = prompt_tokens if prompt_tokens is not None else self.last_prompt_tokens

        # Trigger if we're at 80% of context (configurable)
        threshold = int(self.context_length * self.threshold_percent)
        return tokens >= threshold

    def compress(
        self,
        messages: List[Dict[str, Any]],
        current_tokens: int = None,
        focus_topic: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Compact the message list using Engram as a knowledge graph store.

        Instead of destructive summarization, this:
        1. Protects first N messages (system, initial context)
        2. Protects last N messages (recent conversation)
        3. Middle messages are saved as a snapshot in Engram
        4. Returns a compressed list with a summary message explaining the snapshot
        """
        if not messages:
            return messages

        self.compression_count += 1

        # Determine protected ranges
        protected_count = self.protect_first_n + self.protect_last_n
        if protected_count >= len(messages):
            # Not enough messages to compress meaningfully
            return messages[-self.protect_last_n:] if self.protect_last_n else messages

        # Build protected message lists
        head = messages[:self.protect_first_n]
        tail = messages[-self.protect_last_n:] if self.protect_last_n else []
        middle = messages[self.protect_first_n:-self.protect_last_n] if self.protect_last_n else messages[self.protect_first_n:]

        # Save middle messages to Engram as a snapshot
        self._save_snapshot(middle, focus_topic)

        # Build compressed message list
        compressed = list(head)

        # Add summary message explaining the compression
        summary = self._build_summary_message(middle, focus_topic)
        if summary:
            compressed.append(summary)

        # Add tail
        compressed.extend(tail)

        return compressed

    def _save_snapshot(
        self,
        messages: List[Dict[str, Any]],
        focus_topic: Optional[str] = None,
    ) -> None:
        """Save compressed messages as a snapshot observation in Engram."""
        try:
            # Build a structured representation of the conversation
            turns = []
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")

                # Handle tool calls/results
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        turns.append({
                            "role": "assistant",
                            "type": "tool_call",
                            "name": tc.get("name", "unknown"),
                            "args": tc.get("arguments", ""),
                        })
                elif msg.get("tool_call_id"):
                    # Tool result
                    turns.append({
                        "role": "tool",
                        "content": content,
                    })
                else:
                    turns.append({
                        "role": role,
                        "content": _truncate(str(content), 500),
                    })

            snapshot_content = {
                "compression_number": self.compression_count,
                "turn_count": self._turn_count,
                "total_tokens": self._total_tokens_seen,
                "focus_topic": focus_topic,
                "message_count": len(messages),
                "turns": turns,
            }

            result = _engram_fetch(
                "/observations",
                method="POST",
                body={
                    "title": f"Context Snapshot #{self.compression_count}",
                    "content": json.dumps(snapshot_content, indent=2),
                    "type": "context_snapshot",
                    "scope": "project",
                    "project": self._project,
                    "topic_key": f"context/snapshot-{self.compression_count}",
                },
            )

            if result and "id" in result:
                self._snapshot_id = result["id"]

            logger.info(
                "Saved context snapshot #%d to Engram (ID: %s)",
                self.compression_count,
                self._snapshot_id,
            )

        except Exception as e:
            logger.warning("Failed to save snapshot to Engram: %s", e)

    def _build_summary_message(
        self,
        messages: List[Dict[str, Any]],
        focus_topic: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Build a summary message to insert in place of compressed messages."""
        topic_info = f" (focus: {focus_topic})" if focus_topic else ""

        turn_count = len(messages)
        approx_topics = self._extract_topics(messages)

        summary_parts = [
            f"[Context compressed: {turn_count} messages summarized into snapshot "
            f"#{self.compression_count}{topic_info}]",
        ]

        if approx_topics:
            summary_parts.append(f"Topics covered: {', '.join(approx_topics[:5])}")

        summary_parts.append(
            f"Full context available via engram_recall(snapshot_id={self._snapshot_id})"
        )

        return {
            "role": "system",
            "content": "\n\n".join(summary_parts),
        }

    def _extract_topics(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract approximate topics from messages (simple heuristic)."""
        topics = []
        for msg in messages:
            content = str(msg.get("content", ""))
            # Look for code blocks, file paths, specific terms
            if "def " in content or "class " in content:
                topics.append("code")
            if "import " in content:
                topics.append("imports")
            if ".py" in content or ".ts" in content or ".js" in content:
                topics.append("files")
            if "test" in content.lower():
                topics.append("testing")
            if "bug" in content.lower() or "error" in content.lower():
                topics.append("debugging")
        return list(set(topics))

    # ─── Session lifecycle ────────────────────────────────────────────────────

    def on_session_start(self, session_id: str, **kwargs) -> None:
        """Called when a new conversation session begins."""
        self._session_id = session_id
        self._hermes_home = Path(kwargs.get("hermes_home", "~/.hermes")).expanduser()

        # Determine project from directory
        self._directory = kwargs.get("directory", os.getcwd())
        self._project = _extract_project(self._directory)

        # Ensure Engram server is running
        _ensure_server()

        # Register session in Engram
        if self._session_id:
            _engram_fetch(
                "/sessions",
                method="POST",
                body={
                    "id": self._session_id,
                    "project": self._project,
                    "directory": self._directory,
                },
            )

        self._initialized = True
        logger.info("Engram context engine started for session %s (project: %s)", session_id, self._project)

    def on_session_end(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """Called at real session boundaries (CLI exit, /reset, gateway expiry)."""
        try:
            # Save final conversation state as a session observation
            if self._session_id and messages:
                _engram_fetch(
                    "/observations",
                    method="POST",
                    body={
                        "title": f"Session ended: {self._project}",
                        "content": self._build_session_summary(messages),
                        "type": "session_end",
                        "scope": "project",
                        "project": self._project,
                        "topic_key": f"session/{session_id}",
                    },
                )

            # Clean up state
            self._session_id = None
            self._snapshot_id = None
            self._initialized = False

            logger.info("Engram context engine session ended")

        except Exception as e:
            logger.warning("Session end cleanup failed: %s", e)

    def on_session_reset(self) -> None:
        """Called on /new or /reset. Reset per-session state."""
        super().on_session_reset()
        self._turn_count = 0
        self._total_tokens_seen = 0
        self._snapshot_id = None

    # ─── Engine tools ─────────────────────────────────────────────────────────

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return tool schemas in flat format.

        Hermes Agent wraps these in {"type": "function", "function": {...}}
        automatically at run_agent.py line 2103.
        """
        return [
            {
                "name": "engram_recall",
                "description": (
                    "Retrieve full context from a compressed Engram snapshot. "
                    "Use this when you need to expand on details from a compressed "
                    "context window. Returns the original conversation turns from "
                    "the snapshot."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "snapshot_id": {
                            "type": "integer",
                            "description": (
                                "The snapshot ID from the compressed context message. "
                                "Extract from the engram_recall(...) call in the summary."
                            ),
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional search query to filter snapshot content.",
                        },
                    },
                    "required": ["snapshot_id"],
                },
            },
            {
                "name": "engram_search_context",
                "description": (
                    "Search Engram for relevant context across all snapshots. "
                    "Use this to find information from previous sessions or "
                    "compressed conversations."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for context.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return (default: 5).",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
        ]

    def handle_tool_call(
        self,
        name: str,
        args: Dict[str, Any],
        **kwargs,
    ) -> str:
        """Handle tool calls from the agent."""
        handlers = {
            "engram_recall": self._handle_recall,
            "engram_search_context": self._handle_search_context,
        }

        handler = handlers.get(name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {name}"})

        try:
            return handler(args)
        except Exception as e:
            logger.exception("Error handling tool %s", name)
            return json.dumps({"error": str(e)})

    def _handle_recall(self, args: Dict[str, Any]) -> str:
        """Handle engram_recall tool call."""
        snapshot_id = args.get("snapshot_id")
        query = args.get("query")

        if not snapshot_id:
            return json.dumps({"error": "snapshot_id is required"})

        # Fetch the snapshot from Engram
        result = _engram_fetch(f"/observations/{snapshot_id}", method="GET")

        if result is None:
            return json.dumps({
                "error": "Engram server not reachable. Is 'engram serve' running?",
            })

        if "error" in result:
            return json.dumps(result)

        # Parse and return the snapshot content
        content = result.get("content", "{}")
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {"raw_content": content}

        return json.dumps({
            "snapshot_id": snapshot_id,
            "project": result.get("project"),
            "created_at": result.get("created_at"),
            "compression_number": data.get("compression_number"),
            "turn_count": data.get("turn_count"),
            "focus_topic": data.get("focus_topic"),
            "turns": data.get("turns", []),
            "query_filter": query,
        }, indent=2)

    def _handle_search_context(self, args: Dict[str, Any]) -> str:
        """Handle engram_search_context tool call."""
        query = args.get("query", "")
        limit = args.get("limit", 5)

        result = _engram_fetch(
            "/search",
            method="GET",
            params={
                "q": query,
                "project": self._project,
                "type": "context_snapshot",
                "limit": str(limit),
            },
        )

        if result is None:
            return json.dumps({
                "error": "Engram server not reachable. Is 'engram serve' running?",
            })

        return json.dumps(result, indent=2)

    # ─── Status / Display ────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Return status dict for display/logging."""
        base = super().get_status()
        base.update({
            "engine": "engram",
            "project": self._project,
            "snapshot_id": self._snapshot_id,
            "turn_count": self._turn_count,
        })
        return base

    def update_model(
        self,
        model: str,
        context_length: int,
        base_url: str = "",
        api_key: str = "",
        provider: str = "",
    ) -> None:
        """Called when the user switches models."""
        self.context_length = context_length
        self.threshold_tokens = int(context_length * self.threshold_percent)
        logger.info(
            "Model updated: context_length=%d, threshold=%d",
            context_length,
            self.threshold_tokens,
        )

    # ─── Helper methods ──────────────────────────────────────────────────────

    def _build_session_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Build a session summary for end-of-session logging."""
        total_messages = len(messages)
        roles = {}
        for msg in messages:
            role = msg.get("role", "unknown")
            roles[role] = roles.get(role, 0) + 1

        return json.dumps({
            "session_id": self._session_id,
            "project": self._project,
            "directory": self._directory,
            "total_messages": total_messages,
            "roles": roles,
            "compression_count": self.compression_count,
            "total_tokens": self._total_tokens_seen,
            "snapshots": self.compression_count,
        }, indent=2)

    def _increment_turn(self) -> None:
        """Track conversation turns for snapshot metadata."""
        self._turn_count += 1


# ─── Plugin registration ──────────────────────────────────────────────────────

def register(ctx) -> None:
    """Called by the context engine plugin discovery system."""
    ctx.register_context_engine(EngramContextEngine())