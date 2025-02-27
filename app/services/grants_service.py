import httpx
import json
from app.core.config import settings
from app.utils.supabase import save_grants_data

async def fetch_grants_data(keyword="", date_range="30", opp_statuses="forecasted|posted", rows=5000, sort_by="openDate|desc"):
    """
    Fetch grants data from the Grants.gov API.
    
    Args:
        keyword (str): Keyword to search for
        date_range (str): Date range to search in (e.g., "30" for 30 days)
        opp_statuses (str): Opportunity statuses to include (e.g., "forecasted|posted")
        rows (int): Number of rows to return
        sort_by (str): Sort order (e.g., "openDate|desc")
        
    Returns:
        dict: The response from the Grants.gov API
    """
    url = settings.GRANTS_API_URL
    
    payload = {
        "keyword": keyword,
        "cfda": None,
        "agencies": None,
        "sortBy": sort_by,
        "rows": rows,
        "eligibilities": None,
        "fundingCategories": None,
        "fundingInstruments": None,
        "dateRange": date_range,
        "oppStatuses": opp_statuses
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error occurred: {e}"}
    except httpx.RequestError as e:
        return {"error": f"Request error occurred: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

async def fetch_and_save_grants_data(keyword="", date_range="30", opp_statuses="forecasted|posted", rows=5000, sort_by="openDate|desc", save_to_supabase=True):
    """
    Fetch grants data from the Grants.gov API and save it to Supabase.
    
    Args:
        keyword (str): Keyword to search for
        date_range (str): Date range to search in (e.g., "30" for 30 days)
        opp_statuses (str): Opportunity statuses to include (e.g., "forecasted|posted")
        rows (int): Number of rows to return
        sort_by (str): Sort order (e.g., "openDate|desc")
        save_to_supabase (bool): Whether to save the data to Supabase
        
    Returns:
        dict: The result of the operation
    """
    try:
        # Fetch data from Grants.gov API
        data = await fetch_grants_data(keyword, date_range, opp_statuses, rows, sort_by)
        
        if "error" in data:
            return data
        
        # If save_to_supabase is False, just return the data
        if not save_to_supabase:
            # Extract count and opportunities for consistent response format
            count = 0
            if isinstance(data, list) and len(data) > 0 and "hitCount" in data[0]:
                count = data[0]["hitCount"]
            
            return {
                "success": True,
                "message": "Successfully fetched grants data",
                "count": count,
                "data": data
            }
        
        # Save data to Supabase
        result = save_grants_data(data)
        
        if "error" in result:
            return result
        
        return {
            "success": True,
            "message": f"Successfully fetched and saved {result.get('count', 0)} grants",
            "data": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"An error occurred: {str(e)}"
        } 