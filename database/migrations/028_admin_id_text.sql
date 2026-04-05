-- Migration: Change admins.id (SERIAL) to admins.admin_id (TEXT)
-- Required for: Issue #28 - Admin auth with independent identity system
--
-- Run this as the database OWNER (not the 'backend' user).
-- All admin tables are empty, so this is safe to run.

-- Step 1: Drop FK constraints on dependent tables
ALTER TABLE admin_access_tokens DROP CONSTRAINT IF EXISTS admin_access_tokens_admin_id_fkey;
ALTER TABLE admin_audit_logs DROP CONSTRAINT IF EXISTS admin_audit_logs_admin_id_fkey;

-- Step 2: Migrate admins table: id SERIAL -> admin_id TEXT
ALTER TABLE admins DROP CONSTRAINT IF EXISTS admins_pkey;
ALTER TABLE admins ADD COLUMN IF NOT EXISTS admin_id TEXT;
ALTER TABLE admins DROP COLUMN IF EXISTS id;
ALTER TABLE admins ADD PRIMARY KEY (admin_id);
ALTER TABLE admins ALTER COLUMN admin_id SET NOT NULL;

-- Step 3: Change admin_access_tokens.admin_id from INTEGER to TEXT
ALTER TABLE admin_access_tokens ALTER COLUMN admin_id TYPE TEXT USING admin_id::TEXT;
ALTER TABLE admin_access_tokens ADD CONSTRAINT admin_access_tokens_admin_id_fkey
    FOREIGN KEY (admin_id) REFERENCES admins(admin_id) ON DELETE CASCADE;

-- Step 4: Change admin_audit_logs.admin_id from INTEGER to TEXT
ALTER TABLE admin_audit_logs ALTER COLUMN admin_id TYPE TEXT USING admin_id::TEXT;
ALTER TABLE admin_audit_logs ADD CONSTRAINT admin_audit_logs_admin_id_fkey
    FOREIGN KEY (admin_id) REFERENCES admins(admin_id);

-- Verify
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'admins' AND column_name = 'admin_id';
