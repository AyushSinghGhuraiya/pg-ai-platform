"""
Supabase-backed LangGraph checkpointer.

Persists conversation state to the `conversation_checkpoints` table so that
every lead's conversation survives restarts and can be resumed mid-flow.

thread_id  = lead_id   (one thread per lead)
checkpoint_ns = "" (default namespace, single-tenant per thread)

Serialisation uses LangGraph's built-in JsonPlusSerializer which produces
(type_tag, bytes) pairs. We store them as two TEXT columns so the data is
readable in the Supabase dashboard without extra tooling.

The MemorySaver stores channel_values separately in a blob dict; we keep the
full checkpoint inline (simpler schema, acceptable for our message volumes).
"""

from __future__ import annotations

import base64
import logging
from typing import Any, AsyncIterator, Optional, Sequence

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    PendingWrite,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

log = logging.getLogger(__name__)


def _encode(pair: tuple[str, bytes]) -> str:
    """Encode a (type_tag, bytes) serde pair to a single storable string."""
    type_tag, data = pair
    return f"{type_tag}:{base64.b64encode(data).decode('ascii')}"


def _decode(value: str) -> tuple[str, bytes]:
    """Decode a stored string back to a (type_tag, bytes) serde pair."""
    type_tag, b64 = value.split(":", 1)
    return type_tag, base64.b64decode(b64)


