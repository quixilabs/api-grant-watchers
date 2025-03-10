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
@task(name="Find New Grants", 
      retries=2, 
      retry_delay_seconds=30,
      cache_key_fn=task_input_hash,
      cache_expiration=timedelta(hours=1))
async def find_new_grants(date_range: int = 1) -> Dict[str, Any]:
    """Find new grants from the API"""
    logger = get_run_logger()
    logger.info(f"Finding new grants from the last {date_range} days")
    
    result = await make_api_call(
        "keywords/check-new-grants", 
        method="POST",
        params={"date_range": str(date_range)}
    )
    
    logger.info(f"Found {result.get('count', 0)} new grants")
    return result

@task(name="Add Summaries to New Grants",
      retries=2,
      retry_delay_seconds=30)
async def add_summaries_to_grants(grants_result: Dict[str, Any]) -> Dict[str, Any]:
    """Add summaries to new grants"""
    logger = get_run_logger()
    
    if not grants_result.get("success", False):
        logger.warning("Skipping grant summaries due to previous task failure")
        return {"success": False, "message": "Previous task failed"}
    
    new_grants_count = grants_result.get("count", 0)
    if new_grants_count == 0:
        logger.info("No new grants to summarize")
        return {"success": True, "message": "No new grants to summarize"}
    
    logger.info(f"Adding summaries to {new_grants_count} new grants")
    
    # Start the background task for generating summaries
    result = await make_api_call(
        "grants/generate-summaries", 
        method="POST",
        params={"force_regenerate": "false"}
    )
    
    if "task_id" in result:
        task_id = result["task_id"]
        logger.info(f"Waiting for grant summary generation task {task_id} to complete")
        
        # Wait for the task to complete
        task_result = await wait_for_task_completion(task_id)
        
        if task_result["status"] == "completed":
            logger.info(f"Successfully generated summaries for grants")
            return {"success": True, "grants_summarized": task_result.get("processed_items", 0)}
        else:
            logger.error(f"Failed to generate summaries: {task_result.get('error', 'Unknown error')}")
            return {"success": False, "error": task_result.get("error", "Unknown error")}
    
    return result

@task(name="Add Summaries to New Organizations",
      retries=2,
      retry_delay_seconds=30)
async def add_summaries_to_organizations() -> Dict[str, Any]:
    """Add summaries to new organizations"""
    logger = get_run_logger()
    logger.info("Finding organizations without summaries")
    
    # Get organizations without summaries
    orgs_result = await make_api_call("organizations/without-summaries")
    
    orgs_count = len(orgs_result.get("organizations", []))
    if orgs_count == 0:
        logger.info("No organizations need summaries")
        return {"success": True, "message": "No organizations need summaries"}
    
    logger.info(f"Adding summaries to {orgs_count} organizations")
    
    # Process each organization
    results = []
    for org in orgs_result.get("organizations", []):
        org_id = org.get("id")
        logger.info(f"Generating summary for organization {org_id}")
        
        try:
            result = await make_api_call(
                f"organizations/generate-summary/{org_id}", 
                method="POST"
            )
            results.append({"organization_id": org_id, "success": result.get("success", False)})
        except Exception as e:
            logger.error(f"Error generating summary for organization {org_id}: {str(e)}")
            results.append({"organization_id": org_id, "success": False, "error": str(e)})
    
    success_count = sum(1 for r in results if r.get("success", False))
    logger.info(f"Successfully generated summaries for {success_count}/{orgs_count} organizations")
    
    return {
        "success": True,
        "organizations_processed": orgs_count,
        "organizations_summarized": success_count,
        "results": results
    }

@task(name="Match Organizations with Grants",
      retries=2,
      retry_delay_seconds=30)
