import asyncio
import logging
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.utils.resend_client import send_grant_match_email_via_smtp
from app.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_smtp_email():
    """
    Test sending an email via Resend SMTP.
    Uses Resend's test domain (onboarding@resend.dev) as the From address.
    All test emails will be sent to charlie@quixilabs.com regardless of the intended recipient.
    """
    # Sample organization data
    organization_data = {
        "id": "test-org-id",
        "organization_name": "Test Organization",
        "organization_profile": "This is a test organization for SMTP email testing.",
        "email": "recipient@example.com"  # Replace with your test email
    }
    
    # Sample grant matches
    grant_matches = [
        {
            "grant": {
                "id": "TEST-GRANT-001",
                "title": "Test Grant Opportunity",
                "agency": "Test Agency",
                "award_floor": "10000",
                "award_ceiling": "50000",
                "close_date": "2023-12-31",
                "description": "This is a test grant description for SMTP email testing."
            },
            "match_score": 0.85,
            "match_reason": "This grant matches your organization's focus on technology and education."
        }
    ]
    
    # Get intended recipient email from command line argument or use default
    intended_recipient = sys.argv[1] if len(sys.argv) > 1 else "your-test-email@example.com"
    
    logger.info(f"Testing SMTP email sending (intended recipient: {intended_recipient})")
    logger.info("Using Resend's test domain (onboarding@resend.dev) as the From address")
    logger.info("NOTE: During testing, all emails will be sent to charlie@quixilabs.com")
    
    # Send the test email
    result = await send_grant_match_email_via_smtp(
        organization_data=organization_data,
        grant_matches=grant_matches,
        to_email=intended_recipient
    )
    
    if result.get("success"):
        logger.info("✅ SMTP Email sent successfully!")
        logger.info(f"Result: {result}")
    else:
        logger.error("❌ Failed to send SMTP email")
        logger.error(f"Error: {result.get('error')}")
    
    return result

if __name__ == "__main__":
    # Check if Resend API key is set
    if not settings.resend_api_key:
        logger.error("❌ RESEND_API_KEY is not set in environment variables")
        sys.exit(1)
    
    # Run the test
    asyncio.run(test_smtp_email()) 