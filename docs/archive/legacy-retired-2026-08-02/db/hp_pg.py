"""HP Postgres knowledge stub — not wired in production.

Real HP KB lives outside this repo. This module previously imported asyncpg
and returned hard-coded stubs; callers must not treat it as a live DB.
"""

from __future__ import annotations

from typing import Optional


class KnowledgeHP:
    """Placeholder. Raises if used — do not silently return fake data."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        raise NotImplementedError(
            "KnowledgeHP is not connected; use HP KB MCP / external service"
        )

    def get_failure_patterns(self, category: Optional[str] = None):
        raise NotImplementedError("KnowledgeHP is not connected")

    def record_failure(self, task_id: str, category: Optional[str] = None):
        raise NotImplementedError("KnowledgeHP is not connected")

    def insert_failure_log(self, timestamp: str, category: Optional[str] = None):
        raise NotImplementedError("KnowledgeHP is not connected")

    def record_failure_stats(self, task_type: Optional[str] = None):
        raise NotImplementedError("KnowledgeHP is not connected")

    def insert_knowledge_meta(self, tags: Optional[str] = None):
        raise NotImplementedError("KnowledgeHP is not connected")
