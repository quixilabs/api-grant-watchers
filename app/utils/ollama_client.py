import logging
import httpx
import json
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

OLLAMA_API_URL = "http://localhost:11434/api/chat"

async def get_ollama_client():
    """
    Get an Ollama client instance.
    """
    return httpx.AsyncClient()

async def generate_with_ollama(prompt: str, system_message: str) -> str:
    """
    Generate text using Ollama's API.
    
    Args:
        prompt (str): The user prompt
        system_message (str): The system message
        
    Returns:
        str: The generated response
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OLLAMA_API_URL,
                json={
                    "model": "mistral",  # Using mistral as it's a good balance of performance and quality
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                return response.json()["message"]["content"]
            else:
                logger.error(f"Error from Ollama API: {response.status_code} - {response.text}")
                raise Exception(f"Ollama API error: {response.status_code}")
                
    except Exception as e:
        logger.error(f"Error in generate_with_ollama: {str(e)}")
        raise

async def generate_grant_summary(grant_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a summary of a grant using Ollama.
    
    Args:
        grant_data (dict): The grant data to summarize
        
    Returns:
        dict: The summary in JSON format
    """
    try:
        # Extract relevant information from the grant data
        title = grant_data.get("title", "")
        description = grant_data.get("description", "")
        agency = grant_data.get("agency", "")
        open_date = grant_data.get("open_date", "")
        close_date = grant_data.get("close_date", "")
        award_ceiling = grant_data.get("award_ceiling", "")
        award_floor = grant_data.get("award_floor", "")
        expected_awards = grant_data.get("expected_awards", "")
        eligibility_categories = grant_data.get("eligibility_categories", [])
        funding_instrument_type = grant_data.get("funding_instrument_type", "")
        
        # Prepare the prompt for Ollama
        prompt = f"""
        Grant Opportunity Information:
        Title: {title}
        Agency: {agency}
        Open Date: {open_date}
        Close Date: {close_date}
        Award Ceiling: {award_ceiling}
        Award Floor: {award_floor}
        Expected Number of Awards: {expected_awards}
        Eligibility Categories: {eligibility_categories}
        Funding Instrument Type: {funding_instrument_type}
        
        Description:
        {description}
        
        Please provide a summary in the following JSON format:
        {{
            "goal": "Brief description of the grant's purpose",
            "duration": "Expected duration of the grant",
            "success_criteria": ["Key criteria 1", "Key criteria 2"],
            "good_to_know": ["Important note 1", "Important note 2"]
        }}
        
        IMPORTANT: Return ONLY the JSON object, with no additional text or explanation.
        """
        
        # System message for Ollama
        system_message = """You are a JSON-only response bot. Your task is to generate a summary of a grant opportunity in a specific JSON format.
        You must return ONLY the JSON object, with no additional text, explanation, or formatting.
        The JSON must be valid and parseable.
        Do not include any markdown formatting or code blocks.
        The output must be a single, valid JSON object."""
        
        # Call Ollama API
        logger.info(f"Generating summary for grant: {title}")
        response = await generate_with_ollama(prompt, system_message)
        
        # Log the raw response for debugging
        logger.info(f"Raw response from Ollama: {response}")
        
        # Clean the response
        response = response.strip()
        
        # Remove any markdown code blocks if present
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].strip()
        
        # Remove any leading/trailing whitespace
        response = response.strip()
        
        # Parse the JSON
        try:
            summary = json.loads(response)
            logger.info(f"Successfully parsed JSON summary: {summary}")
            return summary
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Failed to parse response: {response}")
            # Try to fix common JSON issues
            try:
                # Remove any non-JSON characters
                response = response.replace('\n', ' ').replace('\r', '')
                # Ensure the response starts and ends with curly braces
                if not response.startswith('{'):
                    response = '{' + response
                if not response.endswith('}'):
                    response = response + '}'
                summary = json.loads(response)
                return summary
            except json.JSONDecodeError as e2:
                logger.error(f"Second attempt at JSON parsing failed: {str(e2)}")
                return {"error": f"Failed to parse JSON response: {str(e2)}"}
            
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return {"error": f"Error generating summary: {str(e)}"} 