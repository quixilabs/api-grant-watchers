import logging
import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from app.utils.supabase import get_supabase_client, get_grants_data, get_organization_grant_matches
from app.utils.organization_utils import update_organization_summary
from app.utils.organization_grant_matcher import match_organization_with_grants, save_organization_grant_matches, background_match_organization_with_grants
from app.utils.resend_client import send_grant_match_email as resend_send_grant_match_email, generate_email_content, send_grant_match_email_via_smtp
from app.utils.task_manager import create_task, get_task_status, get_organization_tasks, run_background_task

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

async def process_organization_summary(organization: dict) -> dict:
    """
    Process a single organization to generate a summary.
    
    Args:
        organization (dict): Organization data
        
    Returns:
        dict: Result of the summary generation
    """
    try:
        # Generate prompt for the summary
        prompt = f"""
        Organization Information:
        Name: {organization.get('organization_name', '')}
        Type: {organization.get('organization_type', '')}
        Profile: {organization.get('organization_profile', '')}
        Grant Interests: {organization.get('grant_interests', '')}
        
        Based on the information above, please generate a summary of this organization with the following components:
        1. Mission: A brief statement of what the organization aims to achieve.
        2. Expertise: Key areas of knowledge and experience within the organization.
        3. Funding Interests: What kind of grant opportunities would be most relevant to this organization.
        4. Notable Aspects: Anything that makes this organization unique or particularly qualified for grants.
        
        Format the response as a JSON object with the following structure:
        {{
            "mission": "Brief statement of the organization's mission",
            "expertise": ["Area 1", "Area 2", "Area 3"],
            "funding_interests": ["Interest 1", "Interest 2"],
            "notable_aspects": ["Notable aspect 1", "Notable aspect 2"]
        }}
        """
        
        # Generate summary using DeepSeek AI
        logger.debug(f"Generating summary for organization: {organization.get('organization_name')}")
        from app.utils.deepseek_client import generate_with_deepseek
        response = await generate_with_deepseek(prompt)
        
        # Parse the JSON response
        summary = json.loads(response)
        
        # Update the organization with the summary
        organization_id = organization.get('id')
        await update_organization_summary(organization_id, summary)
        
        return {
            "success": True,
            "message": "Successfully generated organization summary",
            "organization_id": organization_id,
            "result": summary
        }
    except Exception as e:
        logger.error(f"Error generating organization summary: {str(e)}")
        raise

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
    Saves all matches to the database immediately as they are generated.
    Only includes match_reason for matches with score >= 0.5.
    
    Args:
        organization (dict): Organization data
        grants (list): List of grants to match against
        
    Returns:
        dict: Result of the matching process
    """
    try:
        # Match organization with grants (matches are saved to the database immediately)
        matches = await match_organization_with_grants(organization, grants)
        
        if matches:
            # Count high-quality matches (score >= 0.5) in the new matches
            high_quality_matches = sum(1 for match in matches if float(match.get("match_score", 0)) >= 0.5)
            low_quality_matches = len(matches) - high_quality_matches
            
            # Get total matches count from the database
            client = get_supabase_client()
            total_matches_result = client.table("organization_grant_matches").select("*").eq("organization_id", organization["id"]).execute()
            total_matches = len(total_matches_result.data)
            
            # Count total high-quality matches
            total_high_quality_matches = sum(1 for match in total_matches_result.data if float(match.get("match_score", 0)) >= 0.5)
            
            return {
                "success": True,
                "organization_id": organization.get("id"),
                "new_matches_count": len(matches),
                "total_matches_count": total_matches,
                "high_quality_matches": high_quality_matches,
                "total_high_quality_matches": total_high_quality_matches,
                "low_quality_matches": low_quality_matches
            }
        else:
            # Get total matches count from the database
            client = get_supabase_client()
            total_matches_result = client.table("organization_grant_matches").select("*").eq("organization_id", organization["id"]).execute()
            total_matches = len(total_matches_result.data)
            
            # Count total high-quality matches
            total_high_quality_matches = sum(1 for match in total_matches_result.data if float(match.get("match_score", 0)) >= 0.5)
            
            return {
                "success": True,
                "organization_id": organization.get("id"),
                "new_matches_count": 0,
                "total_matches_count": total_matches,
                "high_quality_matches": 0,
                "total_high_quality_matches": total_high_quality_matches,
                "low_quality_matches": 0,
                "message": "No new matching grants found"
            }
    except Exception as e:
        logger.error(f"Error in organization grant matching: {str(e)}")
        return {
            "success": False,
            "organization_id": organization.get("id"),
            "error": str(e)
        }

@router.post("/match-with-grants/{organization_id}")
async def match_organization_with_grants_by_id(
    organization_id: str,
    background_tasks: BackgroundTasks,
    force_rematch: bool = Query(False, description="Force rematch even if matches exist"),
    run_in_background: bool = Query(True, description="Run the matching process in the background")
):
    """
    Match a specific organization with relevant grants.
    Only considers grants that have keywords matching the organization's interests.
    Saves all matches to the database regardless of score, but only includes match_reason for matches with score >= 0.5.
    If matches already exist, only processes grants that haven't been matched yet.
    
    Args:
        organization_id (str): ID of the organization to process
        background_tasks: FastAPI BackgroundTasks
        force_rematch (bool): Whether to rematch even if matches exist
        run_in_background (bool): Whether to run the matching process in the background
        
    Returns:
        dict: Result of the matching process or task information
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
        
        # Extract organization interests/keywords
        org_interests = organization.get('grant_interests', '')
        org_keywords = []
        
        if isinstance(org_interests, list):
            # If it's already a list, use it directly
            for interest in org_interests:
                if isinstance(interest, str):
                    org_keywords.append(interest.strip().lower())
                else:
                    # Handle case where list items might not be strings
                    org_keywords.append(str(interest).strip().lower())
        elif isinstance(org_interests, str):
            # If it's a string, split by commas
            org_keywords = [keyword.strip().lower() for keyword in org_interests.split(',') if keyword.strip()]
        
        if org_keywords:
            logger.info(f"Organization keywords: {org_keywords}")
        else:
            logger.warning("Organization has no grant interests specified. Matching may be less accurate.")
        
        # Get all grants
        grants_result = client.table("grants").select("*").execute()
        all_grants = grants_result.data
        
        if not all_grants:
            raise HTTPException(
                status_code=500,
                detail="No grants found in the database"
            )
        
        logger.debug(f"Fetched {len(all_grants)} grants from database")
        
        # Get existing matches for this organization
        existing_matches = []
        if not force_rematch:
            matches_result = client.table("organization_grant_matches").select("*").eq("organization_id", organization_id).execute()
            existing_matches = matches_result.data
            
            # Count high-quality matches (score >= 0.5)
            high_quality_matches = sum(1 for match in existing_matches if float(match.get("match_score", 0)) >= 0.5)
            
            logger.info(f"Found {len(existing_matches)} existing matches, with {high_quality_matches} high-quality matches")
            
            # If force_rematch is False and there are existing matches, only process unmatched grants
            if existing_matches:
                # Get IDs of grants that have already been matched
                matched_grant_ids = {match.get("grant_id") for match in existing_matches}
                logger.info(f"Already matched with {len(matched_grant_ids)} grants")
            else:
                matched_grant_ids = set()
                logger.info("No existing matches found, will process all grants")
        else:
            # If force_rematch is True, we'll process all grants
            matched_grant_ids = set()
            logger.info("Force rematch is enabled, will process all grants")
        
        # Pre-filter grants based on keywords if organization has keywords
        filtered_grants = []
        if org_keywords:
            for grant in all_grants:
                grant_id = grant.get('id')
                
                # Skip grants that have already been matched unless force_rematch is True
                if not force_rematch and grant_id in matched_grant_ids:
                    logger.debug(f"Skipping grant {grant_id} as it's already matched")
                    continue
                
                # Check if any organization keyword is in the grant title, description, or search_keyword
                grant_title = str(grant.get('title', '')).lower()
                grant_desc = str(grant.get('description', '')).lower()
                grant_keywords = str(grant.get('search_keyword', '')).lower()
                
                # Check for keyword matches
                for keyword in org_keywords:
                    if (keyword in grant_title or 
                        keyword in grant_desc or 
                        keyword in grant_keywords):
                        filtered_grants.append(grant)
                        logger.debug(f"Grant {grant_id} matched keyword: {keyword}")
                        break  # Once we find a match, no need to check other keywords
            
            logger.info(f"Pre-filtered grants from {len(all_grants)} to {len(filtered_grants)} based on keywords and existing matches")
        else:
            # If no keywords, don't process any grants
            logger.warning(f"Organization {organization_id} has no keywords specified. Cannot match without common keywords.")
            return {
                "success": False,
                "message": "Organization has no keywords specified. Cannot match without common keywords.",
                "organization_id": organization_id,
                "existing_matches_count": len(existing_matches),
                "new_matches_count": 0,
                "total_matches_count": len(existing_matches)
            }
        
        if not filtered_grants:
            return {
                "success": True,
                "message": "No new grants found matching organization keywords",
                "organization_id": organization_id,
                "existing_matches_count": len(existing_matches),
                "new_matches_count": 0,
                "total_matches_count": len(existing_matches),
                "high_quality_matches_count": sum(1 for match in existing_matches if float(match.get("match_score", 0)) >= 0.5)
            }
        
        # If running in background, create a task and return task ID
        if run_in_background:
            # Create a task
            task_id = create_task("grant_matching", organization_id)
            
            # Start the background task
            background_tasks.add_task(
                run_background_task,
                task_id,
                organization_id,
                background_match_organization_with_grants,
                organization,
                filtered_grants
            )
            
            return {
                "success": True,
                "message": "Grant matching task started in the background",
                "organization_id": organization_id,
                "task_id": task_id,
                "grants_to_process": len(filtered_grants),
                "existing_matches_count": len(existing_matches),
                "status_url": f"organizations/task-status/{task_id}"
            }
        
        # If not running in background, process synchronously
        result = await process_organization_grant_matching(organization, filtered_grants)
        
        if result["success"]:
            return {
                "success": True,
                "message": "Successfully matched organization with grants",
                "organization_id": organization_id,
                "existing_matches_count": result.get("existing_matches_count", 0),
                "new_matches_count": result.get("new_matches_count", 0),
                "total_matches_count": result.get("total_matches_count", 0),
                "high_quality_matches_count": result.get("total_high_quality_matches", 0),
                "low_quality_matches_count": result.get("low_quality_matches", 0)
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

@router.get("/task-status/{task_id}")
async def get_matching_task_status(task_id: str):
    """
    Get the status of a grant matching task
    
    Args:
        task_id (str): ID of the task
        
    Returns:
        dict: Task status
    """
    status = get_task_status(task_id)
    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"Task not found with ID: {task_id}"
        )
    
    return status

