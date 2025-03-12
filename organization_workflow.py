import os
import time
import json
import httpx
import asyncio
from datetime import timedelta
from typing import List, Dict, Any, Optional
from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from prefect.context import get_run_context
from app.utils.supabase import get_supabase_client

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8020/api/v1")
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Helper functions
async def make_api_call(
    endpoint: str, 
    method: str = "GET", 
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    retry_count: int = 0
) -> Dict[str, Any]:
    """Make an API call with retries"""
    logger = get_run_logger()
    url = f"{API_BASE_URL}/{endpoint}"
    
    logger.info(f"Making {method} request to {url}")
    if params:
        logger.info(f"Params: {params}")
    if json_data:
        logger.info(f"Data: {json_data}")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if method == "GET":
                response = await client.get(url, params=params)
            elif method == "POST":
                response = await client.post(url, params=params, json=json_data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        if retry_count < MAX_RETRIES:
            logger.info(f"Retrying in {RETRY_DELAY} seconds... (Attempt {retry_count + 1}/{MAX_RETRIES})")
            await asyncio.sleep(RETRY_DELAY)
            return await make_api_call(endpoint, method, params, json_data, retry_count + 1)
        raise
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        if retry_count < MAX_RETRIES:
            logger.info(f"Retrying in {RETRY_DELAY} seconds... (Attempt {retry_count + 1}/{MAX_RETRIES})")
            await asyncio.sleep(RETRY_DELAY)
            return await make_api_call(endpoint, method, params, json_data, retry_count + 1)
        raise

async def wait_for_task_completion(task_id: str, max_wait_time: int = 3600) -> Dict[str, Any]:
    """Wait for a background task to complete"""
    logger = get_run_logger()
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        task_status = await make_api_call(f"organizations/task-status/{task_id}")
        
        if task_status["status"] in ["completed", "failed"]:
            return task_status
        
        progress = task_status.get("progress_percentage", 0)
        logger.info(f"Task {task_id} in progress: {progress}% complete")
        
        # Wait longer as the task progresses (adaptive waiting)
        wait_time = min(30, max(5, 60 - progress))
        await asyncio.sleep(wait_time)
    
    raise TimeoutError(f"Task {task_id} did not complete within {max_wait_time} seconds")

# Prefect tasks
@task(name="Get Organization Data",
      retries=2,
      retry_delay_seconds=30)
async def get_organization_data(organization_name_or_id: str) -> Dict[str, Any]:
    """
    Get organization data by name or ID
    
    Args:
        organization_name_or_id: The name or ID of the organization
        
    Returns:
        Organization data
    """
    logger = get_run_logger()
    logger.info(f"Getting data for organization: {organization_name_or_id}")
    
    # Try to get by ID first
    try:
        # Check if it's a UUID
        if len(organization_name_or_id) == 36 and "-" in organization_name_or_id:
            result = await make_api_call(f"organizations/{organization_name_or_id}")
            if result.get("success", False) and result.get("organization"):
                logger.info(f"Found organization by ID: {organization_name_or_id}")
                return {
                    "success": True,
                    "organization": result.get("organization")
                }
    except Exception as e:
        logger.warning(f"Error getting organization by ID: {str(e)}")
    
    # If not found by ID, search by name
    try:
        # Get all organizations
        all_orgs = await make_api_call("organizations")
        
        # Find the organization by name (case-insensitive)
        org_name_lower = organization_name_or_id.lower()
        for org in all_orgs.get("organizations", []):
            if org.get("organization_name", "").lower() == org_name_lower:
                logger.info(f"Found organization by name: {organization_name_or_id}")
                return {
                    "success": True,
                    "organization": org
                }
        
        logger.error(f"Organization not found: {organization_name_or_id}")
        return {
            "success": False,
            "error": f"Organization not found: {organization_name_or_id}"
        }
    except Exception as e:
        logger.error(f"Error getting organization data: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@task(name="Extract Organization Keywords",
      retries=2,
      retry_delay_seconds=30)
async def extract_organization_keywords(organization_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract keywords from organization data
    
    Args:
        organization_data: Organization data from previous task
        
    Returns:
        Organization keywords
    """
    logger = get_run_logger()
    
    if not organization_data.get("success", False):
        logger.warning("Skipping keyword extraction due to previous task failure")
        return organization_data
    
    organization = organization_data.get("organization", {})
    org_id = organization.get("id")
    
    logger.info(f"Extracting keywords for organization: {org_id}")
    
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
    
    if not org_keywords:
        logger.warning(f"No keywords found for organization {org_id}")
        return {
            "success": False,
            "error": "No keywords found for organization",
            "organization": organization
        }
    
    logger.info(f"Found {len(org_keywords)} keywords: {', '.join(org_keywords)}")
    
    return {
        "success": True,
        "organization": organization,
        "keywords": org_keywords
    }

@task(name="Find Grants by Keywords",
      retries=2,
      retry_delay_seconds=30)
async def find_grants_by_keywords(keywords_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Find grants matching the organization's keywords
    
    Args:
        keywords_data: Organization and keywords data from previous task
        
    Returns:
        Matching grants
    """
    logger = get_run_logger()
    
    if not keywords_data.get("success", False):
        logger.warning("Skipping grant search due to previous task failure")
        return keywords_data
    
    organization = keywords_data.get("organization", {})
    org_id = organization.get("id")
    keywords = keywords_data.get("keywords", [])
    date_range = keywords_data.get("date_range", 30)
    
    logger.info(f"Finding grants for organization {org_id} with keywords: {', '.join(keywords)}")
    logger.info(f"Using date range of {date_range} days")
    
    # Get all grants
    try:
        # Use the correct endpoint to get grants
        all_grants = []
        
        for keyword in keywords:
            grants_result = await make_api_call(
                f"grants/search", 
                params={
                    "keyword": keyword,
                    "date_range": str(date_range),
                    "opp_statuses": "forecasted|posted",
                    "rows": "5000",
                    "sort_by": "openDate|desc"
                }
            )
            
            # Extract grants from the correct location in the response structure
            keyword_grants = []
            
            # Check if the response has the expected structure
            if grants_result.get("data") and grants_result["data"].get("results"):
                # Iterate through results and extract grants
                for result in grants_result["data"]["results"]:
                    if result.get("data"):
                        keyword_grants.extend(result["data"])
            
            logger.info(f"Found {len(keyword_grants)} grants for keyword '{keyword}' using search endpoint with date range {date_range} days")
            
            # Add grants to the list, avoiding duplicates
            for grant in keyword_grants:
                if grant.get("id") not in [g.get("id") for g in all_grants]:
                    all_grants.append(grant)
        
        if not all_grants:
            logger.warning("No grants found in the database")
            return {
                "success": False,
                "error": "No grants found in the database",
                "organization": organization,
                "keywords": keywords,
                "date_range": date_range
            }
        
        logger.info(f"Found {len(all_grants)} total grants in the database")
        
        # Filter grants based on keywords
        matching_grants = []
        for grant in all_grants:
            grant_title = str(grant.get('title', '')).lower()
            grant_desc = str(grant.get('description', '')).lower()
            grant_keywords = str(grant.get('search_keyword', '')).lower()
            
            # Check for keyword matches
            for keyword in keywords:
                if (keyword in grant_title or 
                    keyword in grant_desc or 
                    keyword in grant_keywords):
                    matching_grants.append(grant)
                    logger.debug(f"Grant {grant.get('id')} matched keyword: {keyword}")
                    break  # Once we find a match, no need to check other keywords
        
        logger.info(f"Found {len(matching_grants)} grants matching organization keywords")
        
        return {
            "success": True,
            "organization": organization,
            "keywords": keywords,
            "date_range": date_range,
            "matching_grants": matching_grants,
            "matching_grants_count": len(matching_grants)
        }
    except Exception as e:
        logger.error(f"Error finding grants by keywords: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "organization": organization,
            "keywords": keywords,
            "date_range": date_range
        }

@task(name="Generate Grant Summaries",
      retries=2,
      retry_delay_seconds=30)
async def generate_grant_summaries(grants_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate summaries for matching grants that don't have summaries
    
    Args:
        grants_data: Organization and matching grants data from previous task
        
    Returns:
        Updated grants data with summaries
    """
    logger = get_run_logger()
    
    if not grants_data.get("success", False):
        logger.warning("Skipping grant summary generation due to previous task failure")
        return grants_data
    
    organization = grants_data.get("organization", {})
    matching_grants = grants_data.get("matching_grants", [])
    
    if not matching_grants:
        logger.info("No matching grants to summarize")
        return grants_data
    
    logger.info(f"Checking summaries for {len(matching_grants)} matching grants")
    
    # Find grants without summaries
    grants_without_summaries = [
        grant for grant in matching_grants
        if not grant.get("summary") or not grant.get("summary").strip()
    ]
    
    if not grants_without_summaries:
        logger.info("All matching grants already have summaries")
        return grants_data
    
    logger.info(f"Generating summaries for {len(grants_without_summaries)} grants")
    
    # Get grant IDs
    grant_ids = [grant.get("id") for grant in grants_without_summaries]
    
    # Generate summaries
    try:
        # Process each grant individually since there's no bulk endpoint
        updated_grants = []
        grants_summarized = 0
        
        for grant in matching_grants:
            if grant.get("id") in grant_ids:
                # Generate summary for this grant
                try:
                    logger.info(f"Generating summary for grant {grant.get('id')}")
                    result = await make_api_call(
                        f"grants/generate-summary/{grant.get('id')}", 
                        method="POST"
                    )
                    
                    if result.get("success", False):
                        grants_summarized += 1
                        # Get the updated grant with summary
                        try:
                            # There's no specific endpoint to get a grant by ID, so we'll use the client directly
                            client = get_supabase_client()
                            updated_grant_result = client.table("grants").select("*").eq("id", grant.get("id")).execute()
                            if updated_grant_result.data and len(updated_grant_result.data) > 0:
                                updated_grant = updated_grant_result.data[0]
                            else:
                                updated_grant = grant
                            updated_grants.append(updated_grant)
                        except Exception as e:
                            logger.warning(f"Error getting updated grant {grant.get('id')}: {str(e)}")
                            updated_grants.append(grant)
                    else:
                        logger.warning(f"Failed to generate summary for grant {grant.get('id')}: {result.get('error', 'Unknown error')}")
                        updated_grants.append(grant)
                except Exception as e:
                    logger.warning(f"Error generating summary for grant {grant.get('id')}: {str(e)}")
                    updated_grants.append(grant)
            else:
                updated_grants.append(grant)
        
        logger.info(f"Successfully generated summaries for {grants_summarized} grants")
        
        return {
            "success": True,
            "organization": organization,
            "keywords": grants_data.get("keywords", []),
            "date_range": grants_data.get("date_range", 30),
            "matching_grants": updated_grants,
            "matching_grants_count": len(updated_grants),
            "grants_summarized": grants_summarized
        }
    except Exception as e:
        logger.error(f"Error generating grant summaries: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "organization": organization,
            "keywords": grants_data.get("keywords", []),
            "date_range": grants_data.get("date_range", 30),
            "matching_grants": matching_grants,
            "matching_grants_count": len(matching_grants)
        }

@task(name="Match Organization with Grants",
      retries=2,
      retry_delay_seconds=30)
async def match_organization_with_grants(grants_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Match organization with grants
    
    Args:
        grants_data: Organization and matching grants data from previous task
        
    Returns:
        Matching results
    """
    logger = get_run_logger()
    
    if not grants_data.get("success", False):
        logger.warning("Skipping organization-grant matching due to previous task failure")
        return grants_data
    
    organization = grants_data.get("organization", {})
    org_id = organization.get("id")
    matching_grants = grants_data.get("matching_grants", [])
    
    if not matching_grants:
        logger.info("No matching grants to process")
        return grants_data
    
    logger.info(f"Matching organization {org_id} with {len(matching_grants)} grants")
    
    try:
        # Start the matching process
        result = await make_api_call(
            f"organizations/match-with-grants/{org_id}", 
            method="POST",
            params={"force_rematch": "true", "run_in_background": "true"}
        )
        
        if "task_id" in result:
            task_id = result["task_id"]
            logger.info(f"Waiting for matching task {task_id} to complete")
            
            # Wait for the task to complete
            task_result = await wait_for_task_completion(task_id)
            
            if task_result["status"] == "completed":
                logger.info(f"Successfully matched organization {org_id} with grants")
                
                # Get the matches
                matches_result = await make_api_call(f"organizations/grant-matches/{org_id}")
                
                return {
                    "success": True,
                    "organization": organization,
                    "keywords": grants_data.get("keywords", []),
                    "date_range": grants_data.get("date_range", 30),
                    "matching_grants": matching_grants,
                    "matching_grants_count": len(matching_grants),
                    "grants_summarized": grants_data.get("grants_summarized", 0),
                    "matches": matches_result.get("matches", []),
                    "matches_count": len(matches_result.get("matches", [])),
                    "high_quality_matches_count": sum(1 for match in matches_result.get("matches", []) 
                                                    if float(match.get("match_score", 0)) >= 0.5)
                }
            else:
                logger.error(f"Failed to match organization {org_id}: {task_result.get('error', 'Unknown error')}")
                return {
                    "success": False,
                    "error": task_result.get("error", "Unknown error"),
                    "organization": organization,
                    "keywords": grants_data.get("keywords", []),
                    "date_range": grants_data.get("date_range", 30),
                    "matching_grants": matching_grants,
                    "matching_grants_count": len(matching_grants),
                    "grants_summarized": grants_data.get("grants_summarized", 0)
                }
        
        return {
            "success": result.get("success", False),
            "organization": organization,
            "keywords": grants_data.get("keywords", []),
            "date_range": grants_data.get("date_range", 30),
            "matching_grants": matching_grants,
            "matching_grants_count": len(matching_grants),
            "grants_summarized": grants_data.get("grants_summarized", 0),
            "matches_count": result.get("total_matches_count", 0),
            "high_quality_matches_count": result.get("high_quality_matches_count", 0)
        }
    except Exception as e:
        logger.error(f"Error matching organization with grants: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "organization": organization,
            "keywords": grants_data.get("keywords", []),
            "date_range": grants_data.get("date_range", 30),
            "matching_grants": matching_grants,
            "matching_grants_count": len(matching_grants),
            "grants_summarized": grants_data.get("grants_summarized", 0)
        }

@task(name="Create Email Campaign",
      retries=2,
      retry_delay_seconds=30)
async def create_email_campaign(matching_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create email campaign for organization with grant matches
    
    Args:
        matching_result: Organization and matching results from previous task
        
    Returns:
        Email campaign result
    """
    logger = get_run_logger()
    
    if not matching_result.get("success", False):
        logger.warning("Skipping email campaign creation due to previous task failure")
        return matching_result
    
    organization = matching_result.get("organization", {})
    org_id = organization.get("id")
    matches = matching_result.get("matches", [])
    
    if not matches:
        logger.info("No matches to include in email campaign")
        return matching_result
    
    logger.info(f"Creating email campaign for organization {org_id} with {len(matches)} matches")
    
    try:
        # Send email with matches
        email_result = await make_api_call(
            "email/send-grant-matches", 
            method="POST",
            json_data={
                "organization_id": org_id,
                "matches": matches
            }
        )
        
        logger.info(f"Email campaign creation result: {email_result}")
        
        return {
            "success": email_result.get("success", False),
            "organization": organization,
            "keywords": matching_result.get("keywords", []),
            "date_range": matching_result.get("date_range", 30),
            "matching_grants_count": matching_result.get("matching_grants_count", 0),
            "grants_summarized": matching_result.get("grants_summarized", 0),
            "matches_count": matching_result.get("matches_count", 0),
            "high_quality_matches_count": matching_result.get("high_quality_matches_count", 0),
            "email_sent": email_result.get("email_sent", False),
            "email_result": email_result
        }
    except Exception as e:
        logger.error(f"Error creating email campaign: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "organization": organization,
            "keywords": matching_result.get("keywords", []),
            "date_range": matching_result.get("date_range", 30),
            "matching_grants_count": matching_result.get("matching_grants_count", 0),
            "grants_summarized": matching_result.get("grants_summarized", 0),
            "matches_count": matching_result.get("matches_count", 0),
            "high_quality_matches_count": matching_result.get("high_quality_matches_count", 0)
        }

# Main Prefect flow
@flow(name="Organization Grant Processing Pipeline")
async def organization_grant_processing_pipeline(
    organization_name_or_id: str,
    date_range: int = 30
):
    """
    Process a specific organization through the grant matching pipeline:
    1. Get organization data
    2. Extract organization keywords
    3. Find grants matching the keywords
    4. Generate summaries for matching grants
    5. Match organization with grants
    6. Create email campaign
    
    Args:
        organization_name_or_id: The name or ID of the organization to process
        date_range: Number of days to look back for grants (default: 30)
    """
    logger = get_run_logger()
    logger.info(f"Starting organization grant processing pipeline for: {organization_name_or_id}")
    logger.info(f"Using date range of {date_range} days")
    
    # Step 1: Get organization data
    org_data = await get_organization_data(organization_name_or_id)
    
    # Step 2: Extract organization keywords
    keywords_data = await extract_organization_keywords(org_data)
    
    # Step 3: Find grants matching the keywords
    keywords_data["date_range"] = date_range  # Add date_range to the data
    grants_data = await find_grants_by_keywords(keywords_data)
    
    # Step 4: Generate summaries for matching grants
    summaries_data = await generate_grant_summaries(grants_data)
    
    # Step 5: Match organization with grants
    matching_result = await match_organization_with_grants(summaries_data)
    
    # Step 6: Create email campaign
    email_result = await create_email_campaign(matching_result)
    
    # Compile final results
    final_result = {
        "organization_name": email_result.get("organization", {}).get("organization_name", "Unknown"),
        "organization_id": email_result.get("organization", {}).get("id", "Unknown"),
        "keywords_count": len(email_result.get("keywords", [])),
        "date_range": date_range,
        "matching_grants_count": email_result.get("matching_grants_count", 0),
        "grants_summarized": email_result.get("grants_summarized", 0),
        "matches_count": email_result.get("matches_count", 0),
        "high_quality_matches_count": email_result.get("high_quality_matches_count", 0),
        "email_sent": email_result.get("email_sent", False)
    }
    
    logger.info(f"Organization grant processing pipeline completed: {json.dumps(final_result, indent=2)}")
    return final_result

# Entry point for running the flow directly
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python organization_workflow.py <organization_name_or_id> [date_range]")
        sys.exit(1)
    
    organization_name_or_id = sys.argv[1]
    date_range = 30  # Default to 30 days
    
    # Check if date_range is provided
    if len(sys.argv) >= 3:
        try:
            date_range = int(sys.argv[2])
        except ValueError:
            print(f"Error: date_range must be an integer. Using default value of {date_range} days.")
    
    print(f"Processing organization: {organization_name_or_id}")
    print(f"Using date range: {date_range} days")
    
    asyncio.run(organization_grant_processing_pipeline(organization_name_or_id, date_range)) 