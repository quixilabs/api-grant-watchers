import logging
import json
import asyncio
from typing import List, Dict, Any, Optional
from app.utils.supabase import get_supabase_client
from app.utils.deepseek_client import generate_with_deepseek
from app.utils.task_manager import update_task_status

# Set up logging
logger = logging.getLogger(__name__)

async def match_organization_with_grants(
    organization_data: Dict[str, Any], 
    grants: List[Dict[str, Any]],
    task_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Match an organization with relevant grants using DeepSeek AI.
    Only considers grants that have keywords matching the organization's interests.
    Processes each grant individually with a 60-second delay between LLM calls.
    
    Args:
        organization_data (dict): The organization data
        grants (list): List of grants to match against
        task_id (str, optional): Task ID for background processing
        
    Returns:
        list: List of matches with scores and reasons
    """
    try:
        # Extract organization interests/keywords
        org_interests = organization_data.get('grant_interests', '')
        
        # Convert interests to a list of keywords
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
        else:
            # Handle unexpected type
            logger.warning(f"Unexpected type for grant_interests: {type(org_interests)}. Converting to string.")
            try:
                org_keywords = [str(org_interests).strip().lower()]
            except:
                logger.warning(f"Could not convert grant_interests to string. Using empty list.")
        
        if not org_keywords:
            logger.warning(f"Organization {organization_data.get('organization_name', 'Unknown')} has no grant interests specified")
        else:
            logger.info(f"Organization keywords: {org_keywords}")
        
        # Filter grants based on keywords
        filtered_grants = []
        if org_keywords:
            for grant in grants:
                # Check if any organization keyword is in the grant title, description, or search_keyword
                grant_title = str(grant.get('title', '')).lower()
                grant_desc = str(grant.get('description', '')).lower()
                grant_keywords = str(grant.get('search_keyword', '')).lower()
                
                # Check for keyword matches
                for keyword in org_keywords:
                    if (keyword in grant_keywords):
                        filtered_grants.append(grant)
                        logger.debug(f"Grant {grant.get('id')} matched keyword: {keyword}")
                        break  # Once we find a match, no need to check other keywords

        # If no grants match the keywords, use a subset of all grants
        if not filtered_grants:
            logger.warning(f"No grants matched the organization's keywords. Using a subset of all grants.")
            filtered_grants = grants[:20]  # Limit to 20 grants to avoid too many API calls
        
        logger.info(f"Filtered from {len(grants)} to {len(filtered_grants)} grants based on keywords")
        
        # Update task status if task_id is provided
        if task_id:
            update_task_status(
                task_id,
                total_items=len(filtered_grants),
                processed_items=0,
                matched_items=0,
                failed_items=0
            )
        
        # Prepare organization information
        org_info = f"""
        Organization Information:
        Name: {organization_data.get('organization_name', '')}
        Type: {organization_data.get('organization_type', '')}
        Profile: {organization_data.get('organization_profile', '')}
        Grant Interests: {', '.join(org_keywords) if org_keywords else ''}
        """
        
        # Process each grant individually with staggered LLM calls
        all_matches = []
        for i, grant in enumerate(filtered_grants):
            try:
                # Log progress
                logger.info(f"Processing grant {i+1}/{len(filtered_grants)}: {grant.get('id')} - {grant.get('title', '')}")
                
                # Update task status if task_id is provided
                if task_id:
                    update_task_status(
                        task_id,
                        processed_items=i,
                        current_item_id=grant.get('id'),
                        current_item_name=grant.get('title', '')
                    )
                
                # Prepare grant information
                grant_id = grant.get('id', '')
                grant_title = grant.get('title', '')
                grant_info = f"""
                Grant ID: {grant_id}  # This is a 6-digit numeric code
                Title: {grant_title}
                Description: {grant.get('description', '')}
                Agency: {grant.get('agency', '')}
                Eligibility: {grant.get('eligibility_categories', [])}
                """
                
                # Prepare the prompt for a single grant
                prompt = f"""
                {org_info}
                
                {grant_info}
                
                Determine if this grant is a good match for the organization based on:
                1. The organization's interests and profile
                2. The grant's requirements and eligibility criteria
                3. The organization's type and the grant's target audience
                
                IMPORTANT: You MUST use the exact Grant ID shown in the 'Grant ID:' field above.
                The Grant ID is a 6-digit numeric code.
                Do NOT make up IDs or use any other identifier.
                
                Return a JSON object with the match assessment in this exact format:
                {{{{
                    "grant_id": "{grant_id}",
                    "match_score": 0.85,  # A number between 0 and 1 representing how good the match is
                    "match_reason": "Detailed explanation of why this is a good match or not"
                }}}}
                
                Be honest in your assessment. If it's not a good match, give a lower score (below 0.5).
                """
                
                # System message
                system_message = """You are a grant matching expert. Your task is to analyze if a specific grant is a good match for an organization.
                Respond with only a valid JSON object containing the grant_id, match_score, and match_reason.
                The match_score should be between 0 and 1, with higher scores for better matches.
                Be critical and honest - not every grant is a good match for every organization."""
                
                # Call DeepSeek AI API for this grant
                logger.debug(f"Sending prompt to DeepSeek AI for grant {grant_id}")
                response = await generate_with_deepseek(prompt, system_message)
                logger.debug(f"DeepSeek AI response for grant {grant_id}: {response}")
                
                # Parse the response
                try:
                    match_data = json.loads(response)
                    
                    # Validate the match data
                    if "grant_id" in match_data and "match_score" in match_data and "match_reason" in match_data:
                        # Ensure the grant_id matches
                        if match_data["grant_id"] == grant_id:
                            match_score = float(match_data["match_score"])
                            
                            # Only keep matches with score >= 0.5
                            if match_score >= 0.5:
                                logger.info(f"Grant {grant_id} matched with score {match_score}")
                                all_matches.append(match_data)
                                
                                # Update task status if task_id is provided
                                if task_id:
                                    update_task_status(
                                        task_id,
                                        matched_items=len(all_matches)
                                    )
                            else:
                                logger.info(f"Grant {grant_id} score too low: {match_score}")
                        else:
                            logger.warning(f"Grant ID mismatch: expected {grant_id}, got {match_data['grant_id']}")
                            
                            # Update task status if task_id is provided
                            if task_id:
                                update_task_status(
                                    task_id,
                                    failed_items=update_task_status(task_id, failed_items=lambda x: x + 1)
                                )
                    else:
                        logger.warning(f"Invalid match data format for grant {grant_id}: {match_data}")
                        
                        # Update task status if task_id is provided
                        if task_id:
                            update_task_status(
                                task_id,
                                failed_items=update_task_status(task_id, failed_items=lambda x: x + 1)
                            )
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing match JSON for grant {grant_id}: {str(e)}")
                    logger.error(f"Raw response: {response}")
                    
                    # Update task status if task_id is provided
                    if task_id:
                        update_task_status(
                            task_id,
                            failed_items=update_task_status(task_id, failed_items=lambda x: x + 1)
                        )
                except Exception as e:
                    logger.error(f"Error processing match for grant {grant_id}: {str(e)}")
                    
                    # Update task status if task_id is provided
                    if task_id:
                        update_task_status(
                            task_id,
                            failed_items=update_task_status(task_id, failed_items=lambda x: x + 1)
                        )
                
                # Wait 60 seconds before the next API call to avoid rate limiting
                if i < len(filtered_grants) - 1:  # Don't wait after the last grant
                    logger.info(f"Waiting 60 seconds before processing the next grant...")
                    await asyncio.sleep(60)
                    
            except Exception as e:
                logger.error(f"Error processing grant {grant.get('id', 'unknown')}: {str(e)}")
                
                # Update task status if task_id is provided
                if task_id:
                    update_task_status(
                        task_id,
                        failed_items=update_task_status(task_id, failed_items=lambda x: x + 1)
                    )
                
                # Continue with next grant instead of failing the entire batch
                continue
        
        # Sort matches by score (highest first)
        all_matches.sort(key=lambda x: float(x.get("match_score", 0)), reverse=True)
        
        # Update task status if task_id is provided
        if task_id:
            update_task_status(
                task_id,
                processed_items=len(filtered_grants),
                matched_items=len(all_matches)
            )
        
        logger.info(f"Found {len(all_matches)} matching grants with score >= 0.5")
        return all_matches
            
    except Exception as e:
        logger.error(f"Error matching organization with grants: {str(e)}")
        
        # Update task status if task_id is provided
        if task_id:
            update_task_status(
                task_id,
                status="failed",
                error=str(e)
            )
        
        return []

async def background_match_organization_with_grants(
    task_id: str,
    organization_data: Dict[str, Any],
    grants: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Background task for matching an organization with grants
    
    Args:
        task_id (str): Task ID
        organization_data (dict): The organization data
        grants (list): List of grants to match against
        
    Returns:
        dict: Result of the matching process
    """
    try:
        # Match organization with grants
        matches = await match_organization_with_grants(organization_data, grants, task_id)
        
        if matches:
            # Save matches
            organization_id = organization_data.get("id")
            save_result = await save_organization_grant_matches(organization_id, matches)
            
            return {
                "success": save_result.get("success", False),
                "organization_id": organization_id,
                "matches_count": len(matches),
                "result": save_result
            }
        else:
            return {
                "success": True,
                "organization_id": organization_data.get("id"),
                "matches_count": 0,
                "message": "No matching grants found"
            }
    except Exception as e:
        logger.error(f"Error in background matching task: {str(e)}")
        return {
            "success": False,
            "organization_id": organization_data.get("id"),
            "error": str(e)
        }

async def save_organization_grant_matches(organization_id: str, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Save organization-grant matches to the database.
    
    Args:
        organization_id (str): The ID of the organization
        matches (list): List of matches with scores and reasons
        
    Returns:
        dict: Result of the save operation
    """
    try:
        logger.info(f"Saving {len(matches)} grant matches for organization {organization_id}")
        client = get_supabase_client()
        
        # Delete existing matches for this organization
        delete_result = client.table("organization_grant_matches").delete().eq("organization_id", organization_id).execute()
        logger.info(f"Deleted existing matches for organization {organization_id}")
        
        # Insert new matches
        saved_matches = []
        for match in matches:
            grant_id = match.get("grant_id")
            match_score = float(match.get("match_score", 0))
            match_reason = match.get("match_reason", "")
            
            # Only save matches with score >= 0.5
            if match_score >= 0.5:
                match_data = {
                    "organization_id": organization_id,
                    "grant_id": grant_id,
                    "match_score": match_score,
                    "match_reason": match_reason
                }
                
                result = client.table("organization_grant_matches").insert(match_data).execute()
                saved_matches.append(result)
                logger.debug(f"Saved match for organization {organization_id} and grant {grant_id}")
        
        logger.info(f"Successfully saved {len(saved_matches)} grant matches for organization {organization_id}")
        return {
            "success": True,
            "organization_id": organization_id,
            "matches_count": len(saved_matches)
        }
    except Exception as e:
        logger.error(f"Error saving organization-grant matches: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        } 