@router.get("/tasks/{organization_id}")
async def get_organization_matching_tasks(organization_id: str):
    """
    Get all grant matching tasks for an organization
    
    Args:
        organization_id (str): ID of the organization
        
    Returns:
        dict: List of task statuses
    """
    tasks = get_organization_tasks(organization_id)
    
    return {
        "success": True,
        "organization_id": organization_id,
        "tasks_count": len(tasks),
        "tasks": tasks
    }

@router.get("/grant-matches/{organization_id}")
async def get_organization_grant_matches(
    organization_id: str,
    min_score: float = Query(0.5, description="Minimum match score to include (0.0 to 1.0)")
):
    """
    Get all grant matches for a specific organization.
    
    Args:
        organization_id (str): ID of the organization
        min_score (float): Minimum match score to include (default: 0.5)
        
    Returns:
        dict: Organization and its grant matches
    """
    try:
        logger.info(f"Fetching grant matches for organization {organization_id} with min_score {min_score}")
        
        # Get the organization
        client = get_supabase_client()
        org_result = client.table("organizations").select("*").eq("id", organization_id).execute()
        
        if not org_result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Organization not found with ID: {organization_id}"
            )
        
        organization = org_result.data[0]
        
        # Get the grant matches
        matches_result = client.table("organization_grant_matches").select("*").eq("organization_id", organization_id).gte("match_score", min_score).order("match_score", desc=True).execute()
        
        if not matches_result.data:
            return {
                "organization": {
                    "id": organization["id"],
                    "name": organization.get("organization_name", "N/A"),
                    "email": organization.get("email", "N/A"),
                    "description": organization.get("organization_profile", "N/A")
                },
                "matches": [],
                "html_content": "<div><p>No matching grants found for this organization.</p></div>",
                "total_matches": 0,
                "min_score": min_score
            }
        
        # Process the matches
        grant_matches = []
        for match in matches_result.data:
            grant_id = match.get("grant_id")
            grant_result = client.table("grants").select("*").eq("id", grant_id).execute()
            
            if grant_result.data:
                grant = grant_result.data[0]
                grant_matches.append({
                    "grant": grant,
                    "match_score": match.get("match_score"),
                    "match_reason": match.get("match_reason", "")
                })
        
        # Generate HTML content
        html_content = generate_email_content(organization, grant_matches)
        
        # Format the response
        response_data = {
            "organization": {
                "id": organization["id"],
                "name": organization.get("organization_name", "N/A"),
                "email": organization.get("email", "N/A"),
                "description": organization.get("organization_profile", "N/A")
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
            "total_matches": len(grant_matches),
            "min_score": min_score
        }

        return response_data

    except Exception as e:
        logger.error(f"Error in get_organization_grant_matches: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{organization_id}")
async def get_organization_by_id(organization_id: str):
    """
    Get a specific organization by ID.
    
    Args:
        organization_id (str): ID of the organization to retrieve
        
    Returns:
        dict: Organization data
    """
    try:
        logger.info(f"Fetching organization with ID: {organization_id}")
        client = get_supabase_client()
        
        # Query the organization by ID
        query = client.table("organizations").select("*").eq("id", organization_id)
        result = query.execute()
        
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Organization not found with ID: {organization_id}"
            )
        
        organization = result.data[0]
        logger.info(f"Successfully retrieved organization: {organization.get('organization_name')}")
        
        return {
            "success": True,
            "message": "Successfully retrieved organization",
            "organization": organization
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching organization: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching organization: {str(e)}"
        )

