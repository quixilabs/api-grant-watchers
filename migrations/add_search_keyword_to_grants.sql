-- Add search_keyword column to grants table
ALTER TABLE grants ADD COLUMN IF NOT EXISTS search_keyword TEXT;

-- Add an index on search_keyword for faster searches
CREATE INDEX IF NOT EXISTS idx_grants_search_keyword ON grants(search_keyword);

-- Add comment to explain the purpose of the column
COMMENT ON COLUMN grants.search_keyword IS 'The keyword used in the search that found this grant'; 