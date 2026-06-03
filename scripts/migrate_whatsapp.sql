-- ═══════════════════════════════════════════════════════════════════════════
-- Migration: WhatsApp integration columns
-- Run in: Supabase Dashboard → SQL Editor → New query → Run
-- ═══════════════════════════════════════════════════════════════════════════

-- ── leads: add WhatsApp consent fields ───────────────────────────────────────
ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS whatsapp_consent BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS whatsapp_consent_source TEXT;

-- ── messages: rebuild for WhatsApp (original table was too minimal) ───────────
ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id),
  ADD COLUMN IF NOT EXISTS whatsapp_message_id TEXT,
  ADD COLUMN IF NOT EXISTS direction TEXT,
  ADD COLUMN IF NOT EXISTS message_type TEXT DEFAULT 'text',
  ADD COLUMN IF NOT EXISTS from_phone TEXT,
  ADD COLUMN IF NOT EXISTS to_phone TEXT,
  ADD COLUMN IF NOT EXISTS raw_payload JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS media_id TEXT,
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'received',
  ADD COLUMN IF NOT EXISTS template_name TEXT;

-- Make content nullable (inbound media messages may have no text body)
ALTER TABLE messages ALTER COLUMN content DROP NOT NULL;

-- Index for idempotency check and per-lead queries
CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_wa_id ON messages(whatsapp_message_id)
  WHERE whatsapp_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_messages_tenant_lead ON messages(tenant_id, lead_id, created_at DESC);
