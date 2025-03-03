from fastapi import APIRouter, Depends, HTTPException, Request, Header, Query
import json
import hmac
import hashlib
import logging
from app.utils.supabase import get_supabase_client
from app.core.config import settings
from app.utils.organization_utils import process_new_organization
from app.utils.organization_grant_matcher import match_organization_with_grants, save_organization_grant_matches

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
            try:
                # Generate and save summary
                result = await process_new_organization(org)
                if result.get("success"):
                    processed += 1
                else:
                    errors.append({
                        "organization_id": org.get("id"),
                        "error": result.get("error", "Unknown error")
                    })
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
        logger.error(f"Error generating organization summaries: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating organization summaries: {str(e)}"
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
