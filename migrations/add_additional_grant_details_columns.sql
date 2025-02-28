-- Add additional columns for grant details
ALTER TABLE grants ADD COLUMN IF NOT EXISTS applicant_eligibility_desc TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS funding_activity_categories TEXT[];
ALTER TABLE grants ADD COLUMN IF NOT EXISTS opportunity_category TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS response_date TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS posting_date TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS estimated_funding TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS synopsis_desc TEXT;

-- Add comments to explain the purpose of each column
COMMENT ON COLUMN grants.applicant_eligibility_desc IS 'Detailed description of who is eligible to apply for the grant';
COMMENT ON COLUMN grants.funding_activity_categories IS 'Categories of funding activities';
COMMENT ON COLUMN grants.opportunity_category IS 'Category of the opportunity (e.g., Discretionary)';
COMMENT ON COLUMN grants.response_date IS 'Due date for applications';
COMMENT ON COLUMN grants.posting_date IS 'Date when the opportunity was posted';
COMMENT ON COLUMN grants.estimated_funding IS 'Total estimated funding available';
COMMENT ON COLUMN grants.synopsis_desc IS 'Synopsis description of the grant opportunity'; 