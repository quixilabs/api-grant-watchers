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
                existing = client.table("grants").select("id", "search_keyword").eq("id", opp_id).execute()
                
                if existing and existing.data and len(existing.data) > 0:
                    logger.info(f"Grant {opp_id} already exists in database, updating")
                    
                    # If the grant already exists, check if we need to update the search_keyword
                    existing_keyword = existing.data[0].get("search_keyword", "")
                    
                    # If there's a new keyword and it's not already in the existing keywords
                    if search_keyword:
                        # Split existing keywords into a list and normalize them to lowercase for comparison
                        existing_keywords_list = [k.strip().lower() for k in existing_keyword.split(',') if k.strip()] if existing_keyword else []
                        
                        # Check if the new keyword (case-insensitive) is already in the list
                        if search_keyword.lower() not in existing_keywords_list:
                            # Append the new keyword to the existing ones
                            if existing_keyword:
                                # Add the new keyword with a separator
                                upsert_data["search_keyword"] = f"{existing_keyword},{search_keyword}"
                                logger.info(f"Appending keyword '{search_keyword}' to existing keywords '{existing_keyword}'")
                            else:
                                # Just use the new keyword if there's no existing one
                                upsert_data["search_keyword"] = search_keyword
                                logger.info(f"Setting keyword '{search_keyword}' for grant {opp_id}")
                        else:
                            # Keep the existing keyword(s) as the new one is a duplicate
                            upsert_data["search_keyword"] = existing_keyword
                            logger.info(f"Keyword '{search_keyword}' already exists (case-insensitive) for grant {opp_id}")
                    else:
                        # Keep the existing keyword(s)
                        upsert_data["search_keyword"] = existing_keyword
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

