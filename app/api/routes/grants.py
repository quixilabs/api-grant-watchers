from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
import logging

from app.models.grants import GrantsSearchParams, GrantsResponse
from app.services.grants_service import fetch_and_save_grants_data, fetch_grant_details
from app.utils.supabase import get_grants_by_keyword, get_all_grants, update_grant_summary, get_supabase_client, clean_duplicate_keywords, update_grant_details
from app.utils.deepseek_client import generate_grant_summary
from app.utils.background_task_manager import task_manager

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/search", response_model=GrantsResponse)
async def search_grants(params: GrantsSearchParams, save_to_supabase: bool = True):
    """
    Search for grants using the Grants.gov API and save the results to Supabase.
    """
    result = await fetch_and_save_grants_data(
        keyword=params.keyword,
        date_range=params.date_range,
        opp_statuses=params.opp_statuses,
        rows=params.rows,
        sort_by=params.sort_by,
        save_to_supabase=save_to_supabase
    )
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    # Fetch details for each grant that doesn't have details stored in the database
    if save_to_supabase and result.get("success", False):
        client = get_supabase_client()
        details_fetched = 0
        
        # Extract grant IDs from the result
        saved_grants = []
        if "data" in result and "results" in result["data"]:
            # Extract grant IDs from the results
            for grant_result in result["data"]["results"]:
                # Handle different result formats
                if hasattr(grant_result, 'data') and grant_result.data and len(grant_result.data) > 0:
                    for grant in grant_result.data:
                        saved_grants.append(grant.get("id"))
                elif isinstance(grant_result, dict) and "id" in grant_result:
                    saved_grants.append(grant_result["id"])
        
        # If we couldn't extract IDs from results, use the opportunities
        if not saved_grants and "opportunities" in result:
            for opportunity in result["opportunities"]:
                if isinstance(opportunity, dict) and "id" in opportunity:
                    saved_grants.append(opportunity["id"])
                elif hasattr(opportunity, "id"):
                    saved_grants.append(opportunity.id)
        
        logger.info(f"Fetching details for {len(saved_grants)} grants")
        
        # Fetch details for each grant
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
        
        logger.info(f"Fetched and saved details for {details_fetched} grants")
        
        # Add details fetched count to the result
        result["details_fetched"] = details_fetched
    
    return result

@router.get("/by-keyword/{keyword}", response_model=dict)
async def get_grants_for_keyword(
    keyword: str,
    limit: int = Query(100, description="Maximum number of results to return"),
    offset: int = Query(0, description="Offset for pagination")
):
    """
    Retrieve grants that match a specific keyword.
    
    This endpoint returns grants that have the specified keyword in their search_keyword field,
    which may be a comma-separated list of keywords.
    """
    result = get_grants_by_keyword(keyword, limit, offset)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result

@router.post("/generate-summaries", response_model=Dict[str, Any])
async def generate_grant_summaries(
    force_regenerate: bool = Query(False, description="Whether to regenerate summaries for grants that already have them")
):
    """
    Start a background task to generate summaries for all grants in the database using DeepSeek AI.
    
    This endpoint will:
    1. Create a background task status record
    2. Start processing grants in the background
    3. Return the task ID for status tracking
    
    The process will:
    - Skip grants that already have summaries (unless force_regenerate is True)
    - Wait 2 minutes between each summary generation
    - Update progress in real-time
    """
    try:
        # Start the background task
        task_id = await task_manager.start_grant_summary_task()
        
        return {
            "success": True,
            "message": "Background task started successfully",
            "task_id": task_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting background task: {str(e)}")

@router.get("/task-status/{task_id}", response_model=Dict[str, Any])
async def get_task_status(task_id: str):
    """
    Get the current status of a background task.
    
    Args:
        task_id: The ID of the task to check
        
    Returns:
        The current status and progress of the task
    """
    try:
        status = await task_manager.get_task_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail="Task not found")
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting task status: {str(e)}")

@router.get("/active-tasks", response_model=Dict[str, Dict[str, Any]])
async def get_active_tasks():
    """
    Get information about all currently running background tasks.
    
    Returns:
        A dictionary of task IDs to their current status
    """
    try:
        return task_manager.get_active_tasks()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting active tasks: {str(e)}")

@router.post("/stop-task/{task_id}", response_model=Dict[str, Any])
async def stop_task(task_id: str):
    """
    Stop a specific background task.
    
    Args:
        task_id: The ID of the task to stop
        
    Returns:
        Confirmation of the task being stopped
    """
    try:
        await task_manager.stop_task(task_id)
        return {
            "success": True,
            "message": f"Task {task_id} stopped successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping task: {str(e)}")

@router.post("/generate-summary/{grant_id}", response_model=dict)
async def generate_single_grant_summary(
    grant_id: str,
    force_regenerate: bool = Query(False, description="Whether to regenerate the summary if it already exists")
):
    """
    Generate a summary for a specific grant using DeepSeek AI.
    
    This endpoint will:
    1. Retrieve the grant from the database
    2. Generate a summary using DeepSeek AI
    3. Update the grant record with the summary
    """
    try:
        # Get the grant from the database
        client = get_supabase_client()
        result = client.table("grants").select("*").eq("id", grant_id).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail=f"Grant with ID {grant_id} not found")
        
        grant = result.data[0]
        
        # Check if the grant already has a summary
        if not force_regenerate and grant.get("synopsis_summary"):
            return {
                "success": True,
                "message": "Grant already has a summary",
                "grant_id": grant_id,
                "summary": grant.get("synopsis_summary")
            }
        
        # Generate summary
        summary = await generate_grant_summary(grant)
        
        if "error" in summary:
            raise HTTPException(status_code=500, detail=summary["error"])
        
        # Update grant with summary
        update_result = update_grant_summary(grant_id, summary)
        
        if "error" in update_result:
            raise HTTPException(status_code=500, detail=update_result["error"])
        
        return {
            "success": True,
            "message": "Successfully generated summary",
            "grant_id": grant_id,
            "summary": summary
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")

@router.post("/clean-duplicate-keywords")
async def clean_duplicate_keywords_endpoint():
    """
    Clean up duplicate keywords in the search_keyword field of all grants.
    This endpoint removes duplicate keywords (case-insensitive) from all grants.
    
    Returns:
        dict: Summary of the cleanup operation
    """
    try:
        logger.info("Starting cleanup of duplicate keywords in grants table")
        
        result = clean_duplicate_keywords()
        
        if result.get("success", False):
            return {
                "success": True,
                "message": "Successfully cleaned up duplicate keywords",
                "grants_processed": result.get("grants_processed", 0),
                "grants_updated": result.get("grants_updated", 0)
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to clean up duplicate keywords: {result.get('error', 'Unknown error')}"
            )
    except Exception as e:
        logger.error(f"Error cleaning up duplicate keywords: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error cleaning up duplicate keywords: {str(e)}"
        ) 