-- ═══════════════════════════════════════════════════════════════════════════
-- First tenant seed — run after schema.sql + seed_gurugram.sql
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO tenants (
  id,
  business_name,
  contact_name,
  contact_phone,
  ai_name,
  city,
  working_hours_start,
  working_hours_end,
  plan
) VALUES (
  uuid_generate_v4(),
  'My First PG Business',
  'Admin',
  '+919999999999',
  'Priya',
  'gurugram',
  '09:00',
  '21:00',
  'trial'
);

-- Show the tenant ID — copy this into your .env as TENANT_ID
SELECT id, business_name, ai_name, plan, created_at FROM tenants;
