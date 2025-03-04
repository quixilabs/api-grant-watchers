from fastapi import APIRouter, Depends, HTTPException, Request, Header, Query
import json
import hmac
import hashlib
import logging
from app.utils.supabase import get_supabase_client
from app.core.config import settings
from app.utils.organization_utils import process_new_organization
from app.utils.organization_grant_matcher import match_organization_with_grants, save_organization_grant_matches
from app.utils.mailgun_client import send_grant_match_email, generate_email_content

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

async def verify_webhook_signature(request: Request, x_webhook_signature: str = Header(None)):
    """
    Verify the webhook signature from Supabase.
    """
    # TEMPORARY: Bypass signature verification for testing
    # Remove this line when going to production
    return True
    
    if not settings.WEBHOOK_SECRET:
        logger.warning("Webhook secret not set, skipping signature verification")
        return True
    
    if not x_webhook_signature:
        logger.error("Missing webhook signature header")
        raise HTTPException(status_code=401, detail="Missing webhook signature")
    
    # Get the raw request body
    body = await request.body()
    
    # Compute the expected signature
    expected_signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures
    if not hmac.compare_digest(expected_signature, x_webhook_signature):
        logger.error("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    return True

@router.post("/")
async def webhook_handler(request: Request, verified: bool = Depends(verify_webhook_signature)):
    """
    Handle incoming webhooks from Supabase.
    """
    try:
        # Parse the webhook payload
        payload = await request.json()
        logger.info(f"Received webhook: {json.dumps(payload)[:500]}...")
        
        # Check the event type
        event_type = payload.get("type")
        table = payload.get("table")
        
        if event_type == "INSERT" and table == "organizations":
            # Process new organization
            record = payload.get("record", {})
            logger.info(f"Processing new organization: {record.get('organization_name', 'Unknown')}")
            
            # Process the new organization
            result = await process_new_organization(record)
            
            return {
                "success": True,
                "message": "Organization processed successfully",
                "result": result
            }
        
        # Default response for other webhook types
        return {"message": "Webhook received successfully"}
    
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")

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

@router.post("/generate-organization-summaries")
async def generate_organization_summaries(
    batch_size: int = Query(10, description="Number of organizations to process in each batch"),
    force_regenerate: bool = Query(False, description="Force regenerate summaries even if they exist")
):
    """
    Generate summaries for organizations that don't have them.
    
    Args:
        batch_size (int): Number of organizations to process in each batch
        force_regenerate (bool): Whether to regenerate summaries even if they exist
        
    Returns:
        dict: Results of the processing
    """
    try:
        logger.info(f"Starting organization summary generation. Batch size: {batch_size}, Force regenerate: {force_regenerate}")
        client = get_supabase_client()
        
        # Get organizations without summaries
        query = client.table("organizations").select("*")
        if not force_regenerate:
            query = query.is_("summary", "null")
        
        # Add limit
        query = query.limit(batch_size)
        
        # Execute query
        result = query.execute()
        organizations = result.data
        
        if not organizations:
            return {
                "success": True,
                "message": "No organizations found that need summaries",
                "processed": 0
            }
        
        logger.info(f"Found {len(organizations)} organizations to process")
        
        # Process each organization
        processed = 0
        errors = []
        
        for org in organizations:
            result = await process_organization_summary(org)
            if result["success"]:
                processed += 1
            else:
                errors.append({
                    "organization_id": org.get("id"),
                    "error": result.get("error", "Unknown error")
                })
        
        return {
            "success": True,
            "message": f"Processed {processed} organizations",
            "processed": processed,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        logger.error(f"Error generating organization summaries: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating organization summaries: {str(e)}"
        )

@router.post("/generate-organization-summary/{organization_id}")
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

@router.post("/match-organizations-with-grants")
async def match_organizations_with_grants(
    batch_size: int = Query(10, description="Number of organizations to process in each batch"),
    force_rematch: bool = Query(False, description="Force rematch even if matches exist")
):
    """
    Match organizations with relevant grants.
    
    Args:
        batch_size (int): Number of organizations to process in each batch
        force_rematch (bool): Whether to rematch organizations that already have matches
        
    Returns:
        dict: Results of the matching process
    """
    try:
        logger.info(f"Starting organization-grant matching. Batch size: {batch_size}, Force rematch: {force_rematch}")
        client = get_supabase_client()
        
        # Get organizations to process
        query = client.table("organizations").select("*")
        
        if not force_rematch:
            # First, get organizations that already have matches
            matched_orgs_result = client.table("organization_grant_matches").select("organization_id").execute()
            matched_org_ids = [match["organization_id"] for match in matched_orgs_result.data]
            
            if matched_org_ids:
                # Exclude organizations that already have matches
                query = query.not_.in_("id", matched_org_ids)
        
        # Add limit
        query = query.limit(batch_size)
        
        # Execute query
        result = query.execute()
        organizations = result.data
        
        if not organizations:
            return {
                "success": True,
                "message": "No organizations found that need matching",
                "processed": 0
            }
        
        logger.info(f"Found {len(organizations)} organizations to process")
        
        # Get all grants
        grants_result = client.table("grants").select("*").execute()
        grants = grants_result.data
        
        if not grants:
            return {
                "success": False,
                "message": "No grants found in the database",
                "processed": 0
            }
        
        # Process each organization
        processed = 0
        errors = []
        
        for org in organizations:
            try:
                # Match organization with grants
                matches = await match_organization_with_grants(org, grants)
                
                if matches:
                    # Save matches
                    save_result = await save_organization_grant_matches(org["id"], matches)
                    if save_result.get("success"):
                        processed += 1
                    else:
                        errors.append({
                            "organization_id": org.get("id"),
                            "error": save_result.get("error", "Unknown error")
                        })
                else:
                    logger.info(f"No matches found for organization: {org.get('organization_name')}")
                    
            except Exception as e:
                errors.append({
                    "organization_id": org.get("id"),
                    "error": str(e)
                })
        
        return {
            "success": True,
            "message": f"Processed {processed} organizations",
            "processed": processed,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        logger.error(f"Error matching organizations with grants: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error matching organizations with grants: {str(e)}"
        )

@router.post("/create-grant-match-campaigns")
async def create_grant_match_campaigns(
    batch_size: int = Query(default=5, gt=0),
    force_rematch: bool = Query(default=False)
):
    """
    Create email campaigns for organizations with grant matches.
    """
    try:
        logger.info(f"Starting campaign creation. Batch size: {batch_size}")
        
        # Create Supabase client
        supabase = get_supabase_client()
        if not supabase:
            return {"error": "Failed to create Supabase client"}

        # Get organizations that have matches but no campaigns
        response = supabase.table("organization_grant_matches").select("organization_id").limit(batch_size).execute()
        if len(response.data) == 0:
            return {"message": "No organizations found that need campaigns"}

        results = []
        for org_match in response.data:
            org_id = org_match["organization_id"]
            
            # Get organization details
            org_response = supabase.table("organizations").select("*").eq("id", org_id).execute()
            if not org_response.data:
                logger.error(f"Organization not found: {org_id}")
                continue
            
            organization = org_response.data[0]
            
            # Get all grant matches for this organization
            matches_response = supabase.table("organization_grant_matches").select("*").eq("organization_id", org_id).execute()
            if not matches_response.data:
                logger.error(f"No matches found for organization: {organization.get('organization_name')}")
                continue
                
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

            # Send email via Mailgun
            if organization.get("email"):  # Make sure organization has an email
                result = await send_grant_match_email(
                    organization_data=organization,
                    grant_matches=grant_matches,
                    to_email=organization["email"]
                )
                results.append(result)
            else:
                logger.error(f"No email found for organization: {organization.get('organization_name')}")
                results.append({
                    "success": False,
                    "error": f"No email address found for organization {organization.get('organization_name')}",
                    "organization_id": org_id
                })

        return {"results": results}

    except Exception as e:
        logger.error(f"Error in create_grant_match_campaigns: {str(e)}")
        return {"error": str(e)}

@router.get("/organization-grant-matches/{organization_id}")
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
