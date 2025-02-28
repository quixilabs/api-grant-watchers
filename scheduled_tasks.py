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
        from app.utils.supabase import get_supabase_client, update_grant_details
        from app.services.grants_service import fetch_and_save_grants_data, fetch_grant_details
        
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
            "total_details_fetched": 0,
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
                    
                    # If we saved any grants, fetch details for each one
                    if grants_count > 0:
                        # Get the IDs of the grants we just saved
                        saved_grants = []
                        if "results" in result.get("data", {}):
                            # Extract grant IDs from the results
                            for grant_result in result["data"]["results"]:
                                if grant_result.data and len(grant_result.data) > 0:
                                    for grant in grant_result.data:
                                        saved_grants.append(grant.get("id"))
                        
                        # If we couldn't extract IDs from results, query the database
                        if not saved_grants:
                            # Query grants with this keyword that were recently added
                            # Use LIKE operator to match grants where the keyword is part of a comma-separated list
                            grants_query = client.table("grants").select("id").like("search_keyword", f"%{keyword_value}%").order("created_at", desc=True).limit(grants_count).execute()
                            if grants_query.data:
                                saved_grants = [grant.get("id") for grant in grants_query.data]
                        
                        logger.info(f"Fetching details for {len(saved_grants)} grants")
                        
                        # Fetch details for each grant
                        details_fetched = 0
                        for grant_id in saved_grants:
                            try:
                                # Check if we already have details for this grant
                                has_details = client.table("grants").select("details_raw_data").eq("id", grant_id).execute()
                                if has_details.data and len(has_details.data) > 0 and has_details.data[0].get("details_raw_data"):
                                    logger.info(f"Grant {grant_id} already has details, skipping")
                                    continue
                                
                                # Fetch details from Grants.gov API
                                details = await fetch_grant_details(grant_id)
                                
                                if "error" in details:
                                    logger.error(f"Error fetching details for grant {grant_id}: {details['error']}")
                                    continue
                                
                                # Update the grant with details
                                update_result = update_grant_details(grant_id, details)
                                
                                if "error" in update_result:
                                    logger.error(f"Error updating grant {grant_id} with details: {update_result['error']}")
                                else:
                                    details_fetched += 1
                                    logger.info(f"Successfully updated grant {grant_id} with details")
                            except Exception as e:
                                logger.error(f"Error processing details for grant {grant_id}: {str(e)}")
                        
                        results["total_details_fetched"] += details_fetched
                        logger.info(f"Fetched and saved details for {details_fetched} grants")
                    
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