@router.get("")
async def get_all_organizations(
    limit: int = Query(100, description="Maximum number of organizations to return"),
    offset: int = Query(0, description="Number of organizations to skip")
):
    """
    Get all organizations from the database.
    
    Args:
        limit (int): Maximum number of organizations to return
        offset (int): Number of organizations to skip
        
    Returns:
        dict: List of organizations and metadata
    """
    try:
        logger.info(f"Fetching all organizations (limit: {limit}, offset: {offset})")
        client = get_supabase_client()
        
        # Get total count first
        count_result = client.table("organizations").select("count", count="exact").execute()
        total_count = count_result.count if hasattr(count_result, 'count') else 0
        
        # Get organizations with pagination
        query = client.table("organizations").select("*").range(offset, offset + limit - 1)
        result = query.execute()
        
        if not result.data:
            return {
                "success": True,
                "message": "No organizations found",
                "organizations": [],
                "total_count": 0,
                "limit": limit,
                "offset": offset
            }
        
        logger.info(f"Found {len(result.data)} organizations")
        
        return {
            "success": True,
            "message": f"Successfully retrieved {len(result.data)} organizations",
            "organizations": result.data,
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }
            
    except Exception as e:
        logger.error(f"Error fetching organizations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching organizations: {str(e)}"
        )

