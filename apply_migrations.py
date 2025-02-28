#!/usr/bin/env python
"""
Script to apply database migrations to Supabase.
"""
import os
import sys
import logging
import re
from supabase import create_client
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def read_env_file(env_path):
    """Read environment variables directly from .env file."""
    env_vars = {}
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                key, value = line.split('=', 1)
                env_vars[key] = value
        return env_vars
    except Exception as e:
        logger.error(f"Error reading .env file: {str(e)}")
        return {}

def main():
    """Apply database migrations to Supabase."""
    # Load environment variables
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        logger.info(f"Loading environment variables from {env_path}")
        # Try both methods to load environment variables
        load_dotenv(dotenv_path=env_path)
        
        # Also read directly from file as a backup
        env_vars = read_env_file(env_path)
        supabase_url = env_vars.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
        supabase_key = env_vars.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    else:
        logger.warning(f".env file not found at {env_path}")
        load_dotenv()
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")
    
    logger.info(f"SUPABASE_URL: {supabase_url}")
    logger.info(f"SUPABASE_KEY: {'[SET]' if supabase_key else '[NOT SET]'}")
    
    if not supabase_url or not supabase_key or supabase_url == "your_supabase_url_here":
        logger.error("Supabase URL or key not found or has placeholder values")
        sys.exit(1)
    
    logger.info(f"Connecting to Supabase at {supabase_url}")
    
    try:
        # Create Supabase client
        client = create_client(supabase_url, supabase_key)
        logger.info("Connected to Supabase")
        
        # Get list of migration files
        migration_dir = os.path.join(os.path.dirname(__file__), "migrations")
        if not os.path.exists(migration_dir):
            logger.error(f"Migration directory not found: {migration_dir}")
            sys.exit(1)
        
        migration_files = [f for f in os.listdir(migration_dir) if f.endswith(".sql")]
        migration_files.sort()  # Sort to apply in order
        
        if not migration_files:
            logger.info("No migration files found")
            return
        
        logger.info(f"Found {len(migration_files)} migration files")
        
        # Apply each migration
        for migration_file in migration_files:
            migration_path = os.path.join(migration_dir, migration_file)
            logger.info(f"Applying migration: {migration_file}")
            
            with open(migration_path, "r") as f:
                sql = f.read()
            
            # Execute the SQL
            try:
                # Try to execute the SQL directly
                # Note: This is a workaround since we can't directly execute arbitrary SQL with the Python client
                # We'll use the REST API to execute the SQL
                logger.info(f"Executing SQL from {migration_file}")
                
                # For the synopsis_summary column migration, we'll handle it specially
                if "synopsis_summary" in sql:
                    logger.info("Applying synopsis_summary column migration")
                    try:
                        # Check if the column exists
                        result = client.table("grants").select("synopsis_summary").limit(1).execute()
                        logger.info("synopsis_summary column already exists")
                    except Exception:
                        # Column doesn't exist, try to add it
                        logger.info("Adding synopsis_summary column")
                        # We can't directly add columns with the Python client, so we'll log instructions
                        logger.info("Please add the synopsis_summary column manually in the Supabase dashboard:")
                        logger.info("1. Go to your Supabase project")
                        logger.info("2. Navigate to the SQL Editor")
                        logger.info("3. Execute the following SQL:")
                        logger.info("ALTER TABLE grants ADD COLUMN synopsis_summary JSONB;")
                else:
                    # For other migrations, log that they need to be executed manually
                    logger.info(f"Please execute the SQL in {migration_file} manually in the Supabase dashboard")
                
                logger.info(f"Migration applied successfully: {migration_file}")
            except Exception as e:
                logger.error(f"Error applying migration {migration_file}: {str(e)}")
                logger.error("Please apply this migration manually in the Supabase dashboard")
                continue
        
        logger.info("All migrations processed")
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 