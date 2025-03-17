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
    Generate HTML content for the email campaign with improved styling and layout.
    """
    # Define some color variables for consistent styling
    primary_color = "#2563EB"  # Blue
    secondary_color = "#1E40AF"  # Darker blue
    text_color = "#333333"
    light_bg = "#F3F4F6"
    border_color = "#E5E7EB"
    success_color = "#10B981"  # Green for high match scores
    
    content = [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '</head>',
        '<body style="font-family: \'Helvetica Neue\', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f5f7fa;">',
        '<div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">',
        
        # Header section
        f'<div style="background-color: {primary_color}; padding: 30px 20px; text-align: center;">',
        f'<h1 style="color: white; margin: 0; font-size: 24px;">Grant Opportunities for {organization_data.get("organization_name")}</h1>',
        '</div>',
        
        # Intro section
        '<div style="padding: 25px 30px;">',
        '<p style="color: #555; font-size: 16px; margin-top: 0;">Based on your organization\'s profile and interests, we\'ve identified the following grant opportunities that match your criteria:</p>',
        '</div>'
    ]

    # Grant matches section
    for i, match in enumerate(grant_matches):
        grant = match.get("grant", {})
        match_score = float(match.get("match_score", 0)) * 100
        
        # Determine match score color based on percentage
        score_color = "#FFA500"  # Default orange
        if match_score >= 90:
            score_color = success_color  # Green for high matches
        elif match_score < 70:
            score_color = "#DC2626"  # Red for lower matches
            
        # Format award range properly
        award_floor = grant.get("award_floor", "N/A")
        award_ceiling = grant.get("award_ceiling", "N/A")
        
        if award_floor != "N/A" and award_ceiling != "N/A":
            try:
                # Convert to float or int first, then format
                floor_value = float(award_floor)
                ceiling_value = float(award_ceiling)
                award_range = f"${floor_value:,.2f} - ${ceiling_value:,.2f}"
            except (ValueError, TypeError):
                # Fallback if conversion fails
                award_range = f"${award_floor} - ${award_ceiling}"
        elif award_floor != "N/A":
            try:
                floor_value = float(award_floor)
                award_range = f"${floor_value:,.2f} minimum"
            except (ValueError, TypeError):
                award_range = f"${award_floor} minimum"
        elif award_ceiling != "N/A":
            try:
                ceiling_value = float(award_ceiling)
                award_range = f"Up to ${ceiling_value:,.2f}"
            except (ValueError, TypeError):
                award_range = f"Up to ${award_ceiling}"
        else:
            award_range = "Not specified"
            
        content.extend([
            '<div style="margin: 0 30px 25px; border: 1px solid ' + border_color + '; border-radius: 8px; overflow: hidden;">',
            
            # Grant header with title and match score
            f'<div style="background-color: {light_bg}; padding: 15px 20px; border-bottom: 1px solid {border_color}; display: flex; justify-content: space-between; align-items: center;">',
            f'<h2 style="color: {secondary_color}; margin: 0; font-size: 18px; flex: 1;">{grant.get("title", "N/A")}</h2>',
            f'<div style="background-color: {score_color}; color: white; font-weight: bold; padding: 5px 10px; border-radius: 20px; font-size: 14px; min-width: 50px; text-align: center;">{match_score:.0f}%</div>',
            '</div>',
            
            # Grant details
            '<div style="padding: 20px;">',
            '<table style="width: 100%; border-collapse: collapse; font-size: 15px;">',
            '<tr>',
            f'<td style="padding: 8px 0; vertical-align: top; width: 140px;"><strong style="color: {text_color};">Agency:</strong></td>',
            f'<td style="padding: 8px 0;">{grant.get("agency", "N/A")}</td>',
            '</tr>',
            '<tr>',
            f'<td style="padding: 8px 0; vertical-align: top;"><strong style="color: {text_color};">Award Range:</strong></td>',
            f'<td style="padding: 8px 0;">{award_range}</td>',
            '</tr>',
            '<tr>',
            f'<td style="padding: 8px 0; vertical-align: top;"><strong style="color: {text_color};">Close Date:</strong></td>',
            f'<td style="padding: 8px 0;">{grant.get("close_date", "N/A")}</td>',
            '</tr>',
            '</table>',
            
            # Why this matches section
            '<div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid ' + border_color + ';">',
            f'<p style="margin-top: 0; margin-bottom: 5px;"><strong style="color: {secondary_color};">Why This Matches:</strong></p>',
            f'<p style="margin-top: 5px; color: #555; line-height: 1.5;">{match.get("match_reason", "N/A")}</p>',
            '</div>',
            
            # CTA button
            '<div style="margin-top: 20px; text-align: center;">',
            f'<a target="_blank" href="https://grants.gov/search-results-detail/{grant.get("id", "")}" style="display: inline-block; background-color: {primary_color}; color: white; padding: 10px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; transition: background-color 0.2s;">View Grant Details</a>',
            '</div>',
            '</div>',
            '</div>'
        ])

    # Footer section
    content.extend([
        '<div style="padding: 25px 30px; background-color: ' + light_bg + '; text-align: center; border-top: 1px solid ' + border_color + ';">',
        f'<p style="margin: 0; color: #555; font-size: 15px;">Need assistance with your grant application? <a href="#" style="color: {primary_color}; text-decoration: none; font-weight: bold;">Our team is here to help!</a></p>',
        '</div>',
        '</div>',
        '<div style="text-align: center; padding: 20px; font-size: 13px; color: #6B7280;">',
        '<p style="margin: 5px 0;">© 2023 Grant Watchers. All rights reserved.</p>',
        '<p style="margin: 5px 0;">You received this email because you subscribed to grant alerts.</p>',
        '</div>',
        '</body>',
        '</html>'
    ])

    return ''.join(content) 