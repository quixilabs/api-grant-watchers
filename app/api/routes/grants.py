from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from app.models.grants import GrantsSearchParams, GrantsResponse
from app.services.grants_service import fetch_and_save_grants_data
from app.utils.supabase import get_grants_by_keyword, get_all_grants, update_grant_summary, get_supabase_client
from app.utils.openai_client import generate_grant_summary

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

@router.post("/generate-summaries", response_model=dict)
async def generate_grant_summaries(
    batch_size: int = Query(10, description="Number of grants to process in each batch"),
    offset: int = Query(0, description="Offset for pagination"),
    force_regenerate: bool = Query(False, description="Whether to regenerate summaries for grants that already have them")
):
    """
    Generate summaries for all grants in the database using GPT.
    
    This endpoint will:
    1. Retrieve grants from the database
    2. Generate a summary for each grant using GPT
    3. Update the grant record with the summary
    
    The process is batched to avoid timeouts and rate limits.
    """
    try:
        # Get grants from the database
        grants_result = get_all_grants(limit=batch_size, offset=offset)
        
        if "error" in grants_result:
            raise HTTPException(status_code=500, detail=grants_result["error"])
        
        grants = grants_result["data"]
        
        if not grants:
            return {
                "success": True,
                "message": "No grants found to process",
                "count": 0,
                "processed": []
            }
        
        # Process each grant
        processed_grants = []
        for grant in grants:
            grant_id = grant.get("id")
            
            # Skip grants that already have a summary unless force_regenerate is True
            if not force_regenerate and grant.get("synopsis_summary"):
                processed_grants.append({
                    "grant_id": grant_id,
                    "status": "skipped",
                    "message": "Grant already has a summary"
                })
                continue
            
            # Generate summary
            summary = await generate_grant_summary(grant)
            
            if "error" in summary:
                processed_grants.append({
                    "grant_id": grant_id,
                    "status": "error",
                    "message": summary["error"]
                })
                continue
            
            # Update grant with summary
            update_result = update_grant_summary(grant_id, summary)
            
            if "error" in update_result:
                processed_grants.append({
                    "grant_id": grant_id,
                    "status": "error",
                    "message": update_result["error"]
                })
                continue
            
            processed_grants.append({
                "grant_id": grant_id,
                "status": "success",
                "summary": summary
            })
        
        return {
            "success": True,
            "message": f"Processed {len(processed_grants)} grants",
            "count": len(processed_grants),
            "next_offset": offset + batch_size,
            "processed": processed_grants
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summaries: {str(e)}")

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