async def update_grant_details(grant_id, details_data):
    """
    Update a grant record with detailed information.
    
    Args:
        grant_id (str): The ID of the grant to update
        details_data (dict): The detailed grant information
        
    Returns:
        dict: The response from Supabase
    """
    try:
        logger.info(f"Updating grant {grant_id} with detailed information")
        logger.info(f"Details data type: {type(details_data)}")
        logger.info(f"Details data structure: {str(details_data)[:500]}...")  # Log first 500 chars to avoid huge logs
        
        client = get_supabase_client()
        
        if not details_data or "error" in details_data:
            logger.error(f"Invalid details data for grant {grant_id}")
            return {"error": "Invalid details data"}
        
        # Extract relevant details from the response
        grant_details = {}
        
        # Handle the direct response format we're actually receiving
        if isinstance(details_data, dict) and "synopsis" in details_data:
            logger.info(f"Processing direct response format with synopsis")
            
            # Basic grant information
            if "opportunityNumber" in details_data:
                grant_details["number"] = details_data.get("opportunityNumber", "")
            
            if "opportunityTitle" in details_data:
                grant_details["title"] = details_data.get("opportunityTitle", "")
            
            if "owningAgencyCode" in details_data:
                grant_details["agency_code"] = details_data.get("owningAgencyCode", "")
            
            # Opportunity category
            if "opportunityCategory" in details_data and isinstance(details_data["opportunityCategory"], dict):
                category = details_data["opportunityCategory"]
                grant_details["opportunity_category"] = f"{category.get('category', '')}: {category.get('description', '')}"
            
            # Synopsis information
            if "synopsis" in details_data and isinstance(details_data["synopsis"], dict):
                synopsis = details_data["synopsis"]
                logger.info(f"Synopsis keys: {list(synopsis.keys())}")
                
                # Agency information
                if "agencyName" in synopsis:
                    grant_details["agency"] = synopsis.get("agencyName", "")
                
                # Description
                if "synopsisDesc" in synopsis:
                    grant_details["synopsis_desc"] = synopsis.get("synopsisDesc", "")
                    grant_details["description"] = synopsis.get("synopsisDesc", "")
                
                # Dates
                if "responseDate" in synopsis:
                    grant_details["close_date"] = synopsis.get("responseDate", "")
                    grant_details["response_date"] = synopsis.get("responseDate", "")
                
                if "postingDate" in synopsis:
                    grant_details["open_date"] = synopsis.get("postingDate", "")
                    grant_details["posting_date"] = synopsis.get("postingDate", "")
                
                # Funding information
                if "estimatedFunding" in synopsis:
                    grant_details["estimated_funding"] = synopsis.get("estimatedFunding", "")
                
                if "awardCeiling" in synopsis:
                    grant_details["award_ceiling"] = synopsis.get("awardCeiling", "")
                
                if "awardFloor" in synopsis:
                    grant_details["award_floor"] = synopsis.get("awardFloor", "")
                
                if "numberOfAwards" in synopsis:
                    grant_details["expected_awards"] = synopsis.get("numberOfAwards", "")
                
                if "costSharing" in synopsis:
                    grant_details["cost_sharing"] = str(synopsis.get("costSharing", ""))
                
                # Eligibility information
                if "applicantEligibilityDesc" in synopsis:
                    grant_details["applicant_eligibility_desc"] = synopsis.get("applicantEligibilityDesc", "")
                
                # Extract applicant types
                if "applicantTypes" in synopsis and isinstance(synopsis["applicantTypes"], list):
                    applicant_types = [item.get("description", "") for item in synopsis["applicantTypes"] if "description" in item]
                    if applicant_types:
                        grant_details["eligibility_categories"] = applicant_types
                
                # Extract funding instruments
                if "fundingInstruments" in synopsis and isinstance(synopsis["fundingInstruments"], list) and len(synopsis["fundingInstruments"]) > 0:
                    funding_instruments = [item.get("description", "") for item in synopsis["fundingInstruments"] if "description" in item]
                    if funding_instruments:
                        grant_details["funding_instrument_type"] = ", ".join(funding_instruments)
                
                # Extract funding activity categories
                if "fundingActivityCategories" in synopsis and isinstance(synopsis["fundingActivityCategories"], list):
                    funding_categories = [item.get("description", "") for item in synopsis["fundingActivityCategories"] if "description" in item]
                    if funding_categories:
                        grant_details["funding_activity_categories"] = funding_categories
                
                # Agency contacts
                agency_contacts = {}
                if "agencyContactName" in synopsis:
                    agency_contacts["name"] = synopsis.get("agencyContactName", "")
                if "agencyContactPhone" in synopsis:
                    agency_contacts["phone"] = synopsis.get("agencyContactPhone", "")
                if "agencyContactEmail" in synopsis:
                    agency_contacts["email"] = synopsis.get("agencyContactEmail", "")
                if "agencyContactDesc" in synopsis:
                    agency_contacts["description"] = synopsis.get("agencyContactDesc", "")
                
                if agency_contacts:
                    grant_details["agency_contacts"] = agency_contacts
            
            # Check for forecast data as well
            if "forecast" in details_data and isinstance(details_data["forecast"], dict):
                forecast = details_data["forecast"]
                logger.info(f"Found forecast data with keys: {list(forecast.keys())}")
                
                # If we don't have a description from synopsis, try to get it from forecast
                if "description" not in grant_details and "description" in forecast:
                    grant_details["description"] = forecast.get("description", "")
                
                # Additional forecast information
                if "estimatedFunding" in forecast and "estimated_funding" not in grant_details:
                    grant_details["estimated_funding"] = forecast.get("estimatedFunding", "")
                
                if "expectedNumberOfAwards" in forecast and "expected_awards" not in grant_details:
                    grant_details["expected_awards"] = forecast.get("expectedNumberOfAwards", "")
        
        # Handle the new response format from the sample (list format)
        elif isinstance(details_data, list) and len(details_data) > 0:
            # Use the first item in the list
            data = details_data[0]
            logger.info(f"Processing list data format, first item keys: {list(data.keys())}")
            
            # Basic grant information
            if "opportunityNumber" in data:
                grant_details["number"] = data.get("opportunityNumber", "")
            
            if "opportunityTitle" in data:
                grant_details["title"] = data.get("opportunityTitle", "")
            
            if "owningAgencyCode" in data:
                grant_details["agency_code"] = data.get("owningAgencyCode", "")
            
            # Opportunity category
            if "opportunityCategory" in data and isinstance(data["opportunityCategory"], dict):
                category = data["opportunityCategory"]
                grant_details["opportunity_category"] = f"{category.get('category', '')}: {category.get('description', '')}"
            
            # Synopsis information
            if "synopsis" in data and isinstance(data["synopsis"], dict):
                synopsis = data["synopsis"]
                logger.info(f"Synopsis keys: {list(synopsis.keys())}")
                
                # Agency information
                if "agencyName" in synopsis:
                    grant_details["agency"] = synopsis.get("agencyName", "")
                
                # Description
                if "synopsisDesc" in synopsis:
                    grant_details["synopsis_desc"] = synopsis.get("synopsisDesc", "")
                    grant_details["description"] = synopsis.get("synopsisDesc", "")
                
                # Dates
                if "responseDate" in synopsis:
                    grant_details["close_date"] = synopsis.get("responseDate", "")
                    grant_details["response_date"] = synopsis.get("responseDate", "")
                
                if "postingDate" in synopsis:
                    grant_details["open_date"] = synopsis.get("postingDate", "")
                    grant_details["posting_date"] = synopsis.get("postingDate", "")
                
                # Funding information
                if "estimatedFunding" in synopsis:
                    grant_details["estimated_funding"] = synopsis.get("estimatedFunding", "")
                
                if "awardCeiling" in synopsis:
                    grant_details["award_ceiling"] = synopsis.get("awardCeiling", "")
                
                if "awardFloor" in synopsis:
                    grant_details["award_floor"] = synopsis.get("awardFloor", "")
                
                if "numberOfAwards" in synopsis:
                    grant_details["expected_awards"] = synopsis.get("numberOfAwards", "")
                
                if "costSharing" in synopsis:
                    grant_details["cost_sharing"] = str(synopsis.get("costSharing", ""))
                
                # Eligibility information
                if "applicantEligibilityDesc" in synopsis:
                    grant_details["applicant_eligibility_desc"] = synopsis.get("applicantEligibilityDesc", "")
                
                # Extract applicant types
                if "applicantTypes" in synopsis and isinstance(synopsis["applicantTypes"], list):
                    applicant_types = [item.get("description", "") for item in synopsis["applicantTypes"] if "description" in item]
                    if applicant_types:
                        grant_details["eligibility_categories"] = applicant_types
                
                # Extract funding instruments
                if "fundingInstruments" in synopsis and isinstance(synopsis["fundingInstruments"], list) and len(synopsis["fundingInstruments"]) > 0:
                    funding_instruments = [item.get("description", "") for item in synopsis["fundingInstruments"] if "description" in item]
                    if funding_instruments:
                        grant_details["funding_instrument_type"] = ", ".join(funding_instruments)
                
                # Extract funding activity categories
                if "fundingActivityCategories" in synopsis and isinstance(synopsis["fundingActivityCategories"], list):
                    funding_categories = [item.get("description", "") for item in synopsis["fundingActivityCategories"] if "description" in item]
                    if funding_categories:
                        grant_details["funding_activity_categories"] = funding_categories
                
                # Agency contacts
                agency_contacts = {}
                if "agencyContactName" in synopsis:
                    agency_contacts["name"] = synopsis.get("agencyContactName", "")
                if "agencyContactPhone" in synopsis:
                    agency_contacts["phone"] = synopsis.get("agencyContactPhone", "")
                if "agencyContactEmail" in synopsis:
                    agency_contacts["email"] = synopsis.get("agencyContactEmail", "")
                if "agencyContactDesc" in synopsis:
                    agency_contacts["description"] = synopsis.get("agencyContactDesc", "")
                
                if agency_contacts:
                    grant_details["agency_contacts"] = agency_contacts
        
        # Handle the old response format as a fallback
        elif "detailsResponse" in details_data:
            details = details_data["detailsResponse"]
            logger.info(f"Processing detailsResponse format, keys: {list(details.keys())}")
            
            # Extract opportunity details
            if "opportunity" in details:
                opp = details["opportunity"]
                logger.info(f"Opportunity keys: {list(opp.keys())}")
                grant_details["description"] = opp.get("description", "")
                grant_details["category_explanation"] = opp.get("categoryExplanation", "")
                grant_details["award_ceiling"] = opp.get("awardCeiling", "")
                grant_details["award_floor"] = opp.get("awardFloor", "")
                grant_details["expected_awards"] = opp.get("expectedNumberOfAwards", "")
                grant_details["funding_instrument_type"] = opp.get("fundingInstrumentType", "")
                grant_details["eligibility_categories"] = opp.get("eligibilityCategories", [])
                grant_details["cost_sharing"] = opp.get("costSharing", "")
                
                # Add any additional fields that might be useful
                if "additionalInformation" in opp:
                    grant_details["additional_information"] = opp["additionalInformation"]
                
                if "agencyContactList" in opp:
                    grant_details["agency_contacts"] = opp["agencyContactList"]
        # Handle the format with direct keys like 'opportunityNumber', 'opportunityTitle', etc.
        elif isinstance(details_data, dict) and "opportunityNumber" in details_data and "opportunityTitle" in details_data:
            logger.info(f"Processing direct keys format for grant {grant_id}")
            
            # Basic grant information
            grant_details["number"] = details_data.get("opportunityNumber", "")
            grant_details["title"] = details_data.get("opportunityTitle", "")
            grant_details["agency_code"] = details_data.get("owningAgencyCode", "")
            
            # Opportunity category
            if "opportunityCategory" in details_data and isinstance(details_data["opportunityCategory"], dict):
                category = details_data["opportunityCategory"]
                grant_details["opportunity_category"] = f"{category.get('category', '')}: {category.get('description', '')}"
            
            # Check for agency details
            if "agencyDetails" in details_data and isinstance(details_data["agencyDetails"], dict):
                agency_details = details_data["agencyDetails"]
                grant_details["agency"] = agency_details.get("name", "")
            
            # Check for forecast data
            if "forecast" in details_data and isinstance(details_data["forecast"], dict):
                forecast = details_data["forecast"]
                
                # Description and funding information from forecast
                if "description" in forecast:
                    grant_details["description"] = forecast.get("description", "")
                
                if "estimatedFunding" in forecast:
                    grant_details["estimated_funding"] = forecast.get("estimatedFunding", "")
                
                if "expectedNumberOfAwards" in forecast:
                    grant_details["expected_awards"] = forecast.get("expectedNumberOfAwards", "")
                
                if "awardCeiling" in forecast:
                    grant_details["award_ceiling"] = forecast.get("awardCeiling", "")
                
                if "awardFloor" in forecast:
                    grant_details["award_floor"] = forecast.get("awardFloor", "")
                
                # Dates from forecast
                if "postDate" in forecast:
                    grant_details["open_date"] = forecast.get("postDate", "")
                    grant_details["posting_date"] = forecast.get("postDate", "")
                
                if "closeDate" in forecast:
                    grant_details["close_date"] = forecast.get("closeDate", "")
                    grant_details["response_date"] = forecast.get("closeDate", "")
        else:
            logger.warning(f"Unrecognized details data format for grant {grant_id}. Keys: {list(details_data.keys()) if isinstance(details_data, dict) else 'Not a dict'}")
        
        # Add the full details data as a JSON field
        grant_details["details_raw_data"] = details_data
        
        logger.info(f"Extracted grant details: {grant_details.keys()}")
        
        # Update the grant record
        result = client.table("grants").update(grant_details).eq("id", grant_id).execute()
        
        logger.info(f"Successfully updated grant {grant_id} with detailed information")
        return {
            "success": True,
            "grant_id": grant_id,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error updating grant {grant_id} with details: {str(e)}")
        return {"error": f"Error updating grant details: {str(e)}"}

def get_grants_by_keyword(keyword, limit=100, offset=0):
    """
    Retrieve grants that match a specific keyword.
    
    Args:
        keyword (str): The keyword to search for (case-insensitive)
        limit (int): Maximum number of results to return
        offset (int): Offset for pagination
        
    Returns:
        dict: The grants that match the keyword
    """
    try:
        logger.info(f"Retrieving grants for keyword: {keyword}")
        client = get_supabase_client()
        
        # Calculate range for pagination
        from_range = offset
        to_range = offset + limit - 1  # -1 because range is inclusive
        
        # Use ILIKE operator for case-insensitive matching
        # Use range instead of offset for pagination
        result = client.table("grants").select("*").ilike("search_keyword", f"%{keyword}%").range(from_range, to_range).execute()
        
        logger.info(f"Found {len(result.data)} grants for keyword '{keyword}'")
        return {
            "success": True,
            "grants": result.data,
            "count": len(result.data)
        }
    except Exception as e:
        logger.error(f"Error retrieving grants for keyword '{keyword}': {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "grants": []
        }

def update_grant_summary(grant_id, summary_data):
    """
    Update a grant record with summary information generated by DeepSeek AI.
    
    Args:
        grant_id (str): The ID of the grant to update
        summary_data (dict): The summary information generated by DeepSeek AI
        
    Returns:
        dict: The response from Supabase
    """
    try:
        logger.info(f"Updating grant {grant_id} with summary information")
        client = get_supabase_client()
        
        if not summary_data or "error" in summary_data:
            logger.error(f"Invalid summary data for grant {grant_id}")
            return {"error": "Invalid summary data"}
        
        # Prepare the data for update
        update_data = {
            "synopsis_summary": summary_data
        }
        
        # Update the grant record
        result = client.table("grants").update(update_data).eq("id", grant_id).execute()
        
        logger.info(f"Successfully updated grant {grant_id} with summary information")
        return {
            "success": True,
            "grant_id": grant_id,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error updating grant {grant_id} with summary: {str(e)}")
        return {"error": f"Error updating grant summary: {str(e)}"}

def get_all_grants(limit=100, offset=0):
    """
    Retrieve all grants from the database.
    
    Args:
        limit (int): Maximum number of results to return
        offset (int): Offset for pagination
        
    Returns:
        dict: The grants from the database
    """
    try:
        logger.info(f"Retrieving all grants with limit {limit} and offset {offset}")
        client = get_supabase_client()
        
        # In Supabase Python client 1.2.0, we need to use range instead of offset
        # The range is inclusive of the lower bound and exclusive of the upper bound
        # So to get records from offset to offset+limit, we use range(offset, offset+limit)
        from_range = offset
        to_range = offset + limit - 1  # -1 because range is inclusive
        
        # Use the range method instead of offset
        result = client.table("grants").select("*").range(from_range, to_range).execute()
        
        logger.info(f"Found {len(result.data)} grants")
        return {
            "success": True,
            "count": len(result.data),
            "grants": result.data,  # Changed 'data' to 'grants' for workflow compatibility
            "total": None  # This will be None since we don't know the total count without a separate query
        }
    except Exception as e:
        logger.error(f"Error retrieving grants: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "grants": []  # Changed 'data' to 'grants' for workflow compatibility
        }

async def get_grants_data():
    """
    Get all grants data from the Supabase database.
    
    Returns:
        list: List of all grants
    """
    try:
        logger.info("Fetching all grants data from Supabase")
        client = get_supabase_client()
        
        result = client.table("grants").select("*").execute()
        
        if not result.data:
            logger.warning("No grants found in the database")
            return []
        
        logger.info(f"Successfully fetched {len(result.data)} grants")
        return result.data
    except Exception as e:
        logger.error(f"Error fetching grants data: {str(e)}")
        raise

async def get_organization_grant_matches(organization_id: str):
    """
    Get all grant matches for a specific organization.
    
    Args:
        organization_id (str): The ID of the organization
        
    Returns:
        dict: Organization and its grant matches
    """
    try:
        logger.info(f"Fetching grant matches for organization {organization_id}")
        client = get_supabase_client()
        
        # Get the organization
        org_result = client.table("organizations").select("*").eq("id", organization_id).execute()
        
        if not org_result.data:
            logger.error(f"Organization not found with ID: {organization_id}")
            return {"error": f"Organization not found with ID: {organization_id}"}
        
        organization = org_result.data[0]
        
        # Get the grant matches
        matches_query = client.table("organization_grant_matches").select("*").eq("organization_id", organization_id).execute()
        
        matches = []
        for match in matches_query.data:
            # Get the grant details
            grant_id = match.get("grant_id")
            grant_result = client.table("grants").select("*").eq("id", grant_id).execute()
            
            if grant_result.data:
                grant = grant_result.data[0]
                
                # Format the grant information
                grant_info = {
                    "id": grant.get("id"),
                    "title": grant.get("title"),
                    "agency": grant.get("agency"),
                    "award_floor": grant.get("award_floor"),
                    "award_ceiling": grant.get("award_ceiling"),
                    "close_date": grant.get("close_date"),
                    "description": grant.get("description"),
                    "eligibility": grant.get("applicant_eligibility_desc"),
                    "grant_link": f"https://www.grants.gov/search-grants.html?keywords={grant.get('id')}"
                }
                
                matches.append({
                    "grant": grant_info,
                    "match_score": match.get("match_score"),
                    "match_reason": match.get("match_reason")
                })
        
        result = {
            "organization": {
                "id": organization.get("id"),
                "name": organization.get("organization_name"),
                "email": organization.get("email"),
                "description": organization.get("organization_profile")
            },
            "matches": matches,
            "total_matches": len(matches)
        }
        
        # Generate HTML content for the response
        html_content = generate_matches_html(result)
        result["html_content"] = html_content
        
        logger.info(f"Successfully fetched {len(matches)} grant matches for organization {organization_id}")
        return result
    except Exception as e:
        logger.error(f"Error fetching organization grant matches: {str(e)}")
        raise

def generate_matches_html(data):
    """
    Generate HTML content for grant matches.
    
    Args:
        data (dict): Organization and matches data
        
    Returns:
        str: HTML content
    """
    org = data["organization"]
    matches = data["matches"]
    
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
            Grant Matches for {org.get('name', 'Organization')}
        </h1>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
            <h3 style="margin-top: 0; color: #2c3e50;">Organization Information</h3>
            <p><strong>Name:</strong> {org.get('name', '')}</p>
            <p><strong>Email:</strong> {org.get('email', '')}</p>
            <p><strong>Description:</strong> {org.get('description', '')}</p>
        </div>
        
        <h2 style="color: #2c3e50; margin-top: 30px;">
            {len(matches)} Matching Grants Found
        </h2>
    """
    
    if not matches:
        html += """
        <div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin-top: 20px;">
            <p style="margin: 0; color: #721c24;">No matching grants found for this organization.</p>
        </div>
        """
    else:
        for i, match in enumerate(matches):
            grant = match.get("grant", {})
            score = match.get("match_score", 0)
            reason = match.get("match_reason", "")
            
            # Calculate score color (green for high scores, yellow for medium, red for low)
            if score >= 0.8:
                score_color = "#28a745"  # Green
            elif score >= 0.6:
                score_color = "#ffc107"  # Yellow
            else:
                score_color = "#dc3545"  # Red
            
            html += f"""
            <div style="background-color: #ffffff; padding: 15px; border-radius: 5px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h3 style="margin: 0; color: #2c3e50;">{i+1}. {grant.get('title', 'Unknown Grant')}</h3>
                    <span style="background-color: {score_color}; color: white; padding: 5px 10px; border-radius: 20px; font-weight: bold;">
                        Match: {int(score * 100)}%
                    </span>
                </div>
                
                <p><strong>Grant ID:</strong> {grant.get('id', '')}</p>
                <p><strong>Agency:</strong> {grant.get('agency', '')}</p>
                <p><strong>Deadline:</strong> {grant.get('close_date', '')}</p>
                <p><strong>Award Range:</strong> ${grant.get('award_floor', '0')} - ${grant.get('award_ceiling', '0')}</p>
                
                <div style="background-color: #e9f7fe; padding: 10px; border-radius: 5px; margin: 10px 0;">
                    <h4 style="margin-top: 0; color: #0078d4;">Why This Grant Matches</h4>
                    <p>{reason}</p>
                </div>
                
                <p><strong>Description:</strong> {grant.get('description', '')[:300]}...</p>
                
                <a href="{grant.get('grant_link', '')}" target="_blank" style="display: inline-block; background-color: #3498db; color: white; padding: 8px 15px; text-decoration: none; border-radius: 5px; margin-top: 10px;">
                    View Grant Details
                </a>
            </div>
            """
    
    html += """
    </div>
    """
    
    return html 

def clean_duplicate_keywords():
    """
    Clean up duplicate keywords in the search_keyword field of all grants.
    This function normalizes keywords and removes duplicates.
    
    Returns:
        dict: Summary of the cleanup operation
    """
    try:
        logger.info("Starting cleanup of duplicate keywords in grants table")
        client = get_supabase_client()
        
        # Get all grants
        result = client.table("grants").select("id", "search_keyword").execute()
        
        if not result.data:
            logger.info("No grants found in the database")
            return {
                "success": True,
                "message": "No grants found in the database",
                "grants_processed": 0,
                "grants_updated": 0
            }
        
        grants_processed = 0
        grants_updated = 0
        
        for grant in result.data:
            grants_processed += 1
            grant_id = grant.get("id")
            search_keyword = grant.get("search_keyword", "")
            
            if not search_keyword:
                continue
            
            # Split keywords and normalize them
            keywords_list = [k.strip() for k in search_keyword.split(',') if k.strip()]
            
            # Remove duplicates (case-insensitive)
            unique_keywords = []
            lowercase_set = set()
            
            for keyword in keywords_list:
                if keyword.lower() not in lowercase_set:
                    lowercase_set.add(keyword.lower())
                    unique_keywords.append(keyword)
            
            # Check if we removed any duplicates
            if len(unique_keywords) < len(keywords_list):
                # Join the unique keywords back into a string
                new_search_keyword = ','.join(unique_keywords)
                
                # Update the grant
                client.table("grants").update({"search_keyword": new_search_keyword}).eq("id", grant_id).execute()
                
                grants_updated += 1
                logger.info(f"Updated grant {grant_id}: Removed duplicate keywords. Before: '{search_keyword}', After: '{new_search_keyword}'")
        
        logger.info(f"Completed keyword cleanup. Processed {grants_processed} grants, updated {grants_updated} grants.")
        
        return {
            "success": True,
            "message": "Successfully cleaned up duplicate keywords",
            "grants_processed": grants_processed,
            "grants_updated": grants_updated
        }
    except Exception as e:
        logger.error(f"Error cleaning up duplicate keywords: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        } 