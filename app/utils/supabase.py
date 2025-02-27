from supabase import create_client
from app.core.config import settings
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_supabase_client():
    """
    Create and return a Supabase client using the credentials from settings.
    """
    # Check if Supabase URL and key are properly set
    logger.info(f"Supabase URL: {settings.SUPABASE_URL}")
    logger.info(f"Supabase Key: {settings.SUPABASE_KEY[:10]}...{settings.SUPABASE_KEY[-10:]}")
    
    if not settings.SUPABASE_URL or settings.SUPABASE_URL == "your_supabase_url_here":
        raise ValueError("Supabase URL is not properly configured in .env file")
    
    if not settings.SUPABASE_KEY or settings.SUPABASE_KEY == "your_supabase_key_here":
        raise ValueError("Supabase key is not properly configured in .env file")
    
    try:
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info("Supabase client created successfully")
        return client
    except Exception as e:
        logger.error(f"Error creating Supabase client: {str(e)}")
        raise

def save_grants_data(data):
    """
    Save grants data to Supabase table.
    
    Args:
        data (dict or list): The grants data to save
        
    Returns:
        dict: The response from Supabase
    """
    try:
        logger.info("Attempting to get Supabase client")
        client = get_supabase_client()
        
        # Handle different data formats
        logger.info(f"Data type received: {type(data)}")
        
        # Convert to list if it's a dictionary
        if isinstance(data, dict):
            logger.info("Converting dictionary to list format")
            data = [data]
        
        # Extract the opportunities from the response
        if not data or not isinstance(data, list) or len(data) == 0:
            logger.error("Invalid data format")
            return {"error": "Invalid data format"}
        
        response_data = data[0]
        
        # Extract search keyword from search parameters
        search_keyword = ""
        if "searchParams" in response_data and "keyword" in response_data["searchParams"]:
            search_keyword = response_data["searchParams"]["keyword"]
            logger.info(f"Extracted search keyword: {search_keyword}")
        
        if "oppHits" not in response_data:
            logger.error(f"No opportunities found in data. Keys available: {list(response_data.keys())}")
            # Try to find opportunities in a different format
            if "searchResponse" in response_data and "opportunityList" in response_data["searchResponse"]:
                logger.info("Found opportunities in searchResponse.opportunityList")
                opportunities = response_data["searchResponse"]["opportunityList"]
            else:
                return {"error": "No opportunities found in data"}
        else:
            opportunities = response_data["oppHits"]
        
        logger.info(f"Found {len(opportunities)} opportunities to save")
        
        # Track processed IDs to avoid duplicates within the same batch
        processed_ids = set()
        
        # Insert each opportunity into the grants table
        results = []
        for i, opp in enumerate(opportunities):
            try:
                # Get the opportunity ID
                opp_id = opp.get("id", opp.get("opportunityId", ""))
                
                # Skip if we've already processed this ID in the current batch
                if opp_id in processed_ids:
                    logger.info(f"Skipping duplicate opportunity {opp_id} within batch")
                    continue
                
                # Add to processed IDs
                processed_ids.add(opp_id)
                
                logger.info(f"Saving opportunity {i+1}/{len(opportunities)}: {opp_id} - {opp.get('title', 'unknown')}")
                
                # Prepare data for upsert, handling different data structures
                upsert_data = {
                    "id": opp_id,
                    "number": opp.get("number", opp.get("opportunityNumber", "")),
                    "title": opp.get("title", opp.get("opportunityTitle", "")),
                    "agency_code": opp.get("agencyCode", ""),
                    "agency": opp.get("agency", ""),
                    "open_date": opp.get("openDate", opp.get("opportunityOpenDate", "")),
                    "close_date": opp.get("closeDate", opp.get("opportunityCloseDate", "")),
                    "status": opp.get("oppStatus", opp.get("opportunityStatus", "")),
                    "doc_type": opp.get("docType", ""),
                    "cfda_list": opp.get("cfdaList", opp.get("cfdaNumberList", [])),
                    "raw_data": opp,
                    "search_params": response_data.get("searchParams", {}),
                    "search_keyword": search_keyword  # Add the search keyword
                }
                
                # Check if the grant already exists before upserting
                existing = client.table("grants").select("id").eq("id", opp_id).execute()
                
                if existing and existing.data and len(existing.data) > 0:
                    logger.info(f"Grant {opp_id} already exists in database, updating")
                else:
                    logger.info(f"Grant {opp_id} is new, inserting")
                
                # Use upsert to handle both insert and update cases
                result = client.table("grants").upsert(upsert_data).execute()
                
                results.append(result)
            except Exception as e:
                logger.error(f"Error saving opportunity {opp.get('id', 'unknown')}: {str(e)}")
                # Continue with next opportunity instead of failing the entire batch
                continue
        
        logger.info(f"Successfully saved {len(results)} opportunities")
        return {
            "success": True,
            "count": len(results),  # Return actual number of saved records
            "total_found": len(opportunities),  # Total opportunities found
            "results": results
        }
    except ValueError as e:
        logger.error(f"ValueError: {str(e)}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error saving data to Supabase: {str(e)}")
        return {"error": f"Error saving data to Supabase: {str(e)}"} 