class SupabaseCheckpointSaver(BaseCheckpointSaver[str]):
    """
    LangGraph checkpointer backed by Supabase (supabase-py async client).

    Required table: conversation_checkpoints
    Required writes table: conversation_checkpoint_writes
    See: scripts/migration_checkpoints.sql
    """

    def __init__(self) -> None:
        super().__init__(serde=JsonPlusSerializer())
        log.info("SupabaseCheckpointSaver initialised")

    # ── Sync stubs (required by base class, not used in async context) ─────────

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        raise NotImplementedError("Use aget_tuple for async operation")

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ):
        raise NotImplementedError("Use alist for async operation")

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        raise NotImplementedError("Use aput for async operation")

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        raise NotImplementedError("Use aput_writes for async operation")

    # ── get_next_version ───────────────────────────────────────────────────────

    def get_next_version(self, current: Optional[str], channel: Any) -> str:
        if current is None:
            return "1"
        try:
            return str(int(current) + 1)
        except (ValueError, TypeError):
            return "1"

    # ── Async read ─────────────────────────────────────────────────────────────

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Load the most recent (or specific) checkpoint for a thread."""
        from db.client import get_supabase

        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)

        client = get_supabase()
        try:
            q = (
                client.table("conversation_checkpoints")
                .select("*")
                .eq("thread_id", thread_id)
                .eq("checkpoint_ns", checkpoint_ns)
            )
            if checkpoint_id:
                q = q.eq("checkpoint_id", checkpoint_id)
            else:
                q = q.order("created_at", desc=True).limit(1)

            result = await q.execute()
            if not result.data:
                return None

            row = result.data[0]

            checkpoint: Checkpoint = self.serde.loads_typed(_decode(row["checkpoint"]))
            meta: CheckpointMetadata = self.serde.loads_typed(_decode(row["metadata"]))

            # Load pending writes for this checkpoint
            writes_result = await (
                client.table("conversation_checkpoint_writes")
                .select("*")
                .eq("thread_id", thread_id)
                .eq("checkpoint_ns", checkpoint_ns)
                .eq("checkpoint_id", row["checkpoint_id"])
                .execute()
            )
            pending_writes: list[PendingWrite] = []
            for wr in (writes_result.data or []):
                try:
                    val = self.serde.loads_typed(_decode(wr["value"]))
                    pending_writes.append((wr["task_id"], wr["channel"], val))
                except Exception as exc:
                    log.warning("checkpoint_write_decode_failed", error=str(exc))

            parent_config: Optional[RunnableConfig] = None
            if row.get("parent_checkpoint_id"):
                parent_config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": row["parent_checkpoint_id"],
                    }
                }

            return CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": row["checkpoint_id"],
                    }
                },
                checkpoint=checkpoint,
                metadata=meta,
                parent_config=parent_config,
                pending_writes=pending_writes,
            )

        except Exception as exc:
            log.error("aget_tuple_failed", thread_id=thread_id, error=str(exc))
            return None

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Yield all checkpoints for a thread, newest first."""
        if not config:
            return

        from db.client import get_supabase

        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        client = get_supabase()

        try:
            q = (
                client.table("conversation_checkpoints")
                .select("*")
                .eq("thread_id", thread_id)
                .eq("checkpoint_ns", checkpoint_ns)
                .order("created_at", desc=True)
            )

            if before:
                before_id = get_checkpoint_id(before)
                if before_id:
                    before_result = await (
                        client.table("conversation_checkpoints")
                        .select("created_at")
                        .eq("checkpoint_id", before_id)
                        .limit(1)
                        .execute()
                    )
                    if before_result.data:
                        q = q.lt("created_at", before_result.data[0]["created_at"])

            if limit:
                q = q.limit(limit)

            result = await q.execute()
            for row in (result.data or []):
                try:
                    checkpoint: Checkpoint = self.serde.loads_typed(_decode(row["checkpoint"]))
                    meta: CheckpointMetadata = self.serde.loads_typed(_decode(row["metadata"]))
                    parent_config = (
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": row["parent_checkpoint_id"],
                            }
                        }
                        if row.get("parent_checkpoint_id")
                        else None
                    )
                    yield CheckpointTuple(
                        config={
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": row["checkpoint_id"],
                            }
                        },
                        checkpoint=checkpoint,
                        metadata=meta,
                        parent_config=parent_config,
                        pending_writes=None,
                    )
                except Exception as exc:
                    log.warning(
                        "alist_row_failed",
                        checkpoint_id=row.get("checkpoint_id"),
                        error=str(exc),
                    )
                    continue

        except Exception as exc:
            log.error("alist_failed", thread_id=thread_id, error=str(exc))

    # ── Async write ────────────────────────────────────────────────────────────

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Upsert a checkpoint to Supabase."""
        from db.client import get_supabase

        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id: str = checkpoint["id"]
        parent_checkpoint_id = get_checkpoint_id(config)

        full_meta = get_checkpoint_metadata(config, metadata)

        row = {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
            "parent_checkpoint_id": parent_checkpoint_id,
            "checkpoint": _encode(self.serde.dumps_typed(checkpoint)),
            "metadata": _encode(self.serde.dumps_typed(full_meta)),
        }

        client = get_supabase()
        try:
            await (
                client.table("conversation_checkpoints")
                .upsert(row, on_conflict="thread_id,checkpoint_ns,checkpoint_id")
                .execute()
            )
            log.debug(
                "checkpoint_saved",
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
            )
        except Exception as exc:
            log.error("aput_failed", thread_id=thread_id, error=str(exc))
            raise

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Persist pending writes (intermediate node outputs before commit)."""
        if not writes:
            return

        from db.client import get_supabase

        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id: str = config["configurable"]["checkpoint_id"]

        client = get_supabase()
        rows = []
        for idx, (channel, value) in enumerate(writes):
            write_idx = WRITES_IDX_MAP.get(channel, idx)
            rows.append({
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "task_path": task_path,
                "idx": write_idx,
                "channel": channel,
                "value": _encode(self.serde.dumps_typed(value)),
            })

        try:
            await (
                client.table("conversation_checkpoint_writes")
                .upsert(
                    rows,
                    on_conflict="thread_id,checkpoint_ns,checkpoint_id,task_id,idx",
                )
                .execute()
            )
        except Exception as exc:
            log.warning("aput_writes_failed", thread_id=thread_id, error=str(exc))


# ── Module-level singleton ─────────────────────────────────────────────────────

_checkpointer: Optional[SupabaseCheckpointSaver] = None


def get_checkpointer() -> SupabaseCheckpointSaver:
    """Return the singleton checkpointer. Created lazily."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = SupabaseCheckpointSaver()
    return _checkpointer
