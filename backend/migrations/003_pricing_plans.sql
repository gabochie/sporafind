-- 003_pricing_plans.sql
-- Run this in Supabase SQL Editor after 002_activity_log.sql

CREATE TABLE IF NOT EXISTS pricing_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    price_monthly FLOAT DEFAULT 0,
    price_yearly FLOAT DEFAULT 0,
    description TEXT DEFAULT '',
    features JSONB DEFAULT '[]',
    highlighted BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed data
INSERT INTO pricing_plans (name, display_name, price_monthly, price_yearly, description, features, highlighted, sort_order)
VALUES
  ('free', 'Free', 0, 0, 'Get started with basic diaspora search and discovery.',
   '["Browse 50 profiles/month", "Basic search filters", "Grid & list view", "Community insights"]',
   FALSE, 1),
  ('pro', 'Pro', 29, 290, 'Unlock advanced search, exports, and AI-powered insights.',
   '["Unlimited profile browsing", "Advanced multi-field search", "CSV export up to 1000 records", "AI segment enrichment", "Priority support"]',
   TRUE, 2),
  ('enterprise', 'Enterprise', 99, 990, 'Full platform access with custom integrations and dedicated support.',
   '["Everything in Pro", "Unlimited CSV exports", "API access & webhooks", "Custom integrations", "Dedicated account manager", "SLA guarantee"]',
   FALSE, 3)
ON CONFLICT (name) DO NOTHING;
