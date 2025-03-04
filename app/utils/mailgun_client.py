from typing import Dict, Any, List
import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_grant_match_email(organization_data: Dict[str, Any], grant_matches: List[Dict[str, Any]], to_email: str) -> Dict[str, Any]:
    """
    Send an email via Mailgun with grant matches for an organization.
    """
    try:
        # Generate email content
        email_content = generate_email_content(organization_data, grant_matches)
        
        subject = f"Grant Opportunities for {organization_data.get('organization_name')}"
        
        mailgun_api_url = f"https://api.mailgun.net/v3/{settings.mailgun_domain}"
        
        data = {
            "from": settings.mailgun_from_email,
            "to": to_email,
            "subject": subject,
            "html": email_content
        }
        
        logger.info(f"Sending email for organization: {organization_data.get('organization_name')}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{mailgun_api_url}/messages",
                auth=("api", settings.mailgun_api_key),
                data=data,
                timeout=30.0
            )
        
            logger.info(f"Mailgun Response Status: {response.status_code}")
            logger.info(f"Mailgun Response: {response.text}")
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "message_id": response.json().get("id"),
                    "organization_id": organization_data.get("id")
                }
            else:
                error_msg = f"Error sending email. Status: {response.status_code}, Response: {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
            
    except Exception as e:
        error_msg = f"Error sending email: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }

def generate_email_content(organization_data: Dict[str, Any], grant_matches: List[Dict[str, Any]]) -> str:
    """
    Generate HTML content for the email campaign.
    """
    content = [
        '<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">',
        f'<h1 style="color: #333; text-align: center;">Grant Opportunities for {organization_data.get("organization_name")}</h1>',
        '<p style="color: #666; line-height: 1.6;">Based on your organization\'s profile and interests, we\'ve identified the following grant opportunities that match your criteria:</p>',
        '<div style="margin: 20px 0;">'
    ]

    for match in grant_matches:
        grant = match.get("grant", {})
        content.extend([
            '<div style="margin-bottom: 30px; padding: 20px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9;">',
            f'<h2 style="color: #2c5282; margin-top: 0;">{grant.get("title", "N/A")}</h2>',
            f'<p><strong>Agency:</strong> {grant.get("agency", "N/A")}</p>',
            f'<p><strong>Match Score:</strong> {float(match.get("match_score", 0)) * 100:.0f}%</p>',
            f'<p><strong>Why This Matches:</strong> {match.get("match_reason", "N/A")}</p>',
            f'<p><strong>Award Range:</strong> ${grant.get("award_floor", "N/A")} - ${grant.get("award_ceiling", "N/A")}</p>',
            f'<p><strong>Close Date:</strong> {grant.get("close_date", "N/A")}</p>',
            '<div style="margin-top: 15px;">',
            f'<a href="https://www.grants.gov/search-grants.html?keywords={grant.get("id", "")}" style="background-color: #4299e1; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">View Grant Details</a>',
            '</div>',
            '</div>'
        ])

    content.extend([
        '</div>',
        '<p style="margin-top: 30px; color: #666; text-align: center; padding: 20px; background-color: #f5f5f5; border-radius: 5px;">Need assistance with your grant application? Our team is here to help!</p>',
        '</div>'
    ])

    return ''.join(content) 