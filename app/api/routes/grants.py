from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any

from app.models.grants import GrantsSearchParams, GrantsResponse
from app.services.grants_service import fetch_and_save_grants_data
from app.utils.supabase import get_grants_by_keyword, get_all_grants, update_grant_summary, get_supabase_client
from app.utils.ollama_client import generate_grant_summary
from app.utils.background_task_manager import task_manager

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
    
    return result

@router.get("/search", response_model=GrantsResponse)
async def search_grants_get(
    keyword: str = Query("", description="Keyword to search for"),
    date_range: str = Query("30", description="Date range to search in (e.g., '30' for 30 days)"),
    opp_statuses: str = Query("forecasted|posted", description="Opportunity statuses to include (e.g., 'forecasted|posted')"),
    rows: int = Query(5000, description="Number of rows to return"),
    sort_by: str = Query("openDate|desc", description="Sort order (e.g., 'openDate|desc')"),
    save_to_supabase: bool = Query(True, description="Whether to save the data to Supabase")
):
    """
    Search for grants using the Grants.gov API and save the results to Supabase.
    This endpoint supports GET requests with query parameters.
    """
    result = await fetch_and_save_grants_data(
        keyword=keyword,
        date_range=date_range,
        opp_statuses=opp_statuses,
        rows=rows,
        sort_by=sort_by,
        save_to_supabase=save_to_supabase
    )
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
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
    Start a background task to generate summaries for all grants in the database.
    
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
    Generate a summary for a specific grant using GPT.
    
    This endpoint will:
    1. Retrieve the grant from the database
    2. Generate a summary using GPT
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