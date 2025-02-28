#!/usr/bin/env python
"""
Script to apply database migrations to Supabase.
"""
import os
import sys
import logging
from supabase import create_client
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Apply database migrations to Supabase."""
    # Load environment variables
    load_dotenv()
    
    # Get Supabase credentials
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        logger.error("Supabase URL or key not found in environment variables")
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
                # Use the REST API to execute SQL
                result = client.rpc("exec_sql", {"sql": sql}).execute()
                logger.info(f"Migration applied successfully: {migration_file}")
            except Exception as e:
                logger.error(f"Error applying migration {migration_file}: {str(e)}")
                sys.exit(1)
        
        logger.info("All migrations applied successfully")
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 