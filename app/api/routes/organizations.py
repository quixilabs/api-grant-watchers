from fastapi import APIRouter, HTTPException, Query
import logging
from app.utils.supabase import get_supabase_client
from app.utils.organization_utils import process_new_organization

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