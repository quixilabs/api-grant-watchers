from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
from pydantic import BaseModel
from app.services.grants_service import fetch_and_save_grants_data, fetch_grant_details
from app.utils.supabase import get_supabase_client, update_grant_details

router = APIRouter()
logger = logging.getLogger(__name__)

class CheckNewGrantsRequest(BaseModel):
    date_range: Optional[str] = "1"  # Default to 1 day
    opp_statuses: Optional[str] = "forecasted|posted"
    rows: Optional[int] = 5000
    sort_by: Optional[str] = "openDate|desc"
    keywords: Optional[List[str]] = None

@router.post("/check-new-grants", response_model=Dict[str, Any])
async def check_new_grants_for_keywords(
    request: CheckNewGrantsRequest,
    background_tasks: BackgroundTasks,
):
    """
    Check for new grants for specified keywords or all keywords in the database.
    
    This endpoint:
    1. Uses provided keywords or retrieves all keywords from the 'keywords' table
    2. For each keyword, checks for new grants in the specified date range
    3. Saves any new grants to the database
    
    Args:
        request: Request body containing:
            - date_range: Number of days to look back for new grants (default: 1)
            - opp_statuses: Opportunity statuses to include (default: "forecasted|posted")
            - rows: Maximum number of results to return per keyword (default: 5000)
            - sort_by: How to sort the results (default: "openDate|desc")
            - keywords: Optional list of keywords to check for
        
    Returns:
        A summary of the operation
    """
    try:
        # Add the task to the background
        background_tasks.add_task(
            process_keywords_for_new_grants,
            date_range=request.date_range,
            opp_statuses=request.opp_statuses,
            rows=request.rows,
            sort_by=request.sort_by,
            keywords=request.keywords
        )
        
        return {
            "success": True,
            "message": "Background task started to check for new grants for keywords",
            "date_range": request.date_range,
            "keywords_provided": request.keywords is not None
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
    sort_by: str,
    keywords: List[str],
):
    """
    Process keywords and check for new grants.
    
    This function runs in the background and:
    1. Uses provided keywords or retrieves all keywords from the database
    2. For each keyword, checks for new grants
    3. Saves any new grants to the database
    4. Fetches detailed information for each new grant
    """
    try:
        logger.info(f"Starting to process keywords for new grants (date_range={date_range})")
        
        # Get Supabase client
        client = get_supabase_client()
        
        # If keywords are provided, use them directly
        if keywords:
            logger.info(f"Using provided keywords: {keywords}")
            keywords_to_process = [{"keyword": keyword} for keyword in keywords]
        else:
            # Get all keywords from the database
            response = client.table("keywords").select("*").execute()
            
            if not response.data:
                logger.info("No keywords found in the database")
                return
            
            keywords_to_process = response.data
            logger.info(f"Found {len(keywords_to_process)} keywords to process")
        
        # Track results
        results = {
            "total_keywords": len(keywords_to_process),
            "keywords_processed": 0,
            "total_grants_found": 0,
            "total_grants_saved": 0,
            "total_details_fetched": 0,
            "errors": []
        }
        
        # Process each keyword
        for keyword in keywords_to_process:
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
                                update_result = await update_grant_details(grant_id, details)
                                
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
                    if keyword.get("id"):
                        client.table("keywords").update({
                            "execution_date": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat()
                        }).eq("id", keyword.get("id")).execute()
                        logger.info(f"Updated execution date for keyword ID: {keyword.get('id')}")
                    else:
                        logger.info("Skipping execution date update for provided keyword without ID")
                    
            except Exception as e:
                logger.error(f"Error processing keyword '{keyword_value}': {str(e)}")
                results["errors"].append({
                    "keyword": keyword_value,
                    "error": str(e)
                })
        
        logger.info(f"Completed processing keywords. Results: {results}")
        return results
        
        # Save the run results to a new table if needed
        # client.table("keyword_run_results").insert(results).execute()
        
    except Exception as e:
        logger.error(f"Error in process_keywords_for_new_grants: {str(e)}")
        raise 