-- 001_initial_schema.sql
-- Run this in Supabase SQL Editor to set up the database

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Users table (auth) — must be created before profiles due to FK
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    auth_provider VARCHAR(50) DEFAULT 'magic_link',
    is_active BOOLEAN DEFAULT TRUE,
    plan_tier VARCHAR(20) DEFAULT 'free',
    export_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

-- Profiles table (Companies House officers)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL DEFAULT 'companies_house',
    source_id VARCHAR(100) UNIQUE,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(255),
    company_name VARCHAR(255),
    company_number VARCHAR(20),
    nationality VARCHAR(100),
    date_of_birth DATE,
    country_of_residence VARCHAR(100),
    address_line_1 VARCHAR(255),
    address_line_2 VARCHAR(255),
    locality VARCHAR(100),
    region VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),
    occupation VARCHAR(255),
    appointed_on DATE,
    resigned_on DATE,
    is_active BOOLEAN DEFAULT TRUE,
    tags TEXT[],
    segment VARCHAR(50),
    origin VARCHAR(10),
    embedding VECTOR(768),
    claimed_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for profiles
CREATE INDEX IF NOT EXISTS idx_profiles_name ON profiles USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_profiles_segment ON profiles(segment);
CREATE INDEX IF NOT EXISTS idx_profiles_country ON profiles(country_of_residence);
CREATE INDEX IF NOT EXISTS idx_profiles_origin ON profiles(origin);
CREATE INDEX IF NOT EXISTS idx_profiles_is_active ON profiles(is_active);
CREATE INDEX IF NOT EXISTS idx_profiles_source_id ON profiles(source_id);

-- Orgs table (Companies House companies)
CREATE TABLE IF NOT EXISTS orgs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL DEFAULT 'companies_house',
    source_id VARCHAR(20) UNIQUE,
    name VARCHAR(255) NOT NULL,
    company_number VARCHAR(20),
    status VARCHAR(50),
    company_type VARCHAR(50),
    sic_codes TEXT[],
    registered_address VARCHAR(500),
    locality VARCHAR(100),
    region VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),
    incorporation_date TIMESTAMP,
    org_type VARCHAR(50),
    tags TEXT[],
    origin VARCHAR(10),
    profile_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for orgs
CREATE INDEX IF NOT EXISTS idx_orgs_name ON orgs USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_orgs_type ON orgs(org_type);
CREATE INDEX IF NOT EXISTS idx_orgs_country ON orgs(country);

-- Search history table (usage tracking)
CREATE TABLE IF NOT EXISTS search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    query TEXT,
    filters JSONB,
    result_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Exports table (usage metering)
CREATE TABLE IF NOT EXISTS exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    export_type VARCHAR(20) DEFAULT 'csv',
    record_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE orgs ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE exports ENABLE ROW LEVEL SECURITY;

-- RLS policies: authenticated users can read everything, write only own data
CREATE POLICY "Profiles are readable by authenticated users" ON profiles
    FOR SELECT TO authenticated USING (true);

CREATE POLICY "Orgs are readable by authenticated users" ON orgs
    FOR SELECT TO authenticated USING (true);

-- Updated_at triggers
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER set_orgs_updated_at
    BEFORE UPDATE ON orgs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
