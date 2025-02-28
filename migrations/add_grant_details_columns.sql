-- Add columns for grant details
ALTER TABLE grants ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS category_explanation TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS award_ceiling TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS award_floor TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS expected_awards TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS funding_instrument_type TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS eligibility_categories TEXT[];
ALTER TABLE grants ADD COLUMN IF NOT EXISTS cost_sharing TEXT;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS additional_information JSONB;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS agency_contacts JSONB;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS details_raw_data JSONB;

-- Add comments to explain the purpose of each column
COMMENT ON COLUMN grants.description IS 'Detailed description of the grant opportunity';
COMMENT ON COLUMN grants.category_explanation IS 'Explanation of the grant category';
COMMENT ON COLUMN grants.award_ceiling IS 'Maximum award amount';
COMMENT ON COLUMN grants.award_floor IS 'Minimum award amount';
COMMENT ON COLUMN grants.expected_awards IS 'Expected number of awards';
COMMENT ON COLUMN grants.funding_instrument_type IS 'Type of funding instrument';
COMMENT ON COLUMN grants.eligibility_categories IS 'Categories of eligible applicants';
COMMENT ON COLUMN grants.cost_sharing IS 'Cost sharing or matching requirements';
COMMENT ON COLUMN grants.additional_information IS 'Additional information about the grant';
COMMENT ON COLUMN grants.agency_contacts IS 'Contact information for the agency';
COMMENT ON COLUMN grants.details_raw_data IS 'Raw data from the details API response'; 