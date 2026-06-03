-- ═══════════════════════════════════════════════════════════════════════════
-- Migration: LangGraph checkpoint tables
-- Run in: Supabase Dashboard → SQL Editor → New query → Run
-- ═══════════════════════════════════════════════════════════════════════════

-- ── Main checkpoints table ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversation_checkpoints (
  thread_id           TEXT    NOT NULL,
  checkpoint_ns       TEXT    NOT NULL DEFAULT '',
  checkpoint_id       TEXT    NOT NULL,
  parent_checkpoint_id TEXT,

  -- Serialised state (type_tag:base64 format)
  checkpoint          TEXT    NOT NULL,
  metadata            TEXT    NOT NULL DEFAULT '',

  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

  PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_ns_time
  ON conversation_checkpoints(thread_id, checkpoint_ns, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_checkpoints_parent
  ON conversation_checkpoints(parent_checkpoint_id)
  WHERE parent_checkpoint_id IS NOT NULL;

-- ── Pending writes table (intermediate node outputs) ──────────────────────────
CREATE TABLE IF NOT EXISTS conversation_checkpoint_writes (
  thread_id       TEXT NOT NULL,
  checkpoint_ns   TEXT NOT NULL DEFAULT '',
  checkpoint_id   TEXT NOT NULL,
  task_id         TEXT NOT NULL,
  task_path       TEXT NOT NULL DEFAULT '',
  idx             INT  NOT NULL,
  channel         TEXT NOT NULL,
  value           TEXT NOT NULL,

  PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

CREATE INDEX IF NOT EXISTS idx_writes_checkpoint
  ON conversation_checkpoint_writes(thread_id, checkpoint_ns, checkpoint_id);

-- ── RLS ───────────────────────────────────────────────────────────────────────
ALTER TABLE conversation_checkpoints       ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_checkpoint_writes ENABLE ROW LEVEL SECURITY;

-- Service role has full access (backend uses service key, bypasses RLS).
-- Add tenant-scoped policies here when multi-tenant auth is added.