@router.post("/send-grant-match-email/{organization_id}")
async def send_organization_grant_match_email(
    organization_id: str,
    min_score: float = Query(0.5, description="Minimum match score to include (0.0 to 1.0)")
):
    """
    Send an email to a specific organization with their matched grants.
    
    Args:
        organization_id (str): ID of the organization to send email to
        min_score (float): Minimum match score to include (default: 0.5)
        
    Returns:
        dict: Result of the email sending operation
    """
    try:
        logger.info(f"Preparing to send grant match email for organization {organization_id} with min_score {min_score}")
        
        # Get the organization
        client = get_supabase_client()
        org_result = client.table("organizations").select("*").eq("id", organization_id).execute()
        
        if not org_result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Organization not found with ID: {organization_id}"
            )
        
        organization = org_result.data[0]
        
        # Check if organization has an email address
        if not organization.get("email"):
            return {
                "success": False,
                "message": f"No email address found for organization: {organization.get('organization_name', 'Unknown')}",
                "organization_id": organization_id
            }
        
        # Get the grant matches
        matches_result = client.table("organization_grant_matches").select("*").eq("organization_id", organization_id).gte("match_score", min_score).order("match_score", desc=True).execute()
        
        if not matches_result.data:
            return {
                "success": False,
                "message": "No matching grants found for this organization",
                "organization_id": organization_id
            }
        
        # Process the matches
        grant_matches = []
        for match in matches_result.data:
            grant_id = match.get("grant_id")
            grant_result = client.table("grants").select("*").eq("id", grant_id).execute()
            
            if grant_result.data:
                grant = grant_result.data[0]
                grant_matches.append({
                    "grant": grant,
                    "match_score": match.get("match_score"),
                    "match_reason": match.get("match_reason", "")
                })
        
        if not grant_matches:
            return {
                "success": False,
                "message": "No valid grant matches found for this organization",
                "organization_id": organization_id
            }
        
        # Send the email
        result = await resend_send_grant_match_email(
            organization_data=organization,
            grant_matches=grant_matches,
            to_email=organization["email"]
        )
        
        if result.get("success"):
            return {
                "success": True,
                "message": f"Successfully sent grant match email to {organization.get('organization_name')}",
                "organization_id": organization_id,
                "email": organization.get("email"),
                "grants_count": len(grant_matches),
                "message_id": result.get("message_id")
            }
        else:
            return {
                "success": False,
                "message": f"Failed to send email: {result.get('error', 'Unknown error')}",
                "organization_id": organization_id
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending grant match email: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error sending grant match email: {str(e)}"
        )

