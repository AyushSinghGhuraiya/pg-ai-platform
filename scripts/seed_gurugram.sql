-- ═══════════════════════════════════════════════════════════════════════════
-- Gurugram city + location alias seed data
-- Run AFTER schema.sql in Supabase SQL Editor
-- ═══════════════════════════════════════════════════════════════════════════

-- Insert Gurugram city
INSERT INTO cities (name, display_name, state, valid_sectors) VALUES (
  'gurugram',
  'Gurugram',
  'Haryana',
  ARRAY[
    '1','2','3','4','5','6','7','8','9','10',
    '11','12','13','14','15','17','18','19','20',
    '21','22','23','24','25','26','27','28','29',
    '31','32','33','34','35','36','37','38','39','40',
    '41','42','43','44','45','46','47','48','49','50',
    '51','52','53','54','55','56','57','58','59','60',
    '61','62','63','64','65','66','67','68','69','70',
    '71','72','73','74','75','76','77','78','79','80',
    '81','82','83','84','85','86','87','88','89','90',
    '91','92','93','94','95'
  ]
) ON CONFLICT (name) DO NOTHING;

-- Insert location aliases (Gurugram landmarks → sector mappings)
INSERT INTO location_aliases (city, alias, alias_normalized, possible_sectors, primary_sector, alias_type, confidence_score) VALUES
  -- ── Metro Stations ──────────────────────────────────────────────────────────
  ('gurugram', 'Huda City Centre Metro', 'hudacitycentremetro', ARRAY['44','45','46'], '44', 'metro', 0.95),
  ('gurugram', 'HUDA City', 'hudacity', ARRAY['44','45','46'], '44', 'metro', 0.95),
  ('gurugram', 'Huda City Centre', 'hudacitycentre', ARRAY['44','45','46'], '44', 'metro', 0.95),
  ('gurugram', 'IFFCO Chowk Metro', 'iffcochowkmetro', ARRAY['17','18','21'], '17', 'metro', 0.95),
  ('gurugram', 'IFFCO Chowk', 'iffcochowk', ARRAY['17','18','21'], '17', 'metro', 0.95),
  ('gurugram', 'MG Road Metro', 'mgroadmetro', ARRAY['28','25','24'], '28', 'metro', 0.95),
  ('gurugram', 'MG Road', 'mgroad', ARRAY['28','25','24'], '28', 'metro', 0.95),
  ('gurugram', 'Sikanderpur Metro', 'sikanderpurmetro', ARRAY['25','26'], '26', 'metro', 0.95),
  ('gurugram', 'Sikanderpur', 'sikanderpur', ARRAY['25','26'], '26', 'metro', 0.95),
  ('gurugram', 'Guru Dronacharya Metro', 'gurudronacharyametro', ARRAY['23','22'], '23', 'metro', 0.90),
  ('gurugram', 'Rapid Metro Cyber City', 'rapidmetrocybercity', ARRAY['24'], '24', 'metro', 0.95),
  ('gurugram', 'Phase 1 Metro', 'phase1metro', ARRAY['26'], '26', 'metro', 0.90),
  ('gurugram', 'Phase 2 Metro', 'phase2metro', ARRAY['25'], '25', 'metro', 0.90),
  ('gurugram', 'Phase 3 Metro', 'phase3metro', ARRAY['24'], '24', 'metro', 0.90),

  -- ── Office Hubs ─────────────────────────────────────────────────────────────
  ('gurugram', 'Cyber Hub', 'cyberhub', ARRAY['24'], '24', 'office', 0.95),
  ('gurugram', 'Cyber City', 'cybercity', ARRAY['24','25'], '24', 'office', 0.95),
  ('gurugram', 'DLF Cyber City', 'dlfcybercity', ARRAY['24','25'], '24', 'office', 0.95),
  ('gurugram', 'Udyog Vihar', 'udyogvihar', ARRAY['18','19','20'], '18', 'office', 0.90),
  ('gurugram', 'Golf Course Road', 'golfcourseroad', ARRAY['42','43','53','54'], '42', 'office', 0.85),
  ('gurugram', 'Golf Course Extension', 'golfcourseextension', ARRAY['65','66','67'], '66', 'office', 0.85),
  ('gurugram', 'Vatika City', 'vatikacity', ARRAY['49','50'], '49', 'office', 0.80),
  ('gurugram', 'Global Foyer', 'globalfoyer', ARRAY['43'], '43', 'office', 0.85),

  -- ── DLF Phases ──────────────────────────────────────────────────────────────
  ('gurugram', 'DLF Phase 1', 'dlfphase1', ARRAY['26','27'], '26', 'colloquial', 0.90),
  ('gurugram', 'DLF Phase 2', 'dlfphase2', ARRAY['25'], '25', 'colloquial', 0.90),
  ('gurugram', 'DLF Phase 3', 'dlfphase3', ARRAY['24'], '24', 'colloquial', 0.90),
  ('gurugram', 'DLF Phase 4', 'dlfphase4', ARRAY['28'], '28', 'colloquial', 0.90),
  ('gurugram', 'DLF Phase 5', 'dlfphase5', ARRAY['43'], '43', 'colloquial', 0.90),

  -- ── Sushant Lok ─────────────────────────────────────────────────────────────
  ('gurugram', 'Sushant Lok 1', 'sushantlok1', ARRAY['43'], '43', 'colloquial', 0.85),
  ('gurugram', 'Sushant Lok 2', 'sushantlok2', ARRAY['55','56'], '55', 'colloquial', 0.85),
  ('gurugram', 'Sushant Lok 3', 'sushantlok3', ARRAY['57'], '57', 'colloquial', 0.85),

  -- ── South City ──────────────────────────────────────────────────────────────
  ('gurugram', 'South City 1', 'southcity1', ARRAY['40','41'], '41', 'colloquial', 0.85),
  ('gurugram', 'South City 2', 'southcity2', ARRAY['49','50'], '49', 'colloquial', 0.85),

  -- ── Markets / Malls ─────────────────────────────────────────────────────────
  ('gurugram', 'Galleria Market', 'galleriamarket', ARRAY['28'], '28', 'market', 0.90),
  ('gurugram', 'MGF Metropolitan Mall', 'mgfmetropolitanmall', ARRAY['28'], '28', 'market', 0.90),
  ('gurugram', 'Ambience Mall', 'ambiencemall', ARRAY['24'], '24', 'market', 0.90),
  ('gurugram', 'Sahara Mall', 'saharamall', ARRAY['29'], '29', 'market', 0.85),
  ('gurugram', 'Ardee Mall', 'ardeemall', ARRAY['12'], '12', 'market', 0.85),
  ('gurugram', 'Omaxe City Centre', 'omaxecitycentre', ARRAY['49'], '49', 'market', 0.80),

  -- ── Roads / Areas ────────────────────────────────────────────────────────────
  ('gurugram', 'Sohna Road', 'sohnaroad', ARRAY['47','48','49'], '48', 'landmark', 0.85),
  ('gurugram', 'NH8', 'nh8', ARRAY['17','18','19','20','21','22'], '18', 'landmark', 0.80),
  ('gurugram', 'NH 48', 'nh48', ARRAY['17','18','19','20','21','22'], '18', 'landmark', 0.80),
  ('gurugram', 'Old Gurgaon', 'oldgurgaon', ARRAY['4','5','6','7','9','10'], '5', 'colloquial', 0.80),
  ('gurugram', 'New Gurgaon', 'newgurgaon', ARRAY['80','81','82','83','84'], '83', 'colloquial', 0.80),
  ('gurugram', 'Sector 14', 'sector14oldarea', ARRAY['14'], '14', 'colloquial', 0.85),
  ('gurugram', 'Palam Vihar', 'palamvihar', ARRAY['2','3','23'], '2', 'colloquial', 0.85),
  ('gurugram', 'Sheetla Mata Road', 'sheetlamataroad', ARRAY['14','15'], '14', 'landmark', 0.80);

-- Verify the count
SELECT COUNT(*) AS alias_count FROM location_aliases WHERE city = 'gurugram';
