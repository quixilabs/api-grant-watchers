import os
import time
import json
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from prefect.context import get_run_context
from app.api.routes.keywords import process_keywords_for_new_grants

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
@task(name="Check New Grants by Keywords",
      retries=2,
      retry_delay_seconds=30)
def check_new_grants_by_keywords(keywords: List[str], date_range: int = 1) -> Dict[str, Any]:
    """
    Check for new grants based on provided keywords
    
    Args:
        keywords: List of keywords to search for
        date_range: Number of days to look back for new grants
        
    Returns:
        Dictionary containing new grants found
    """
    logger = get_run_logger()
    logger.info(f"Checking for new grants with keywords: {', '.join(keywords)}")
    logger.info(f"Date range: {date_range} days")
    
    try:
        # Run the process synchronously
        results = asyncio.run(process_keywords_for_new_grants(
            date_range=str(date_range),
            opp_statuses="forecasted|posted",
            rows=5000,
            sort_by="openDate|desc",
            keywords=keywords
        ))
        print(results)
        new_grants_count = results.get("total_grants_saved", 0)
        logger.info(f"Found {new_grants_count} new grants matching keywords")
        
        return {
            "success": True,
            "count": new_grants_count,
            "total_grants_found": results.get("total_grants_found", 0),
            "total_details_fetched": results.get("total_details_fetched", 0),
            "keywords": keywords,
            "date_range": date_range,
            "errors": results.get("errors", [])
        }
        
    except Exception as e:
        logger.error(f"Error checking for new grants: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "keywords": keywords,
            "date_range": date_range
        }

@task(name="Match Organization with Grants",
      retries=2,
      retry_delay_seconds=30)
async def match_organization_with_grants(organization_id: str) -> Dict[str, Any]:
    """
    Match an organization with relevant grants based on their keywords
    
    Args:
        organization_id: ID of the organization to match
        
    Returns:
        Dictionary containing matching grants
    """
    logger = get_run_logger()
    logger.info(f"Matching grants for organization: {organization_id}")
    
    try:
        # Get current date in ISO format
        current_date = datetime.now().isoformat()
        
        # Initial API call to start the matching process
        result = await make_api_call(
            f"organizations/match-with-grants/{organization_id}",
            method="POST",
            json_data={
                "close_date_after": current_date
            }
        )
        
        # Check if we got a status URL to poll
        status_url = result.get("status_url")
        if not status_url:
            logger.error("No status URL received from API")
            return {
                "success": False,
                "error": "No status URL received",
                "organization_id": organization_id
            }
            
        logger.info(f"Received status URL: {status_url}")
        
        # Poll the status URL until completion
        max_attempts = 30  # Maximum number of polling attempts
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            logger.info(f"Polling attempt {attempt}/{max_attempts}")
            
            # Poll the status URL
            status_result = await make_api_call(
                status_url,
                method="GET"
            )
            
            # Print the full response
            print(f"Poll Response (Attempt {attempt}):")
            print(json.dumps(status_result, indent=2))
            
            # Check if the process is complete
            status = status_result.get("status")
            if status in ["completed", "failed"]:
                logger.info(f"Process {status} after {attempt} attempts")
                
                if status == "completed":
                    matches = status_result.get("matches", [])
                    matches_count = len(matches)
                    logger.info(f"Found {matches_count} matching grants for organization {organization_id}")
                    
                    return {
                        "success": True,
                        "organization_id": organization_id,
                        "matches": matches,
                        "matches_count": matches_count,
                        "attempts": attempt
                    }
                else:
                    error = status_result.get("error", "Unknown error")
                    logger.error(f"Process failed: {error}")
                    return {
                        "success": False,
                        "error": error,
                        "organization_id": organization_id,
                        "attempts": attempt
                    }
            
            # Wait before next poll
            await asyncio.sleep(15)  # Wait 5 seconds between polls
        
        # If we get here, we've exceeded max attempts
        logger.error(f"Exceeded maximum polling attempts ({max_attempts})")
        return {
            "success": False,
            "error": "Exceeded maximum polling attempts",
            "organization_id": organization_id,
            "attempts": max_attempts
        }
        
    except Exception as e:
        logger.error(f"Error matching grants for organization {organization_id}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "organization_id": organization_id
        }

@flow(name="Process grant for marketing organization")
def process_new_grants_flow(
    keywords: List[str],
    organization_id: str,
    date_range: int = 1,
    schedule: Optional[timedelta] = None
) -> Dict[str, Any]:
    """
    Flow to process new grants for specified keywords and match with organization
    
    Args:
        keywords: List of keywords to search for
        organization_id: ID of the organization to match grants with
        date_range: Number of days to look back for new grants
        schedule: Optional schedule for the flow
        
    Returns:
        Dictionary containing the results of the grant processing and matching
    """
    logger = get_run_logger()
    logger.info(f"Starting new grants processing flow for keywords: {', '.join(keywords)}")
    
    # Step 1: Check for new grants
    grants_result = check_new_grants_by_keywords(keywords=keywords, date_range=date_range)
    
    if not grants_result["success"]:
        logger.error(f"Failed to process grants: {grants_result.get('error')}")
        return {
            "success": False,
            "error": grants_result.get("error"),
            "stage": "grants_processing"
        }
    
    logger.info(f"Successfully processed grants. Found {grants_result['count']} new grants")
    
    # Step 2: Match organization with grants
    logger.info(f"Starting grant matching for organization: {organization_id}")
    match_result = asyncio.run(match_organization_with_grants(organization_id=organization_id))
    
    if not match_result["success"]:
        logger.error(f"Failed to match grants: {match_result.get('error')}")
        return {
            "success": False,
            "error": match_result.get("error"),
            "stage": "grant_matching",
            "grants_processing": grants_result
        }
    
    logger.info(f"Successfully matched grants. Found {match_result['matches_count']} matches")
    
    # Return combined results
    return {
        "success": True,
        "grants_processing": grants_result,
        "grant_matching": match_result,
        "total_new_grants": grants_result["count"],
        "total_matches": match_result["matches_count"]
    }

if __name__ == "__main__":
    # Example usage
    date_range = 30
    test_keywords = ["Bio Medical"]
    test_organization_id = "59169758-4f0f-4325-ab6f-28777e495472"  # Replace with actual organization ID
    process_new_grants_flow(
        keywords=test_keywords,
        organization_id=test_organization_id,
        date_range=date_range
    )

