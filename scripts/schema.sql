-- ═══════════════════════════════════════════════════════════════════════════
-- PG AI Platform — Database Schema
-- Run this in your Supabase SQL Editor (Dashboard > SQL Editor > New query)
-- ═══════════════════════════════════════════════════════════════════════════

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ── Tenants ───────────────────────────────────────────────────────────────────
CREATE TABLE tenants (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  business_name TEXT NOT NULL,
  contact_name TEXT,
  contact_phone TEXT,
  whatsapp_number TEXT,
  whatsapp_phone_number_id TEXT,
  whatsapp_waba_id TEXT,
  exotel_sid TEXT,
  exotel_token TEXT,
  exotel_app_id TEXT,
  caller_id TEXT,
  vapi_assistant_id TEXT,
  ai_name TEXT DEFAULT 'Priya',
  ai_language TEXT DEFAULT 'hinglish',
  ai_tone TEXT DEFAULT 'friendly',
  city TEXT DEFAULT 'gurugram',
  working_hours_start TIME DEFAULT '09:00',
  working_hours_end TIME DEFAULT '21:00',
  timezone TEXT DEFAULT 'Asia/Kolkata',
  plan TEXT DEFAULT 'trial',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ── Cities ────────────────────────────────────────────────────────────────────
CREATE TABLE cities (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL UNIQUE,
  display_name TEXT,
  state TEXT,
  valid_sectors TEXT[],
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ── Location Aliases ──────────────────────────────────────────────────────────
CREATE TABLE location_aliases (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID REFERENCES tenants(id),
  city TEXT NOT NULL,
  alias TEXT NOT NULL,
  alias_normalized TEXT NOT NULL,
  alias_type TEXT,
  possible_sectors TEXT[] NOT NULL,
  primary_sector TEXT,
  confidence_score NUMERIC DEFAULT 1.0,
  usage_count INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_alias_lookup ON location_aliases(city, alias_normalized);
CREATE INDEX idx_alias_trigram ON location_aliases USING gin(alias_normalized gin_trgm_ops);

CREATE TABLE location_aliases_pending (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  alias TEXT,
  alias_normalized TEXT,
  city TEXT,
  llm_suggested_sectors TEXT[],
  occurrences INT DEFAULT 1,
  added_at TIMESTAMPTZ DEFAULT now()
);

-- ── Properties ────────────────────────────────────────────────────────────────
CREATE TABLE properties (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID REFERENCES tenants(id),
  name TEXT NOT NULL,
  city TEXT DEFAULT 'gurugram',
  sector TEXT NOT NULL,
  address TEXT,
  pg_type TEXT NOT NULL,
  rent_min INT,
  rent_max INT,
  amenities TEXT[],
  total_beds INT DEFAULT 0,
  available_beds INT DEFAULT 0,
  photos TEXT[],
  google_maps_url TEXT,
  featured BOOLEAN DEFAULT false,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_property_search ON properties(tenant_id, sector, pg_type, available_beds);

-- ── Rooms ─────────────────────────────────────────────────────────────────────
CREATE TABLE rooms (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id UUID REFERENCES properties(id),
  room_number TEXT,
  sharing_type TEXT,
  rent_per_bed INT,
  beds_total INT,
  beds_available INT,
  amenities TEXT[],
  active BOOLEAN DEFAULT true
);

-- ── Leads ─────────────────────────────────────────────────────────────────────
CREATE TABLE leads (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID REFERENCES tenants(id),
  name TEXT,
  phone TEXT NOT NULL,
  email TEXT,
  source TEXT,
  source_url TEXT,
  raw_source_data JSONB,
  city TEXT,
  sector TEXT,
  pg_type TEXT,
  budget_min INT,
  budget_max INT,
  move_in_date DATE,
  matched_property_ids UUID[],
  status TEXT DEFAULT 'new',
  retry_count INT DEFAULT 0,
  max_retries INT DEFAULT 3,
  next_action_at TIMESTAMPTZ,
  assigned_to UUID,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_leads_followup ON leads(tenant_id, next_action_at)
  WHERE status NOT IN ('closed_won','closed_lost','dnd');
CREATE INDEX idx_leads_phone ON leads(tenant_id, phone);

-- ── Lead Consents ─────────────────────────────────────────────────────────────
CREATE TABLE lead_consents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID REFERENCES leads(id),
  tenant_id UUID NOT NULL,
  source TEXT NOT NULL,
  source_url TEXT,
  consent_type TEXT[],
  consent_text TEXT,
  consent_method TEXT,
  consent_timestamp TIMESTAMPTZ DEFAULT now(),
  ip_address TEXT,
  user_agent TEXT,
  raw_payload JSONB,
  withdrawn_at TIMESTAMPTZ,
  withdrawal_reason TEXT
);

-- ── Lead Profiles ─────────────────────────────────────────────────────────────
CREATE TABLE lead_profiles (
  lead_id UUID PRIMARY KEY REFERENCES leads(id),
  tenant_id UUID NOT NULL,
  preferred_sectors TEXT[],
  preferred_pg_types TEXT[],
  budget_max INT,
  amenities_required TEXT[],
  move_in_target_date DATE,
  slot_history JSONB DEFAULT '{}',
  total_conversations INT DEFAULT 0,
  total_calls INT DEFAULT 0,
  total_whatsapp_msgs INT DEFAULT 0,
  visits_scheduled INT DEFAULT 0,
  visits_completed INT DEFAULT 0,
  engagement_level TEXT DEFAULT 'new',
  current_stage TEXT,
  last_blocker TEXT,
  conversation_summary TEXT,
  preferences_summary TEXT,
  memory_embedding vector(1536),
  last_interaction_at TIMESTAMPTZ,
  next_action_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ── Lead Interactions ─────────────────────────────────────────────────────────
CREATE TABLE lead_interactions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID REFERENCES leads(id),
  tenant_id UUID,
  channel TEXT,
  direction TEXT,
  interaction_type TEXT,
  outcome TEXT,
  slots_extracted JSONB,
  slots_changed JSONB,
  summary TEXT,
  duration_seconds INT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ── Conversation Sessions ─────────────────────────────────────────────────────
CREATE TABLE conversation_sessions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID REFERENCES leads(id),
  tenant_id UUID,
  channel TEXT,
  current_state TEXT,
  context JSONB,
  started_at TIMESTAMPTZ DEFAULT now(),
  ended_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ── Messages ──────────────────────────────────────────────────────────────────
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID REFERENCES leads(id),
  session_id UUID REFERENCES conversation_sessions(id),
  channel TEXT,
  direction TEXT,
  content TEXT NOT NULL,
  media_url TEXT,
  meta JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_messages_lead ON messages(lead_id, created_at DESC);

-- ── Call Logs ─────────────────────────────────────────────────────────────────
CREATE TABLE call_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID REFERENCES leads(id),
  tenant_id UUID,
  vapi_call_id TEXT,
  exotel_call_id TEXT,
  direction TEXT DEFAULT 'outbound',
  duration_seconds INT,
  status TEXT,
  recording_url TEXT,
  transcript JSONB,
  summary TEXT,
  extracted_slots JSONB,
  avg_latency_ms INT,
  stt_confidence_avg NUMERIC,
  cost_inr NUMERIC,
  started_at TIMESTAMPTZ,
  ended_at TIMESTAMPTZ
);

-- ── Visits ────────────────────────────────────────────────────────────────────
CREATE TABLE visits (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID REFERENCES leads(id),
  property_id UUID REFERENCES properties(id),
  tenant_id UUID,
  visit_date TIMESTAMPTZ,
  status TEXT DEFAULT 'scheduled',
  notes TEXT,
  reminder_sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ── Followup Jobs ─────────────────────────────────────────────────────────────
CREATE TABLE followup_jobs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID REFERENCES leads(id),
  tenant_id UUID,
  job_type TEXT,
  scheduled_at TIMESTAMPTZ NOT NULL,
  status TEXT DEFAULT 'pending',
  attempts INT DEFAULT 0,
  max_attempts INT DEFAULT 3,
  payload JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_jobs_scheduled ON followup_jobs(scheduled_at, status)
  WHERE status = 'pending';

-- ── DND List ──────────────────────────────────────────────────────────────────
CREATE TABLE dnd_list (
  phone TEXT PRIMARY KEY,
  tenant_id UUID,
  reason TEXT,
  source TEXT,
  added_at TIMESTAMPTZ DEFAULT now()
);

-- ── Team Members ──────────────────────────────────────────────────────────────
CREATE TABLE team_members (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID REFERENCES tenants(id),
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  role TEXT DEFAULT 'sales',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ── Prompts (versioned) ───────────────────────────────────────────────────────
CREATE TABLE prompts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID,
  prompt_key TEXT NOT NULL,
  version INT NOT NULL DEFAULT 1,
  template TEXT NOT NULL,
  variables JSONB,
  is_active BOOLEAN DEFAULT true,
  total_uses INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(tenant_id, prompt_key, version)
);

-- ── Usage Events ──────────────────────────────────────────────────────────────
CREATE TABLE usage_events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL,
  event_type TEXT NOT NULL,
  quantity NUMERIC,
  unit TEXT,
  unit_cost_inr NUMERIC,
  total_cost_inr NUMERIC,
  provider TEXT,
  occurred_at TIMESTAMPTZ DEFAULT now()
);

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE visits ENABLE ROW LEVEL SECURITY;
ALTER TABLE followup_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
