import logging
import json
from typing import List, Dict, Any
from app.utils.supabase import get_supabase_client
from app.utils.ollama_client import generate_with_ollama

# Set up logging
logger = logging.getLogger(__name__)

async def match_organization_with_grants(organization_data: Dict[str, Any], grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Match an organization with relevant grants using Ollama.
    
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
        for grant in grants:
            grants_info += f"""
            Grant ID: {grant.get('id', '')}
            Title: {grant.get('title', '')}
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
        
        IMPORTANT: Use the exact Grant ID provided in the grant information.
        
        Return a JSON array of matches in this format:
        [
            {{
                "grant_id": "exact_grant_id_from_above",
                "match_score": float between 0 and 1,
                "match_reason": "Detailed explanation of why this is a good match"
            }}
        ]
        
        Only include grants that have a match_score >= 0.5
        Ensure you use the exact grant ID as provided in the grant information.
        """
        
        # System message
        system_message = """You are a grant matching expert. Your task is to analyze organizations and grants to find the best matches.
        Return ONLY a JSON array of matches, with no additional text or explanation.
        Each match must include the exact grant ID as provided in the input.
        Each match should include a score (0-1) and a detailed reason for the match."""
        
        # Call Ollama API
        response = await generate_with_ollama(prompt, system_message)
        
        # Parse the response
        try:
            matches = json.loads(response)
            
            # Validate that all grant_ids exist in the provided grants
            valid_grant_ids = {grant.get('id') for grant in grants}
            validated_matches = [
                match for match in matches 
                if match.get('grant_id') in valid_grant_ids
            ]
            
            if len(validated_matches) < len(matches):
                logger.warning(f"Some matches were filtered out due to invalid grant IDs. Original: {len(matches)}, Valid: {len(validated_matches)}")
            
            return validated_matches
            
        except json.JSONDecodeError:
            logger.error(f"Error parsing matches JSON: {response}")
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