async def match_organizations_with_grants() -> Dict[str, Any]:
    """Match organizations with grants"""
    logger = get_run_logger()
    logger.info("Finding organizations to match with grants")
    
    # Get organizations to match
    orgs_result = await make_api_call("organizations")
    
    orgs = orgs_result.get("organizations", [])
    orgs_count = len(orgs)
    if orgs_count == 0:
        logger.info("No organizations to match")
        return {"success": True, "message": "No organizations to match"}
    
    logger.info(f"Matching {orgs_count} organizations with grants")
    
    # Process each organization
    results = []
    for org in orgs:
        org_id = org.get("id")
        logger.info(f"Matching organization {org_id} with grants")
        
        try:
            # Start the background task for matching
            result = await make_api_call(
                f"organizations/match-with-grants/{org_id}", 
                method="POST",
                params={"force_rematch": "false", "run_in_background": "true"}
            )
            
            if "task_id" in result:
                task_id = result["task_id"]
                logger.info(f"Waiting for matching task {task_id} to complete")
                
                # Wait for the task to complete
                task_result = await wait_for_task_completion(task_id)
                
                if task_result["status"] == "completed":
                    logger.info(f"Successfully matched organization {org_id} with grants")
                    results.append({
                        "organization_id": org_id, 
                        "success": True,
                        "matches_count": task_result.get("matched_items", 0)
                    })
                else:
                    logger.error(f"Failed to match organization {org_id}: {task_result.get('error', 'Unknown error')}")
                    results.append({
                        "organization_id": org_id, 
                        "success": False, 
                        "error": task_result.get("error", "Unknown error")
                    })
            else:
                results.append({
                    "organization_id": org_id, 
                    "success": result.get("success", False),
                    "matches_count": result.get("matches_count", 0)
                })
        except Exception as e:
            logger.error(f"Error matching organization {org_id}: {str(e)}")
            results.append({"organization_id": org_id, "success": False, "error": str(e)})
    
    success_count = sum(1 for r in results if r.get("success", False))
    logger.info(f"Successfully matched {success_count}/{orgs_count} organizations")
    
    return {
        "success": True,
        "organizations_processed": orgs_count,
        "organizations_matched": success_count,
        "results": results
    }

@task(name="Create Email Campaigns",
      retries=2,
      retry_delay_seconds=30)
async def create_email_campaigns(matching_result: Dict[str, Any]) -> Dict[str, Any]:
    """Create email campaigns for organizations with new grant matches"""
    logger = get_run_logger()
    
    if not matching_result.get("success", False):
        logger.warning("Skipping email campaigns due to previous task failure")
        return {"success": False, "message": "Previous task failed"}
    
    # Get organizations with matches
    orgs_with_matches = [
        r for r in matching_result.get("results", [])
        if r.get("success", False) and r.get("matches_count", 0) > 0
    ]
    
    orgs_count = len(orgs_with_matches)
    if orgs_count == 0:
        logger.info("No organizations with matches to email")
        return {"success": True, "message": "No organizations with matches to email"}
    
    logger.info(f"Creating email campaigns for {orgs_count} organizations")
    
    # Process each organization
    results = []
    for org_result in orgs_with_matches:
        org_id = org_result.get("organization_id")
        logger.info(f"Creating email campaign for organization {org_id}")
        
        try:
            # Get the grant matches
            matches_result = await make_api_call(f"organizations/grant-matches/{org_id}")
            
            # Send email with matches
            email_result = await make_api_call(
                "email/send-grant-matches", 
                method="POST",
                json_data={
                    "organization_id": org_id,
                    "matches": matches_result.get("matches", [])
                }
            )
            
            results.append({
                "organization_id": org_id, 
                "success": email_result.get("success", False),
                "email_sent": email_result.get("email_sent", False)
            })
        except Exception as e:
            logger.error(f"Error creating email campaign for organization {org_id}: {str(e)}")
            results.append({"organization_id": org_id, "success": False, "error": str(e)})
    
    success_count = sum(1 for r in results if r.get("success", False))
    logger.info(f"Successfully created email campaigns for {success_count}/{orgs_count} organizations")
    
    return {
        "success": True,
        "organizations_processed": orgs_count,
        "emails_sent": success_count,
        "results": results
    }

# Main Prefect flow
@flow(name="Grant Processing Pipeline")
async def grant_processing_pipeline(date_range: int = 1):
    """
    Main workflow that orchestrates the grant processing pipeline:
    1. Find new grants
    2. Add summaries to new grants
    3. Add summaries to new organizations
    4. Match organizations with grants
    5. Create email campaigns
    """
    logger = get_run_logger()
    logger.info(f"Starting grant processing pipeline for the last {date_range} days")
    
    # Step 1: Find new grants
    grants_result = await find_new_grants(date_range)
    
    # Step 2: Add summaries to new grants
    grant_summaries_result = await add_summaries_to_grants(grants_result)
    
    # # Step 3: Add summaries to new organizations
    org_summaries_result = await add_summaries_to_organizations()
    
    # Step 4: Match organizations with grants
    matching_result = await match_organizations_with_grants()
    
    # Step 5: Create email campaigns
    email_result = await create_email_campaigns(matching_result)
    
    # Compile final results
    final_result = {
        "grants_found": grants_result.get("count", 0),
        "grants_summarized": grant_summaries_result.get("grants_summarized", 0),
        "organizations_summarized": org_summaries_result.get("organizations_summarized", 0),
        "organizations_matched": matching_result.get("organizations_matched", 0),
        "emails_sent": email_result.get("emails_sent", 0)
    }
    
    logger.info(f"Grant processing pipeline completed: {json.dumps(final_result, indent=2)}")
    return final_result

# Entry point for running the flow directly
if __name__ == "__main__":
    asyncio.run(grant_processing_pipeline()) 