from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from app.models.grants import GrantsSearchParams, GrantsResponse
from app.services.grants_service import fetch_and_save_grants_data
from app.utils.supabase import get_grants_by_keyword

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