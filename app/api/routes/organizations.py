from fastapi import APIRouter, HTTPException, Query
import logging
from app.utils.supabase import get_supabase_client
from app.utils.organization_utils import process_new_organization
from app.utils.organization_grant_matcher import match_organization_with_grants, save_organization_grant_matches
from app.utils.mailgun_client import send_grant_match_email, generate_email_content

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

async def process_organization_summary(organization: dict) -> dict:
    """
    Process a single organization to generate its summary.
    
    Args:
        organization (dict): Organization data
        
    Returns:
        dict: Result of the processing
    """
    try:
        # Generate and save summary
        result = await process_new_organization(organization)
        return {
            "success": result.get("success", False),
            "organization_id": organization.get("id"),
            "result": result
        }
    except Exception as e:
        return {
            "success": False,
            "organization_id": organization.get("id"),
            "error": str(e)
        }

@router.post("/generate-summary/{organization_id}")
async def generate_organization_summary_by_id(
    organization_id: str,
    force_regenerate: bool = Query(False, description="Force regenerate summary even if it exists")
):
    """
    Generate a summary for a specific organization.
    
    Args:
        organization_id (str): ID of the organization to process
        force_regenerate (bool): Whether to regenerate the summary even if it exists
        
    Returns:
        dict: Result of the processing
    """
    try:
        logger.info(f"Generating summary for organization: {organization_id}")
        client = get_supabase_client()
        
        # Get the organization
        query = client.table("organizations").select("*").eq("id", organization_id)
        result = query.execute()
        
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Organization not found with ID: {organization_id}"
            )
        
        organization = result.data[0]
        
        logger.debug(f"Processing organization: {organization.get('organization_name')}")
        logger.debug(f"Organization data: {organization}")
        
        # Check if summary exists and force_regenerate is False
        if organization.get("summary") and not force_regenerate:
            return {
                "success": True,
                "message": "Organization already has a summary",
                "organization_id": organization_id,
                "existing_summary": organization.get("summary")
            }
        
        # Process the organization
        result = await process_organization_summary(organization)
        
        if result["success"]:
            return {
                "success": True,
                "message": "Successfully generated organization summary",
                "organization_id": organization_id,
                "result": result["result"]
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate summary: {result.get('error', 'Unknown error')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating organization summary: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating organization summary: {str(e)}"
        )

async def process_organization_grant_matching(organization: dict, grants: list) -> dict:
    """
    Process a single organization to match it with relevant grants.
    
    Args:
        organization (dict): Organization data
        grants (list): List of all available grants
        
    Returns:
        dict: Result of the matching process
    """
    try:
        # Match organization with grants
        matches = await match_organization_with_grants(organization, grants)
        
        if matches:
            # Save matches
            save_result = await save_organization_grant_matches(organization["id"], matches)
            return {
                "success": save_result.get("success", False),
                "organization_id": organization.get("id"),
                "matches_count": len(matches),
                "result": save_result
            }
        else:
            return {
                "success": True,
                "organization_id": organization.get("id"),
                "matches_count": 0,
                "message": "No matching grants found"
            }
    except Exception as e:
        return {
            "success": False,
            "organization_id": organization.get("id"),
            "error": str(e)
        }

@router.post("/match-with-grants/{organization_id}")
async def match_organization_with_grants_by_id(
    organization_id: str,
    force_rematch: bool = Query(False, description="Force rematch even if matches exist")
):
    """
    Match a specific organization with relevant grants.
    
    Args:
        organization_id (str): ID of the organization to process
        force_rematch (bool): Whether to rematch even if matches exist
        
    Returns:
        dict: Result of the matching process
    """
    try:
        logger.info(f"Generating grant matches for organization: {organization_id}")
        client = get_supabase_client()
        
        # Get the organization
        query = client.table("organizations").select("*").eq("id", organization_id)
        result = query.execute()
        
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Organization not found with ID: {organization_id}"
            )
        
        organization = result.data[0]
        
        logger.debug(f"Processing organization: {organization.get('organization_name')}")
        logger.debug(f"Organization data: {organization}")
        
        # Check if matches exist and force_rematch is False
        if not force_rematch:
            matches_result = client.table("organization_grant_matches").select("*").eq("organization_id", organization_id).execute()
            if matches_result.data:
                return {
                    "success": True,
                    "message": "Organization already has grant matches",
                    "organization_id": organization_id,
                    "existing_matches_count": len(matches_result.data)
                }
        
        # Get all grants
        grants_result = client.table("grants").select("*").execute()
        grants = grants_result.data
        
        if not grants:
            raise HTTPException(
                status_code=500,
                detail="No grants found in the database"
            )
        
        logger.debug(f"Fetched {len(grants)} grants from database")
        logger.debug(f"Sample grant IDs: {[grant.get('id') for grant in grants[:5]]}")
        
        # Process the organization
        result = await process_organization_grant_matching(organization, grants)
        
        if result["success"]:
            return {
                "success": True,
                "message": "Successfully matched organization with grants",
                "organization_id": organization_id,
                "matches_count": result.get("matches_count", 0),
                "result": result.get("result")
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to match grants: {result.get('error', 'Unknown error')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error matching organization with grants: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error matching organization with grants: {str(e)}"
        )

@router.get("/grant-matches/{organization_id}")
async def get_organization_grant_matches(organization_id: str):
    """
    Get all grant matches for a specific organization with formatted HTML output.
    """
    try:
        # Create Supabase client
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(status_code=500, detail="Failed to create Supabase client")

        # Get organization details
        org_response = supabase.table("organizations").select("*").eq("id", organization_id).execute()
        if not org_response.data:
            raise HTTPException(status_code=404, detail=f"Organization not found: {organization_id}")
        
        organization = org_response.data[0]
        
        # Get all grant matches for this organization
        matches_response = supabase.table("organization_grant_matches").select("*").eq("organization_id", organization_id).execute()
        if not matches_response.data:
            return {
                "organization": organization,
                "matches": [],
                "html_content": "<p>No grant matches found for this organization.</p>"
            }
                
        # Get grant details for each match
        grant_matches = []
        for match in matches_response.data:
            grant_response = supabase.table("grants").select("*").eq("id", match["grant_id"]).execute()
            if grant_response.data:
                grant_matches.append({
                    "grant": grant_response.data[0],
                    "match_score": match["match_score"],
                    "match_reason": match["match_reason"]
                })

        # Generate HTML content
        html_content = generate_email_content(organization, grant_matches)

        # Format the response
        response_data = {
            "organization": {
                "id": organization["id"],
                "name": organization.get("organization_name", "N/A"),
                "email": organization.get("email", "N/A"),
                "description": organization.get("description", "N/A")
            },
            "matches": [
                {
                    "grant": {
                        "id": match["grant"]["id"],
                        "title": match["grant"].get("title", "N/A"),
                        "agency": match["grant"].get("agency", "N/A"),
                        "award_floor": match["grant"].get("award_floor", "N/A"),
                        "award_ceiling": match["grant"].get("award_ceiling", "N/A"),
                        "close_date": match["grant"].get("close_date", "N/A"),
                        "description": match["grant"].get("description", "N/A"),
                        "eligibility": match["grant"].get("eligibility", "N/A"),
                        "grant_link": f"https://www.grants.gov/search-grants.html?keywords={match['grant']['id']}"
                    },
                    "match_score": float(match["match_score"]),
                    "match_reason": match["match_reason"]
                }
                for match in grant_matches
            ],
            "html_content": html_content,
            "total_matches": len(grant_matches)
        }

        return response_data

    except Exception as e:
        logger.error(f"Error in get_organization_grant_matches: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 