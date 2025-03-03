import logging
import json
from app.utils.supabase import get_supabase_client
from app.utils.openai_client import get_openai_client

# Set up logging
logger = logging.getLogger(__name__)

async def process_new_organization(organization_data):
    """
    Process an organization record and generate a summary.
    
    Args:
        organization_data (dict): The organization data from Supabase
        
    Returns:
        dict: The result of the processing
    """
    try:
        logger.info(f"Processing organization: {organization_data.get('organization_name', 'Unknown')}")
        
        # Generate a summary for the organization
        summary = await generate_organization_summary(organization_data)
        
        # Update the organization record with the summary
        result = await update_organization_summary(organization_data.get('id'), summary)
        
        return {
            "success": True,
            "organization_id": organization_data.get('id'),
            "summary": summary
        }
    except Exception as e:
        logger.error(f"Error processing organization: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

async def generate_organization_summary(organization_data):
    """
    Generate a summary of an organization using OpenAI's GPT model.
    
    Args:
        organization_data (dict): The organization data to summarize
        
    Returns:
        dict: The summary in JSON format
    """
    try:
        client = get_openai_client()
        
        # Extract relevant information from the organization data
        org_name = organization_data.get("organization_name", "")
        org_type = organization_data.get("organization_type", "")
        org_profile = organization_data.get("organization_profile", "")
        website_url = organization_data.get("website_url", "")
        linkedin_url = organization_data.get("linkedin_url", "")
        grant_interests = organization_data.get("grant_interests", "")
        
        # Prepare the prompt for GPT
        prompt = f"""
        Organization Information:
        Name: {org_name}
        Type: {org_type}
        Website: {website_url}
        LinkedIn: {linkedin_url}
        Grant Interests: {grant_interests}
        
        Profile:
        {org_profile}
        
        Generate a summary of this organization in the following JSON format:
        {{
            "mission": "Brief statement of the organization's mission",
            "expertise": ["Area 1", "Area 2", "Area 3"],
            "funding_interests": ["Interest 1", "Interest 2"],
            "notable_aspects": ["Notable aspect 1", "Notable aspect 2"]
        }}
        
        IMPORTANT: Return ONLY the JSON object, no additional text or explanation.
        """
        
        # System message for GPT
        system_message = """You are a JSON-only response bot. Your task is to generate a summary of an organization in a specific JSON format.
        You must return ONLY the JSON object, with no additional text, explanation, or formatting.
        The JSON must be valid and parseable.
        """
        
        # Call the OpenAI API
        logger.info(f"Generating summary for organization: {org_name}")
        response = client.chat.completions.create(
            model="gpt-4",  # Use GPT-4 for better quality summaries
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        # Extract the response content
        response_content = response.choices[0].message.content.strip()
        
        # Try to parse the JSON response
        try:
            # First try direct JSON parsing
            summary_json = json.loads(response_content)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from the response
            try:
                # Look for JSON between curly braces
                import re
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    summary_json = json.loads(json_match.group(0))
                else:
                    raise ValueError("No JSON object found in response")
            except Exception as e:
                logger.error(f"Error parsing summary JSON for organization {org_name}: {response_content}")
                # Create a fallback JSON structure
                summary_json = {
                    "mission": "Error generating mission statement",
                    "expertise": ["Error generating expertise"],
                    "funding_interests": ["Error generating interests"],
                    "notable_aspects": ["Error generating notable aspects"]
                }
        
        # Validate the JSON structure
        required_fields = ["mission", "expertise", "funding_interests", "notable_aspects"]
        for field in required_fields:
            if field not in summary_json:
                summary_json[field] = f"Error generating {field}"
        
        logger.info(f"Successfully generated summary for organization: {org_name}")
        return summary_json
    
    except Exception as e:
        logger.error(f"Error generating organization summary: {str(e)}")
        return {
            "mission": "Error generating mission statement",
            "expertise": ["Error generating expertise"],
            "funding_interests": ["Error generating interests"],
            "notable_aspects": ["Error generating notable aspects"]
        }

async def update_organization_summary(organization_id, summary_data):
    """
    Update an organization record with summary information generated by GPT.
    
    Args:
        organization_id (str): The ID of the organization to update
        summary_data (dict): The summary information generated by GPT
        
    Returns:
        dict: The response from Supabase
    """
    try:
        logger.info(f"Updating organization {organization_id} with summary information")
        client = get_supabase_client()
        
        if not summary_data or "error" in summary_data:
            logger.error(f"Invalid summary data for organization {organization_id}")
            return {"error": "Invalid summary data"}
        
        # Prepare the data for update
        update_data = {
            "summary": summary_data
        }
        
        # Update the organization record
        result = client.table("organizations").update(update_data).eq("id", organization_id).execute()
        
        logger.info(f"Successfully updated organization {organization_id} with summary information")
        return {
            "success": True,
            "organization_id": organization_id,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error updating organization {organization_id} with summary: {str(e)}")
        return {"error": f"Error updating organization summary: {str(e)}"} 