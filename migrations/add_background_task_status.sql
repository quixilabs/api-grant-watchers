-- Create background_task_status table
CREATE TABLE IF NOT EXISTS background_task_status (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    total_items INTEGER NOT NULL,
    processed_items INTEGER NOT NULL DEFAULT 0,
    failed_items INTEGER NOT NULL DEFAULT 0,
    current_item_id VARCHAR(255),
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add index for faster status lookups
CREATE INDEX IF NOT EXISTS idx_background_task_status_task_type ON background_task_status(task_type);
CREATE INDEX IF NOT EXISTS idx_background_task_status_status ON background_task_status(status); 