@router.get("/without-summaries")
async def get_organizations_without_summaries(
    limit: int = Query(100, description="Maximum number of organizations to return"),
    offset: int = Query(0, description="Number of organizations to skip")
):
    """
    Get all organizations that don't have a summary.
    
    Args:
        limit (int): Maximum number of organizations to return
        offset (int): Number of organizations to skip
        
    Returns:
        dict: List of organizations without summaries and metadata
    """
    try:
        logger.info(f"Fetching organizations without summaries (limit: {limit}, offset: {offset})")
        client = get_supabase_client()
        
        # Get total count of organizations without summaries
        count_query = client.table("organizations").select("count", count="exact").is_("summary", "null")
        count_result = count_query.execute()
        total_count = count_result.count if hasattr(count_result, 'count') else 0
        
        # Get organizations without summaries with pagination
        query = client.table("organizations").select("*").is_("summary", "null").range(offset, offset + limit - 1)
        result = query.execute()
        
        if not result.data:
            return {
                "success": True,
                "message": "No organizations without summaries found",
                "organizations": [],
                "total_count": 0,
                "limit": limit,
                "offset": offset
            }
        
        logger.info(f"Found {len(result.data)} organizations without summaries")
        
        return {
            "success": True,
            "message": f"Successfully retrieved {len(result.data)} organizations without summaries",
            "organizations": result.data,
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }
            
    except Exception as e:
        logger.error(f"Error fetching organizations without summaries: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching organizations without summaries: {str(e)}"
        )

@router.post("/send-grant-match-email-smtp/{organization_id}")
async def send_organization_grant_match_email_smtp(
    organization_id: str,
    min_score: float = Query(0.5, description="Minimum match score to include (0.0 to 1.0)")
):
    """
    Send an email to a specific organization with their matched grants using SMTP.
    This endpoint is useful for testing before domain verification is complete in Resend.
    
    Note: During testing, all emails will be sent to charlie@quixilabs.com regardless of 
    the organization's actual email address. The original recipient will be noted in the subject line.
    
    Args:
        organization_id (str): ID of the organization to send email to
        min_score (float): Minimum match score to include (default: 0.5)
        
    Returns:
        dict: Result of the email sending operation
    """
    try:
        logger.info(f"Preparing to send grant match email via SMTP for organization {organization_id} with min_score {min_score}")
        
        # Get the organization
        client = get_supabase_client()
        org_result = client.table("organizations").select("*").eq("id", organization_id).execute()
        
        if not org_result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Organization not found with ID: {organization_id}"
            )
        
        organization = org_result.data[0]
        
        # Check if organization has an email address
        if not organization.get("email"):
            return {
                "success": False,
                "message": f"No email address found for organization: {organization.get('organization_name', 'Unknown')}",
                "organization_id": organization_id
            }
        
        # Get the grant matches
        matches_result = client.table("organization_grant_matches").select("*").eq("organization_id", organization_id).gte("match_score", min_score).order("match_score", desc=True).execute()
        
        if not matches_result.data:
            return {
                "success": False,
                "message": "No matching grants found for this organization",
                "organization_id": organization_id
            }
        
        # Process the matches
        grant_matches = []
        for match in matches_result.data:
            grant_id = match.get("grant_id")
            grant_result = client.table("grants").select("*").eq("id", grant_id).execute()
            
            if grant_result.data:
                grant = grant_result.data[0]
                grant_matches.append({
                    "grant": grant,
                    "match_score": match.get("match_score"),
                    "match_reason": match.get("match_reason", "")
                })
        
        if not grant_matches:
            return {
                "success": False,
                "message": "No valid grant matches found for this organization",
                "organization_id": organization_id
            }
        
        # Send the email using SMTP
        result = await send_grant_match_email_via_smtp(
            organization_data=organization,
            grant_matches=grant_matches,
            to_email=organization["email"]
        )
        
        if result.get("success"):
            return {
                "success": True,
                "message": f"Successfully sent grant match email via SMTP to charlie@quixilabs.com (original recipient: {organization.get('email')})",
                "organization_id": organization_id,
                "email": organization.get("email"),
                "grants_count": len(grant_matches),
                "note": "During testing, all emails are sent to charlie@quixilabs.com regardless of the intended recipient"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to send email via SMTP: {result.get('error', 'Unknown error')}",
                "organization_id": organization_id
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending grant match email via SMTP: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error sending grant match email via SMTP: {str(e)}"
        ) 