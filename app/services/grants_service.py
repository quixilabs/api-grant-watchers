import httpx
import json
import logging
from app.core.config import settings
from app.utils.supabase import save_grants_data, update_grant_details

# Set up logging
logger = logging.getLogger(__name__)

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
    
    logger.info(f"Fetching grants data from {url} with payload: {payload}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Successfully fetched grants data. Status code: {response.status_code}")
            return data
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e}")
        return {"error": f"HTTP error occurred: {e}"}
    except httpx.RequestError as e:
        logger.error(f"Request error occurred: {e}")
        return {"error": f"Request error occurred: {e}"}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {"error": f"An unexpected error occurred: {e}"}

async def fetch_grant_details(opp_id):
    """
    Fetch detailed information about a specific grant opportunity.
    
    Args:
        opp_id (str): The opportunity ID to fetch details for
        
    Returns:
        dict: The detailed grant information
    """
    url = "https://apply07.grants.gov/grantsws/rest/opportunity/details"
    
    # The API expects form data, not JSON
    data = {
        "oppId": opp_id
    }
    
    headers = {
        "Accept": "application/json",
        # Don't set Content-Type header, let httpx set it correctly for form data
    }
    
    logger.info(f"Fetching grant details for opportunity ID: {opp_id}")
    
    async with httpx.AsyncClient() as client:
        # Try multiple approaches to handle the API's requirements
        
        # Approach 1: Using form data
        try:
            logger.info(f"Trying approach 1 (form data) for {opp_id}")
            response = await client.post(url, data=data, headers=headers)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Successfully fetched grant details using approach 1. Status code: {response.status_code}")
            return data
        except Exception as e1:
            logger.error(f"Approach 1 failed: {e1}")
            
            # Approach 2: Using URL parameters with POST
            try:
                logger.info(f"Trying approach 2 (URL parameters with POST) for {opp_id}")
                alt_url = f"{url}?oppId={opp_id}"
                alt_response = await client.post(alt_url, headers={"Accept": "application/json"})
                alt_response.raise_for_status()
                alt_data = alt_response.json()
                logger.info(f"Successfully fetched grant details using approach 2. Status code: {alt_response.status_code}")
                return alt_data
            except Exception as e2:
                logger.error(f"Approach 2 failed: {e2}")
                
                # Approach 3: Using URL parameters with GET
                try:
                    logger.info(f"Trying approach 3 (URL parameters with GET) for {opp_id}")
                    alt_url2 = f"{url}?oppId={opp_id}"
                    alt_response2 = await client.get(alt_url2, headers={"Accept": "application/json"})
                    alt_response2.raise_for_status()
                    alt_data2 = alt_response2.json()
                    logger.info(f"Successfully fetched grant details using approach 3. Status code: {alt_response2.status_code}")
                    return alt_data2
                except Exception as e3:
                    logger.error(f"Approach 3 failed: {e3}")
                    
                    # Approach 4: Using a different endpoint format
                    try:
                        logger.info(f"Trying approach 4 (different endpoint format) for {opp_id}")
                        alt_url3 = f"https://apply07.grants.gov/grantsws/rest/opportunities/details/{opp_id}"
                        alt_response3 = await client.get(alt_url3, headers={"Accept": "application/json"})
                        alt_response3.raise_for_status()
                        alt_data3 = alt_response3.json()
                        logger.info(f"Successfully fetched grant details using approach 4. Status code: {alt_response3.status_code}")
                        return alt_data3
                    except Exception as e4:
                        logger.error(f"All approaches failed. Last error: {e4}")
                        return {
                            "error": "Failed to fetch grant details after trying multiple approaches",
                            "details": f"Errors: 1: {e1}, 2: {e2}, 3: {e3}, 4: {e4}"
                        }

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
        logger.info(f"Fetching and {'saving' if save_to_supabase else 'not saving'} grants data with parameters: keyword={keyword}, date_range={date_range}, opp_statuses={opp_statuses}, rows={rows}, sort_by={sort_by}")
        
        # Fetch data from Grants.gov API
        data = await fetch_grants_data(keyword, date_range, opp_statuses, rows, sort_by)
        
        if "error" in data:
            logger.error(f"Error fetching data: {data['error']}")
            return data
        
        # If save_to_supabase is False, just return the data
        if not save_to_supabase:
            # Extract count and opportunities for consistent response format
            count = 0
            if isinstance(data, list) and len(data) > 0 and "hitCount" in data[0]:
                count = data[0]["hitCount"]
                logger.info(f"Not saving to Supabase. Found {count} opportunities.")
            
            return {
                "success": True,
                "message": "Successfully fetched grants data",
                "count": count,
                "data": data
            }
        
        # Save data to Supabase
        logger.info("Saving data to Supabase")
        result = save_grants_data(data)
        
        if "error" in result:
            logger.error(f"Error saving data to Supabase: {result['error']}")
            return result
        
        logger.info(f"Successfully saved data to Supabase. Count: {result.get('count', 0)}")
        return {
            "success": True,
            "message": f"Successfully fetched and saved {result.get('count', 0)} grants",
            "data": result
        }
    except Exception as e:
        logger.error(f"An error occurred in fetch_and_save_grants_data: {str(e)}")
        return {
            "success": False,
            "error": f"An error occurred: {str(e)}"
        } 