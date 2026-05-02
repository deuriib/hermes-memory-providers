"""Engram HTTP client — wraps engram serve REST API.

Resolution order for config:
  1. $HERMES_HOME/engram.json (profile-scoped)
  2. Environment variables (ENGRAM_PORT, ENGRAM_URL, ENGRAM_BIN)

engram serve must be running at http://127.0.0.1:7437 (default).
The client auto-starts it on first use if ENGRAM_BIN is set.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default port and binary name
DEFAULT_PORT = 7437


def resolve_config_path(hermes_home: str) -> Path:
    """Return the Engram config path for this profile."""
    return Path(hermes_home) / "engram.json"


# ─── HTTP client ───────────────────────────────────────────────────────────────


class EngramHTTPClient:
    """Lightweight HTTP client for engram serve.

    Wraps all REST endpoints used by the memory provider plugin.
    All methods return None on ConnectionError (server unreachable) so callers
    can decide how to degrade gracefully.
    """

    def __init__(
        self,
        port: int | None = None,
        base_url: str | None = None,
        bin_path: str | None = None,
        timeout: float = 5.0,
    ):
        self.port = port or int(os.environ.get("ENGRAM_PORT", DEFAULT_PORT))
        self.base_url = base_url or os.environ.get("ENGRAM_URL", f"http://127.0.0.1:{self.port}")
        self.bin_path = bin_path or os.environ.get("ENGRAM_BIN", "engram")
        self.timeout = timeout
        self._session_lock = threading.Lock()
        self._session_cache: Dict[str, bool] = {}

    # ─── Server lifecycle ──────────────────────────────────────────────────

    def is_running(self) -> bool:
        """Check if engram serve is running at base_url."""
        try:
            import requests

            resp = requests.get(f"{self.base_url}/health", timeout=1.0)
            return resp.status_code == 200
        except Exception:
            return False

    def ensure_running(self) -> bool:
        """Try to start engram serve if not running. Returns True if running."""
        if self.is_running():
            return True

        try:
            subprocess.Popen(
                [self.bin_path, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            for _ in range(15):  # up to 4.5s
                time.sleep(0.3)
                if self.is_running():
                    return True
        except Exception as e:
            logger.debug("Could not start engram serve: %s", e)

        return False

    # ─── Low-level fetch ─────────────────────────────────────────────────────

    def _fetch(
        self,
        path: str,
        method: str = "GET",
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float | None = None,
    ) -> Optional[Dict[str, Any]]:
        """Call engram serve REST API.

        Returns None on ConnectionError only.
        HTTP 4xx/5xx returns a dict with 'error' and 'status' so callers can
        surface real failures instead of a generic "server not reachable" message.
        """
        import requests

        timeout = timeout or self.timeout
        try:
            resp = requests.request(
                method,
                f"{self.base_url}{path}",
                json=body,
                params=params,
                timeout=timeout,
                headers={"Content-Type": "application/json"},
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

    # ─── Sessions ────────────────────────────────────────────────────────────

    def create_session(
        self,
        session_id: str,
        project: str,
        directory: str = "",
    ) -> Optional[Dict[str, Any]]:
        """POST /sessions — register a session. Idempotent."""
        return self._fetch("/sessions", method="POST", body={
            "id": session_id,
            "project": project,
            "directory": directory,
        })

    def ensure_session(self, session_id: str, project: str, directory: str = "") -> bool:
        """Ensure a session exists. Thread-safe and idempotent."""
        if session_id in self._session_cache:
            return True

        result = self.create_session(session_id, project, directory)
        if result is not None:
            with self._session_lock:
                self._session_cache[session_id] = True
            return True
        return False

    def end_session(self, session_id: str, summary: str = "") -> Optional[Dict[str, Any]]:
        """POST /sessions/{id}/end — mark session as completed."""
        return self._fetch(f"/sessions/{session_id}/end", method="POST", body={
            "summary": summary,
        })

    def recent_sessions(
        self, project: str = "", limit: int = 5
    ) -> Optional[List[Dict[str, Any]]]:
        """GET /sessions/recent — list recent sessions."""
        params = {"limit": str(limit)}
        if project:
            params["project"] = project
        result = self._fetch("/sessions/recent", params=params)
        if result is None:
            return None
        if isinstance(result, dict) and "error" in result:
            return []
        return result

    # ─── Observations ────────────────────────────────────────────────────────

    def add_observation(
        self,
        session_id: str,
        title: str,
        content: str,
        project: str,
        obs_type: str = "learning",
        scope: str = "project",
        topic_key: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """POST /observations — create a new observation."""
        body: Dict[str, Any] = {
            "session_id": session_id,
            "title": title,
            "content": content,
            "project": project,
            "type": obs_type,
            "scope": scope,
        }
        if topic_key:
            body["topic_key"] = topic_key
        if source:
            body["source"] = source
        return self._fetch("/observations", method="POST", body=body)

    def passive_capture(
        self,
        session_id: str,
        content: str,
        project: str,
        source: str = "passive_capture",
    ) -> Optional[Dict[str, Any]]:
        """POST /observations/passive — best-effort passive capture."""
        return self._fetch("/observations/passive", method="POST", body={
            "session_id": session_id,
            "content": content,
            "project": project,
            "source": source,
        })

    def get_observation(self, obs_id: int) -> Optional[Dict[str, Any]]:
        """GET /observations/{id} — fetch a single observation."""
        return self._fetch(f"/observations/{obs_id}")

    def update_observation(
        self,
        obs_id: int,
        **fields,
    ) -> Optional[Dict[str, Any]]:
        """PATCH /observations/{id} — update fields."""
        return self._fetch(f"/observations/{obs_id}", method="PATCH", body=fields)

    def delete_observation(self, obs_id: int) -> Optional[Dict[str, Any]]:
        """DELETE /observations/{id} — delete an observation."""
        return self._fetch(f"/observations/{obs_id}", method="DELETE")

    def recent_observations(
        self,
        project: str = "",
        scope: str = "",
        limit: int = 10,
    ) -> Optional[List[Dict[str, Any]]]:
        """GET /observations/recent — recent observations."""
        params: Dict[str, Any] = {"limit": str(limit)}
        if project:
            params["project"] = project
        if scope:
            params["scope"] = scope
        result = self._fetch("/observations/recent", params=params)
        if result is None:
            return None
        if isinstance(result, dict) and "error" in result:
            return []
        return result

    # ─── Search ──────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        project: str = "",
        scope: str = "",
        obs_type: str = "",
        limit: int = 10,
    ) -> Optional[List[Dict[str, Any]]]:
        """GET /search — FTS5 full-text search."""
        params: Dict[str, Any] = {"q": query}
        if project:
            params["project"] = project
        if scope:
            params["scope"] = scope
        if obs_type:
            params["type"] = obs_type
        if limit:
            params["limit"] = str(limit)
        result = self._fetch("/search", params=params)
        if result is None:
            return None
        if isinstance(result, dict) and "error" in result:
            return []
        return result

    # ─── Timeline ────────────────────────────────────────────────────────────

    def timeline(
        self,
        project: str = "",
        scope: str = "",
        limit: int = 20,
    ) -> Optional[List[Dict[str, Any]]]:
        """GET /timeline — project activity timeline."""
        params: Dict[str, Any] = {}
        if project:
            params["project"] = project
        if scope:
            params["scope"] = scope
        if limit:
            params["limit"] = str(limit)
        result = self._fetch("/timeline", params=params)
        if result is None:
            return None
        if isinstance(result, dict) and "error" in result:
            return []
        return result

    # ─── Context ─────────────────────────────────────────────────────────────

    def get_context(
        self,
        project: str = "",
        scope: str = "",
    ) -> Optional[Dict[str, Any]]:
        """GET /context — recent session context for injection."""
        params: Dict[str, Any] = {}
        if project:
            params["project"] = project
        if scope:
            params["scope"] = scope
        return self._fetch("/context", params=params)

    # ─── Stats ───────────────────────────────────────────────────────────────

    def get_stats(self, project: str = "") -> Optional[Dict[str, Any]]:
        """GET /stats — memory statistics."""
        params: Dict[str, Any] = {}
        if project:
            params["project"] = project
        return self._fetch("/stats", params=params)

    # ─── Doctor ─────────────────────────────────────────────────────────────

    def get_doctor(self, project: str = "", check: str = "") -> Optional[Dict[str, Any]]:
        """GET /doctor — operational diagnostics."""
        params: Dict[str, Any] = {}
        if project:
            params["project"] = project
        if check:
            params["check"] = check
        return self._fetch("/doctor", params=params)

    # ─── Judge ──────────────────────────────────────────────────────────────

    def post_judge(
        self,
        judgment_id: str,
        relation: str,
        reason: str = "",
        confidence: float = 1.0,
    ) -> Optional[Dict[str, Any]]:
        """POST /judge — record verdict on memory conflict."""
        return self._fetch("/judge", method="POST", body={
            "judgment_id": judgment_id,
            "relation": relation,
            "reason": reason,
            "confidence": confidence,
        })

    # ─── Prompts ────────────────────────────────────────────────────────────

    def add_prompt(
        self,
        session_id: str,
        content: str,
        project: str,
    ) -> Optional[Dict[str, Any]]:
        """POST /prompts — capture a user prompt."""
        return self._fetch("/prompts", method="POST", body={
            "session_id": session_id,
            "content": content,
            "project": project,
        })

    def search_prompts(
        self,
        query: str,
        project: str = "",
        limit: int = 10,
    ) -> Optional[List[Dict[str, Any]]]:
        """GET /prompts/search — search prompts."""
        params: Dict[str, Any] = {"q": query}
        if project:
            params["project"] = project
        if limit:
            params["limit"] = str(limit)
        result = self._fetch("/prompts/search", params=params)
        if result is None:
            return None
        if isinstance(result, dict) and "error" in result:
            return []
        return result

    # ─── Helpers ────────────────────────────────────────────────────────────

    def clear_session_cache(self, session_id: Optional[str] = None) -> None:
        """Clear the known-sessions cache."""
        with self._session_lock:
            if session_id:
                self._session_cache.pop(session_id, None)
            else:
                self._session_cache.clear()
