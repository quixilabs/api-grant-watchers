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
    
    # Normalize the endpoint path - remove trailing slash if present
    endpoint = endpoint.rstrip('/')
    url = f"{API_BASE_URL}/{endpoint}"
    
    logger.info(f"Making {method} request to {url}")
    if params:
        logger.info(f"Params: {params}")
    if json_data:
        logger.info(f"Data: {json_data}")
    
    try:
        # Always follow redirects to handle 307 redirects automatically
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            if method == "GET":
                response = await client.get(url, params=params)
            elif method == "POST":
                response = await client.post(url, params=params, json=json_data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Check if successful (2xx status code)
            response.raise_for_status()
            
            # Log the actual URL that was used (after any redirects)
            if response.url != url:
                logger.info(f"Request was redirected to: {response.url}")
                
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

@task(name="Get All Grants", 
      retries=2, 
      retry_delay_seconds=30)
async def get_all_grants(batch_size: int = 100, max_batches: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Fetch all grants from the database, potentially in batches to avoid memory issues.
    
    Args:
        batch_size: Number of grants to fetch in each batch
        max_batches: Maximum number of batches to process (for testing/debugging)
        
    Returns:
        List of grants
    """
    logger = get_run_logger()
    logger.info(f"Fetching all grants from the database (batch_size={batch_size}, max_batches={max_batches})")
    
    # Initialize variables
    all_grants = []
    offset = 0
    batches_processed = 0
    continue_fetching = True
    
    # Fetch grants in batches
    while continue_fetching:
        try:
            # Make API call to fetch grants - make sure to use the correct endpoint with trailing slash
            result = await make_api_call(
                "grants/", 
                params={"limit": str(batch_size), "offset": str(offset)}
            )
            
            # Extract grants from the response
            batch_grants = result.get("grants", [])
            batch_size_actual = len(batch_grants)
            
            logger.info(f"Fetched batch {batches_processed + 1} with {batch_size_actual} grants (offset={offset})")
            
            # Add grants to the list
            all_grants.extend(batch_grants)
            
            # Increment counters
            offset += batch_size
            batches_processed += 1
            
            # Check if we should continue fetching
            if batch_size_actual < batch_size:
                # We've fetched all grants
                logger.info(f"Fetched all grants (total: {len(all_grants)})")
                continue_fetching = False
            elif max_batches is not None and batches_processed >= max_batches:
                # We've reached the maximum number of batches
                logger.info(f"Reached maximum number of batches ({max_batches}), stopping")
                continue_fetching = False
        except Exception as e:
            logger.error(f"Error fetching grants batch: {str(e)}")
            continue_fetching = False
    
    logger.info(f"Fetched {len(all_grants)} grants in {batches_processed} batches")
    return all_grants

@task(name="Find Grants Without Details",
      retries=2,
      retry_delay_seconds=30)
async def find_grants_without_details(grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Find grants that don't have details.
    
    Args:
        grants: List of grants
        
    Returns:
        List of grants without details
    """
    logger = get_run_logger()
    
    # Filter grants that don't have details
    grants_without_details = [
        grant for grant in grants
        if not grant.get("details_raw_data")
    ]
    
    logger.info(f"Found {len(grants_without_details)} grants without details out of {len(grants)} total grants")
    return grants_without_details

@task(name="Find Grants Without Summaries",
      retries=2,
      retry_delay_seconds=30)
async def find_grants_without_summaries(grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Find grants that don't have summaries.
    
    Args:
        grants: List of grants
        
    Returns:
        List of grants without summaries
    """
    logger = get_run_logger()
    
    # Filter grants that don't have summaries
    grants_without_summaries = [
        grant for grant in grants
        if not grant.get("synopsis_summary")
    ]
    
    logger.info(f"Found {len(grants_without_summaries)} grants without summaries out of {len(grants)} total grants")
    return grants_without_summaries

@task(name="Fetch Grant Details",
      retries=2,
      retry_delay_seconds=30)
async def fetch_grant_details_batch(grants: List[Dict[str, Any]], batch_size: int = 10, delay_seconds: int = 5) -> Dict[str, Any]:
    """
    Fetch details for a batch of grants.
    
    Args:
        grants: List of grants to fetch details for
        batch_size: Number of grants to process in each batch
        delay_seconds: Delay between API calls
        
    Returns:
        Results of the operation
    """
    logger = get_run_logger()
    
    if not grants:
        logger.info("No grants to fetch details for")
        return {"success": True, "message": "No grants to fetch details for", "processed": 0, "successful": 0}
    
    total_grants = len(grants)
    logger.info(f"Fetching details for {total_grants} grants (batch_size={batch_size}, delay={delay_seconds}s)")
    
    # Process grants in batches
    successful = 0
    failed = 0
    
    for i in range(0, total_grants, batch_size):
        # Get the current batch
        batch = grants[i:i + batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(total_grants+batch_size-1)//batch_size} ({len(batch)} grants)")
        
        # Process each grant in the batch
        for grant in batch:
            grant_id = grant.get("id")
            logger.info(f"Fetching details for grant {grant_id}")
            
            try:
                # Use correct endpoint matching @router.post("/details/{grant_id}")
                result = await make_api_call(
                    f"grants/details/{grant_id}",
                    method="POST",
                    params={"force_fetch": "false"}
                )
                
                if result.get("success", False):
                    successful += 1
                    logger.info(f"Successfully fetched details for grant {grant_id}")
                else:
                    failed += 1
                    logger.warning(f"Failed to fetch details for grant {grant_id}: {result.get('error', 'Unknown error')}")
            except Exception as e:
                failed += 1
                logger.error(f"Error fetching details for grant {grant_id}: {str(e)}")
            
            # Delay to avoid overloading the API
            await asyncio.sleep(delay_seconds)
        
        # Log progress
        logger.info(f"Completed {i + len(batch)}/{total_grants} grants ({successful} successful, {failed} failed)")
        
    logger.info(f"Completed fetching details for {total_grants} grants ({successful} successful, {failed} failed)")
    
    return {
        "success": True,
        "message": f"Completed fetching details for {total_grants} grants",
        "processed": total_grants,
        "successful": successful,
        "failed": failed
    }

@task(name="Generate Grant Summaries",
      retries=2,
      retry_delay_seconds=30)
async def generate_grant_summaries_batch(grants: List[Dict[str, Any]], batch_size: int = 10, delay_seconds: int = 15) -> Dict[str, Any]:
    """
    Generate summaries for a batch of grants.
    
    Args:
        grants: List of grants to generate summaries for
        batch_size: Number of grants to process in each batch
        delay_seconds: Delay between API calls (should be substantial for AI-based summarization)
        
    Returns:
        Results of the operation
    """
    logger = get_run_logger()
    
    if not grants:
        logger.info("No grants to generate summaries for")
        return {"success": True, "message": "No grants to generate summaries for", "processed": 0, "successful": 0}
    
    total_grants = len(grants)
    logger.info(f"Generating summaries for {total_grants} grants (batch_size={batch_size}, delay={delay_seconds}s)")
    
    # Process grants in batches
    successful = 0
    failed = 0
    
    for i in range(0, total_grants, batch_size):
        # Get the current batch
        batch = grants[i:i + batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(total_grants+batch_size-1)//batch_size} ({len(batch)} grants)")
        
        # Process each grant in the batch
        for grant in batch:
            grant_id = grant.get("id")
            logger.info(f"Generating summary for grant {grant_id}")
            
            try:
                # Use correct endpoint matching @router.post("/generate-summary/{grant_id}")
                result = await make_api_call(
                    f"grants/generate-summary/{grant_id}",
                    method="POST",
                    params={"force_regenerate": "false"}
                )
                
                if result.get("success", False):
                    successful += 1
                    logger.info(f"Successfully generated summary for grant {grant_id}")
                else:
                    failed += 1
                    logger.warning(f"Failed to generate summary for grant {grant_id}: {result.get('error', 'Unknown error')}")
            except Exception as e:
                failed += 1
                logger.error(f"Error generating summary for grant {grant_id}: {str(e)}")
            
            # Delay to avoid overloading the API (and AI service)
            logger.info(f"Waiting {delay_seconds} seconds before processing next grant")
            await asyncio.sleep(delay_seconds)
        
        # Log progress
        logger.info(f"Completed {i + len(batch)}/{total_grants} grants ({successful} successful, {failed} failed)")
        
    logger.info(f"Completed generating summaries for {total_grants} grants ({successful} successful, {failed} failed)")
    
    return {
        "success": True,
        "message": f"Completed generating summaries for {total_grants} grants",
        "processed": total_grants,
        "successful": successful,
        "failed": failed
    }

# Main Prefect flow
@flow(name="Grant Details and Summaries Pipeline")
async def grant_details_summaries_pipeline(
    batch_size: int = 100,
    max_batches: Optional[int] = None,
    details_batch_size: int = 10,
    details_delay_seconds: int = 5,
    summaries_batch_size: int = 5,
    summaries_delay_seconds: int = 15,
    process_details: bool = True,
    process_summaries: bool = True,
    max_details_grants: Optional[int] = None,
    max_summary_grants: Optional[int] = None
):
    """
    Main workflow that processes grants to ensure they have details and summaries:
    1. Fetch all grants from the database
    2. Find grants without details
    3. Fetch details for each grant
    4. Find grants without summaries
    5. Generate summaries for each grant
    
    Args:
        batch_size: Number of grants to fetch in each batch when getting all grants
        max_batches: Maximum number of batches to process when getting all grants (for testing/debugging)
        details_batch_size: Number of grants to process in each batch when fetching details
        details_delay_seconds: Delay between API calls when fetching details
        summaries_batch_size: Number of grants to process in each batch when generating summaries
        summaries_delay_seconds: Delay between API calls when generating summaries
        process_details: Whether to process grant details
        process_summaries: Whether to process grant summaries
        max_details_grants: Maximum number of grants to process for details (for testing/debugging)
        max_summary_grants: Maximum number of grants to process for summaries (for testing/debugging)
    """
    logger = get_run_logger()
    logger.info(f"Starting grant details and summaries pipeline")
    
    # Step 1: Fetch all grants
    all_grants = await get_all_grants(batch_size=batch_size, max_batches=max_batches)
    
    details_results = {"processed": 0, "successful": 0, "failed": 0}
    summary_results = {"processed": 0, "successful": 0, "failed": 0}
    
    # Step 2-3: Process grant details
    if process_details:
        # Find grants without details
        grants_without_details = await find_grants_without_details(all_grants)
        
        # Apply max limit if specified
        if max_details_grants is not None and max_details_grants < len(grants_without_details):
            logger.info(f"Limiting details processing to {max_details_grants} grants (out of {len(grants_without_details)})")
            grants_without_details = grants_without_details[:max_details_grants]
        
        # Fetch details for each grant
        details_results = await fetch_grant_details_batch(
            grants_without_details, 
            batch_size=details_batch_size,
            delay_seconds=details_delay_seconds
        )
    else:
        logger.info("Skipping grant details processing")
    
    # Step 4-5: Process grant summaries
    if process_summaries:
        # Find grants without summaries
        grants_without_summaries = await find_grants_without_summaries(all_grants)
        
        # Apply max limit if specified
        if max_summary_grants is not None and max_summary_grants < len(grants_without_summaries):
            logger.info(f"Limiting summary processing to {max_summary_grants} grants (out of {len(grants_without_summaries)})")
            grants_without_summaries = grants_without_summaries[:max_summary_grants]
        
        # Generate summaries for each grant
        summary_results = await generate_grant_summaries_batch(
            grants_without_summaries,
            batch_size=summaries_batch_size,
            delay_seconds=summaries_delay_seconds
        )
    else:
        logger.info("Skipping grant summary processing")
    
    # Compile final results
    final_result = {
        "total_grants": len(all_grants),
        "details_processing": {
            "grants_without_details": len(await find_grants_without_details(all_grants)),
            "grants_processed": details_results.get("processed", 0),
            "successful": details_results.get("successful", 0),
            "failed": details_results.get("failed", 0)
        },
        "summary_processing": {
            "grants_without_summaries": len(await find_grants_without_summaries(all_grants)),
            "grants_processed": summary_results.get("processed", 0),
            "successful": summary_results.get("successful", 0),
            "failed": summary_results.get("failed", 0)
        }
    }
    
    logger.info(f"Grant details and summaries pipeline completed: {json.dumps(final_result, indent=2)}")
    return final_result

# Entry point for running the flow directly
if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Process grants to ensure they have details and summaries")
    parser.add_argument("--batch-size", type=int, default=100, help="Number of grants to fetch in each batch")
    parser.add_argument("--max-batches", type=int, help="Maximum number of batches to process")
    parser.add_argument("--details-batch-size", type=int, default=10, help="Number of grants to process in each batch for details")
    parser.add_argument("--details-delay", type=int, default=5, help="Delay between API calls for details (seconds)")
    parser.add_argument("--summaries-batch-size", type=int, default=5, help="Number of grants to process in each batch for summaries")
    parser.add_argument("--summaries-delay", type=int, default=15, help="Delay between API calls for summaries (seconds)")
    parser.add_argument("--skip-details", action="store_true", help="Skip processing grant details")
    parser.add_argument("--skip-summaries", action="store_true", help="Skip processing grant summaries")
    parser.add_argument("--max-details", type=int, help="Maximum number of grants to process for details")
    parser.add_argument("--max-summaries", type=int, help="Maximum number of grants to process for summaries")
    
    args = parser.parse_args()
    
    print(f"Starting grant details and summaries pipeline with parameters:")
    print(f"  batch_size: {args.batch_size}")
    print(f"  max_batches: {args.max_batches}")
    print(f"  details_batch_size: {args.details_batch_size}")
    print(f"  details_delay_seconds: {args.details_delay}")
    print(f"  summaries_batch_size: {args.summaries_batch_size}")
    print(f"  summaries_delay_seconds: {args.summaries_delay}")
    print(f"  process_details: {not args.skip_details}")
    print(f"  process_summaries: {not args.skip_summaries}")
    print(f"  max_details_grants: {args.max_details}")
    print(f"  max_summary_grants: {args.max_summaries}")
    
    asyncio.run(grant_details_summaries_pipeline(
        batch_size=args.batch_size,
        max_batches=args.max_batches,
        details_batch_size=args.details_batch_size,
        details_delay_seconds=args.details_delay,
        summaries_batch_size=args.summaries_batch_size,
        summaries_delay_seconds=args.summaries_delay,
        process_details=not args.skip_details,
        process_summaries=not args.skip_summaries,
        max_details_grants=args.max_details,
        max_summary_grants=args.max_summaries
    )) 