-- Add summary column to organizations table if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'organizations'
        AND column_name = 'summary'
    ) THEN
        ALTER TABLE organizations ADD COLUMN summary JSONB;
    END IF;
END
$$; 