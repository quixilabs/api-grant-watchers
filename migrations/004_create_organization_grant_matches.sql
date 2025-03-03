-- Create organization_grant_matches table
CREATE TABLE IF NOT EXISTS organization_grant_matches (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    organization_id UUID REFERENCES organizations(id),
    grant_id TEXT REFERENCES grants(id),
    match_score FLOAT,
    match_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    UNIQUE(organization_id, grant_id)
);

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_org_grant_org_id ON organization_grant_matches(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_grant_grant_id ON organization_grant_matches(grant_id); 