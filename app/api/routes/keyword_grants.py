from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
from app.services.grants_service import fetch_and_save_grants_data
from app.utils.supabase import get_supabase_client

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/check-new-grants", response_model=Dict[str, Any])
async def check_new_grants_for_keywords(
    background_tasks: BackgroundTasks,
    date_range: Optional[str] = "1",  # Default to 1 day
    opp_statuses: Optional[str] = "forecasted|posted",
    rows: Optional[int] = 5000,
    sort_by: Optional[str] = "openDate|desc"
):
    """
    Check for new grants for all keywords in the database since yesterday.
    
    This endpoint:
    1. Retrieves all keywords from the 'keywords' table
    2. For each keyword, checks for new grants in the last day (or specified date_range)
    3. Saves any new grants to the database
    
    Args:
        date_range: Number of days to look back for new grants (default: 1)
        opp_statuses: Opportunity statuses to include (default: "forecasted|posted")
        rows: Maximum number of results to return per keyword (default: 5000)
        sort_by: How to sort the results (default: "openDate|desc")
        
    Returns:
        A summary of the operation
    """
    try:
        # Add the task to the background
        background_tasks.add_task(
            process_keywords_for_new_grants,
            date_range=date_range,
            opp_statuses=opp_statuses,
            rows=rows,
            sort_by=sort_by
        )
        
        return {
            "success": True,
            "message": "Background task started to check for new grants for all keywords",
            "date_range": date_range
        }
    except Exception as e:
        logger.error(f"Error starting background task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting background task: {str(e)}")

@router.get("/stats", response_model=Dict[str, Any])
async def get_keyword_grant_stats(
    days: Optional[int] = 7,  # Default to last 7 days
    organization_id: Optional[str] = None  # Optional filter by organization
):
    """
    Get statistics about grants found for each keyword.
    
    This endpoint:
    1. Retrieves all keywords from the 'keywords' table
    2. For each keyword, counts how many grants were found in the specified time period
    3. Returns a summary of grants per keyword
    
    Args:
        days: Number of days to look back (default: 7)
        organization_id: Optional organization ID to filter keywords by
        
    Returns:
        A summary of grants found per keyword
    """
    try:
        # Calculate the date range
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        logger.info(f"Getting grant statistics for the last {days} days (since {start_date})")
        
        # Get Supabase client
        client = get_supabase_client()
        
        # Get all keywords, optionally filtered by organization
        keywords_query = client.table("keywords").select("*")
        
        if organization_id:
            keywords_query = keywords_query.eq("organization_id", organization_id)
            
        keywords_response = keywords_query.execute()
        
        if not keywords_response.data:
            return {
                "success": True,
                "message": "No keywords found",
                "data": {
                    "keywords": [],
                    "total_keywords": 0,
                    "total_grants": 0
                }
            }
        
        keywords = keywords_response.data
        logger.info(f"Found {len(keywords)} keywords to analyze")
        
        # Prepare the result
        keyword_stats = []
        total_grants = 0
        
        # Process each keyword
        for keyword in keywords:
            keyword_value = keyword.get("keyword", "")
            keyword_id = keyword.get("id", "")
            
            if not keyword_value:
                continue
                
            # Count grants for this keyword in the specified time period
            # Just select all matching records and count them in Python
            grants_query = client.table("grants").select("id").eq("search_keyword", keyword_value)
            
            # Add created_at filter if we have a start date
            if start_date:
                grants_query = grants_query.gte("created_at", start_date)
                
            grants_response = grants_query.execute()
            
            # Get the count of grants
            grants_count = len(grants_response.data) if grants_response.data else 0
            total_grants += grants_count
            
            # Get the last execution date
            last_execution = keyword.get("execution_date", None)
            
            # Add to the stats
            keyword_stats.append({
                "keyword_id": keyword_id,
                "keyword": keyword_value,
                "grants_count": grants_count,
                "last_execution": last_execution
            })
        
        # Sort by grants count (descending)
        keyword_stats.sort(key=lambda x: x["grants_count"], reverse=True)
        
        return {
            "success": True,
            "message": f"Found {total_grants} grants for {len(keyword_stats)} keywords in the last {days} days",
            "data": {
                "keywords": keyword_stats,
                "total_keywords": len(keyword_stats),
                "total_grants": total_grants,
                "days": days,
                "start_date": start_date
            }
        }
    except Exception as e:
        logger.error(f"Error getting keyword grant stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting keyword grant stats: {str(e)}")

async def process_keywords_for_new_grants(
    date_range: str,
    opp_statuses: str,
    rows: int,
    sort_by: str
):
    """
    Process all keywords and check for new grants.
    
    This function runs in the background and:
    1. Retrieves all keywords from the database
    2. For each keyword, checks for new grants
    3. Saves any new grants to the database
    """
    try:
        logger.info(f"Starting to process keywords for new grants (date_range={date_range})")
        
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
                    date_range=date_range,
                    opp_statuses=opp_statuses,
                    rows=rows,
                    sort_by=sort_by,
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
        
    except Exception as e:
        logger.error(f"Error in process_keywords_for_new_grants: {str(e)}")
        raise 