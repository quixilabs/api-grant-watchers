#!/usr/bin/env python
"""
Script to run scheduled tasks for the Grants Webhooks API.
This script can be run via a cron job to automatically check for new grants daily.

Example cron job (runs daily at 2 AM):
0 2 * * * cd /path/to/project && /path/to/venv/bin/python scheduled_tasks.py check_new_grants
"""
import os
import sys
import logging
import asyncio
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduled_tasks.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def check_new_grants():
    """
    Check for new grants for all keywords in the database.
    """
    try:
        logger.info("Starting scheduled task: check_new_grants")
        
        # Import here to avoid circular imports
        from app.utils.supabase import get_supabase_client
        from app.services.grants_service import fetch_and_save_grants_data
        
        # Get Supabase client
        client = get_supabase_client()
        
        # Get all keywords from the database
        response = client.table("keywords").select("*").execute()
        
        if not response.data:
            logger.info("No keywords found in the database")
            return
        
        keywords = response.data
        logger.info(f"Found {len(keywords)} keywords to process")
        
        # Track results
        results = {
            "total_keywords": len(keywords),
            "keywords_processed": 0,
            "total_grants_found": 0,
            "total_grants_saved": 0,
            "errors": []
        }
        
        # Process each keyword
        for keyword in keywords:
            keyword_value = keyword.get("keyword", "")
            if not keyword_value:
                logger.warning(f"Skipping keyword with empty value: {keyword}")
                continue
                
            logger.info(f"Processing keyword: {keyword_value}")
            
            try:
                # Fetch and save grants for this keyword
                result = await fetch_and_save_grants_data(
                    keyword=keyword_value,
                    date_range="1",  # Look for grants in the last day
                    opp_statuses="forecasted|posted",
                    rows=5000,
                    sort_by="openDate|desc",
                    save_to_supabase=True
                )
                
                # Update results
                results["keywords_processed"] += 1
                
                if "error" in result:
                    logger.error(f"Error processing keyword '{keyword_value}': {result['error']}")
                    results["errors"].append({
                        "keyword": keyword_value,
                        "error": result["error"]
                    })
                else:
                    grants_count = result.get("data", {}).get("count", 0)
                    total_found = result.get("data", {}).get("total_found", 0)
                    
                    logger.info(f"Found {total_found} grants for keyword '{keyword_value}', saved {grants_count}")
                    
                    results["total_grants_found"] += total_found
                    results["total_grants_saved"] += grants_count
                    
                    # Update the keyword's execution_date
                    client.table("keywords").update({
                        "execution_date": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }).eq("id", keyword.get("id")).execute()
                    
            except Exception as e:
                logger.error(f"Error processing keyword '{keyword_value}': {str(e)}")
                results["errors"].append({
                    "keyword": keyword_value,
                    "error": str(e)
                })
        
        logger.info(f"Completed processing keywords. Results: {results}")
        
        # Save the run results to a new table if needed
        # client.table("keyword_run_results").insert(results).execute()
        
        return results
    
    except Exception as e:
        logger.error(f"Error in check_new_grants: {str(e)}")
        raise

def main():
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(description="Run scheduled tasks for the Grants Webhooks API")
    parser.add_argument("task", choices=["check_new_grants"], help="The task to run")
    args = parser.parse_args()
    
    if args.task == "check_new_grants":
        asyncio.run(check_new_grants())
    else:
        logger.error(f"Unknown task: {args.task}")
        sys.exit(1)

if __name__ == "__main__":
    main() 