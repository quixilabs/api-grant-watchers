from supabase import create_client
from app.core.config import settings

def get_supabase_client():
    """
    Create and return a Supabase client using the credentials from settings.
    """
    # Check if Supabase URL and key are properly set
    if not settings.SUPABASE_URL or settings.SUPABASE_URL == "your_supabase_url_here":
        raise ValueError("Supabase URL is not properly configured in .env file")
    
    if not settings.SUPABASE_KEY or settings.SUPABASE_KEY == "your_supabase_key_here":
        raise ValueError("Supabase key is not properly configured in .env file")
    
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def save_grants_data(data):
    """
    Save grants data to Supabase table.
    
    Args:
        data (dict): The grants data to save
        
    Returns:
        dict: The response from Supabase
    """
    try:
        client = get_supabase_client()
        
        # Extract the opportunities from the response
        if not data or not isinstance(data, list) or len(data) == 0:
            return {"error": "Invalid data format"}
        
        response_data = data[0]
        
        if "oppHits" not in response_data:
            return {"error": "No opportunities found in data"}
        
        opportunities = response_data["oppHits"]
        
        # Insert each opportunity into the grants table
        results = []
        for opp in opportunities:
            result = client.table("grants").upsert(
                {
                    "id": opp.get("id"),
                    "number": opp.get("number"),
                    "title": opp.get("title"),
                    "agency_code": opp.get("agencyCode"),
                    "agency": opp.get("agency"),
                    "open_date": opp.get("openDate"),
                    "close_date": opp.get("closeDate"),
                    "status": opp.get("oppStatus"),
                    "doc_type": opp.get("docType"),
                    "cfda_list": opp.get("cfdaList"),
                    "raw_data": opp,
                    "search_params": response_data.get("searchParams")
                }
            ).execute()
            
            results.append(result)
        
        return {
            "success": True,
            "count": len(opportunities),
            "results": results
        }
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Error saving data to Supabase: {str(e)}"} 