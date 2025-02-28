-- Migration: Add synopsis_summary column to grants table
-- This column will store the AI-generated summary of the grant in a structured format

-- Check if the column already exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'grants'
        AND column_name = 'synopsis_summary'
    ) THEN
        -- Add the column if it doesn't exist
        ALTER TABLE grants
        ADD COLUMN synopsis_summary JSONB;
        
        RAISE NOTICE 'Added synopsis_summary column to grants table';
    ELSE
        RAISE NOTICE 'synopsis_summary column already exists in grants table';
    END IF;
END $$; 