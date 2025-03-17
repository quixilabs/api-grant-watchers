import httpx
import logging
import json
from typing import Dict, List, Any
from app.core.config import settings
from app.utils.resend_client import generate_email_content

logger = logging.getLogger(__name__)

BEEHIIV_API_KEY = "SndMaJHXWcls3z8pDrXC7NIwgYlooLfgKZhtXv6HGnMe4xtivepx18saiVI4uroH"
BEEHIIV_API_BASE_URL = "https://api.beehiiv.com/v2"

async def get_publication_id() -> str:
    """
    Get the first publication ID from Beehiiv account.
    """
    try:
        headers = {
            "Authorization": f"Bearer {BEEHIIV_API_KEY}",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BEEHIIV_API_BASE_URL}/publications",
                headers=headers
            )

            logger.info(f"Publications API Response Status: {response.status_code}")
            logger.info(f"Publications API Response: {response.text}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"Publications data: {data}")
                    
                    # Check if data is a list
                    if isinstance(data, list) and len(data) > 0:
                        return data[0].get('id')
                    # Check if data has a 'data' key containing publications
                    elif isinstance(data, dict) and 'data' in data:
                        publications = data['data']
                        if publications and len(publications) > 0:
                            return publications[0].get('id')
                    
                    logger.error("No publications found in response")
                    return None
                except Exception as e:
                    logger.error(f"Error parsing publications response: {str(e)}")
                    return None
            
            logger.error(f"Error getting publications. Status: {response.status_code}, Response: {response.text}")
            return None

    except Exception as e:
        logger.error(f"Error getting publication ID: {str(e)}")
        return None

async def create_email_campaign(organization_data: Dict[str, Any], grant_matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create an email campaign in Beehiiv for an organization's grant matches.
    """
    try:
        # Get publication ID
        publication_id = await get_publication_id()
        if not publication_id:
            logger.error("Failed to get publication ID")
            return {
                "success": False,
                "error": "Could not get publication ID"
            }

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {BEEHIIV_API_KEY}",
            "Content-Type": "application/json"
        }

        # Format the email content
        email_content = generate_email_content(organization_data, grant_matches)
        
        # Updated post data structure according to Beehiiv API v2
        post_data = {
            "email_settings": {
                "subject_line": f"Grant Opportunities for {organization_data.get('organization_name')}",
                "preview_text": f"Custom-matched grant opportunities for {organization_data.get('organization_name')}"
            },
            "content": {
                "html": email_content
            },
            "status": "draft",
            "title": f"Grant Opportunities for {organization_data.get('organization_name')}",
            "subtitle": f"Custom-matched grant opportunities for {organization_data.get('organization_name')}"
        }

        logger.info(f"Creating campaign for organization: {organization_data.get('organization_name')}")
        logger.info(f"Using publication ID: {publication_id}")
        logger.debug(f"Post data: {json.dumps(post_data, indent=2)}")

        url = f"{BEEHIIV_API_BASE_URL}/publications/{publication_id}/posts"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=post_data,
                timeout=30.0
            )

            logger.info(f"Beehiiv Create Post Response Status: {response.status_code}")
            logger.info(f"Beehiiv Create Post Response: {response.text}")

            if response.status_code == 401:
                logger.error("API access not enabled or invalid API key")
                return {
                    "success": False,
                    "error": "API access not enabled or invalid API key. Please check your Beehiiv workspace settings."
                }
            elif response.status_code in [200, 201]:
                return {
                    "success": True,
                    "campaign_id": response.json().get("id"),
                    "organization_id": organization_data.get("id")
                }
            else:
                error_msg = f"Error creating email campaign. Status: {response.status_code}, Response: {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }

    except Exception as e:
        error_msg = f"Error creating email campaign: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        } 