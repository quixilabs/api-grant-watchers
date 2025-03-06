import logging
import json
from typing import List, Dict, Any
from app.utils.supabase import get_supabase_client
from app.utils.deepseek_client import generate_with_deepseek

# Set up logging
logger = logging.getLogger(__name__)

async def match_organization_with_grants(organization_data: Dict[str, Any], grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Match an organization with relevant grants using DeepSeek AI.
    
    Args:
        organization_data (dict): The organization data
        grants (list): List of grants to match against
        
    Returns:
        list: List of matches with scores and reasons
    """
    try:
        # Prepare organization information
        org_info = f"""
        Organization Information:
        Name: {organization_data.get('organization_name', '')}
        Type: {organization_data.get('organization_type', '')}
        Profile: {organization_data.get('organization_profile', '')}
        Grant Interests: {organization_data.get('grant_interests', '')}
        """
        
        # Prepare grants information with their actual IDs
        grants_info = "\n\nAvailable Grants:\n"
        logger.debug("Processing grants for matching:")
        logger.debug(f"Total number of grants: {len(grants)}")
        
        # Log first few grants in detail
        for i, grant in enumerate(grants[:5]):  # Log first 5 grants in detail
            grant_id = grant.get('id', '')
            grant_title = grant.get('title', '')
            logger.debug(f"Grant {i+1}:")
            logger.debug(f"  ID: {grant_id}")
            logger.debug(f"  Title: {grant_title}")
            logger.debug(f"  Agency: {grant.get('agency', '')}")
            logger.debug("  ---")
        
        for grant in grants:
            grant_id = grant.get('id', '')
            grant_title = grant.get('title', '')
            grants_info += f"""
            Grant ID: {grant_id}  # This is a 6-digit numeric code
            Title: {grant_title}
            Description: {grant.get('description', '')}
            Agency: {grant.get('agency', '')}
            Eligibility: {grant.get('eligibility_categories', [])}
            
            ---
            """
        
        # Prepare the prompt
        prompt = f"""
        {org_info}
        
        {grants_info}
        
        For each grant, determine if it's a good match for this organization based on:
        1. The organization's interests and profile
        2. The grant's requirements and eligibility criteria
        3. The organization's type and the grant's target audience
        
        IMPORTANT: You MUST use the exact Grant ID shown in the 'Grant ID:' field above.
        The Grant ID is a 6-digit numeric code that appears in the format: "358496", "358455", etc.
        Do NOT make up IDs or use the example format "123456".
        Do NOT use the grant title or any other identifier.
        
        Return a JSON object with a 'matches' array in this exact format:
        {{{{
            "matches": [
                {{{{
                    "grant_id": "358496",
                    "match_score": 0.85,
                    "match_reason": "Detailed explanation of why this is a good match"
                }}}}
            ]
        }}}}
        
        Only include grants that have a match_score >= 0.5
        The grant_id must be one of the actual Grant IDs listed above.
        """
        
        # System message
        system_message = """You are a grant matching expert. Your task is to analyze organizations and grants to find the best matches.
        Each match must include an actual Grant ID from the provided list (not made up or example IDs).
        Each match should include a score (0-1) and a detailed reason for the match.
        The grant_id must be one of the actual Grant IDs from the input list.
        Respond with only a valid JSON object containing a 'matches' array."""
        
        # Call DeepSeek AI API
        logger.debug("Sending prompt to DeepSeek AI")
        response = await generate_with_deepseek(prompt, system_message)
        logger.debug(f"DeepSeek AI response: {response}")
        
        # Parse the response
        try:
            result = json.loads(response)
            matches = result.get('matches', [])
            logger.debug(f"Parsed matches: {matches}")
            
            # Validate that all grant_ids exist in the provided grants
            valid_grant_ids = {grant.get('id') for grant in grants}
            logger.debug(f"Valid grant IDs: {valid_grant_ids}")
            logger.debug(f"Matches before validation: {matches}")
            
            # Additional validation to ensure grant_ids are 6-digit numbers
            validated_matches = []
            for match in matches:
                grant_id = match.get('grant_id', '')
                if grant_id in valid_grant_ids and grant_id.isdigit() and len(grant_id) == 6:
                    validated_matches.append(match)
                else:
                    logger.warning(f"Invalid grant ID format or not found in database: {grant_id}")
            
            logger.debug(f"Matches after validation: {validated_matches}")
            
            if len(validated_matches) < len(matches):
                logger.warning(f"Some matches were filtered out due to invalid grant IDs. Original: {len(matches)}, Valid: {len(validated_matches)}")
                logger.warning(f"Filtered out matches: {[m for m in matches if m.get('grant_id') not in valid_grant_ids]}")
                logger.warning(f"Valid grant IDs in database: {valid_grant_ids}")
            
            return validated_matches
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing matches JSON: {str(e)}")
            logger.error(f"Raw response: {response}")
            return []
            
    except Exception as e:
        logger.error(f"Error matching organization with grants: {str(e)}")
        return []

async def save_organization_grant_matches(organization_id: str, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Save organization-grant matches to the database.
    
    Args:
        organization_id (str): The ID of the organization
        matches (list): List of matches to save
        
    Returns:
        dict: Result of the save operation
    """
    try:
        client = get_supabase_client()
        
        # Prepare matches for insertion
        matches_to_insert = [
            {
                "organization_id": organization_id,
                "grant_id": match["grant_id"],
                "match_score": match["match_score"],
                "match_reason": match["match_reason"]
            }
            for match in matches
        ]
        
        # Insert matches
        result = client.table("organization_grant_matches").insert(matches_to_insert).execute()
        
        return {
            "success": True,
            "matches_saved": len(matches_to_insert),
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error saving organization-grant matches: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        } 