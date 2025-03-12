import json
import logging
from typing import Dict, List, Any, Optional

import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

async def generate_with_deepseek(prompt: str, system_message: Optional[str] = None) -> str:
    """
    Generate text using DeepSeek AI's API.
    
    Args:
        prompt (str): The prompt to send to the model
        system_message (str, optional): System message to set context
        
    Returns:
        str: The generated response
    """
    try:
        if not settings.DEEPSEEK_API_KEY:
            raise Exception("DEEPSEEK_API_KEY is not set in the environment variables")
            
        # Prepare the messages array
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        # Prepare the request data
        data = {
            "model": "deepseek-chat",  # Default model for DeepSeek
            "messages": messages,
            "temperature": 0.3,  # Lower temperature for more deterministic output
            "max_tokens": 4000,
            "response_format": {"type": "json_object"}  # Request JSON format
        }
        
        logger.debug(f"Sending request to DeepSeek with data: {json.dumps(data, indent=2)}")
        
        # Create a client with appropriate timeout
        timeout_settings = httpx.Timeout(
            connect=5.0,  # 5 seconds to establish connection
            read=60.0,    # 60 seconds to read response
            write=5.0,    # 5 seconds to write request
            pool=5.0      # 5 seconds to get connection from pool
        )
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"
        }
        
        async with httpx.AsyncClient(timeout=timeout_settings) as client:
            try:
                response = await client.post(DEEPSEEK_API_URL, json=data, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                logger.debug(f"DeepSeek response: {json.dumps(result, indent=2)}")
                
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    return content
                else:
                    logger.error(f"Unexpected response format: {result}")
                    raise Exception(f"Unexpected response format: {result}")
                    
            except httpx.TimeoutException as e:
                logger.error(f"Request timed out: {str(e)}")
                raise Exception(f"Request timed out after {timeout_settings.read} seconds. The model might be taking too long to respond.")
            except httpx.ConnectError as e:
                logger.error(f"Connection error: {str(e)}")
                raise Exception("Could not connect to DeepSeek API.")
            except httpx.HTTPError as e:
                logger.error(f"HTTP error occurred: {str(e)}")
                logger.error(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response content'}")
                raise
                
    except Exception as e:
        logger.error(f"Error generating with DeepSeek: {str(e)}")
        logger.error(f"Full error details: {type(e).__name__}: {str(e)}")
        raise 

async def generate_grant_summary(grant_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a summary of a grant using DeepSeek AI.
    
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
        
        # Prepare the prompt for DeepSeek
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
        
        # System message for DeepSeek
        system_message = """You are a JSON-only response bot. Your task is to generate a summary of a grant opportunity in a specific JSON format.
        You must return ONLY the JSON object, with no additional text, explanation, or formatting.
        The JSON must be valid and parseable.
        Do not include any markdown formatting or code blocks.
        The output must be a single, valid JSON object."""
        
        # Call DeepSeek API
        logger.info(f"Generating summary for grant: {title}")
        response = await generate_with_deepseek(prompt, system_message)
        
        # Log the raw response for debugging
        logger.info(f"Raw response from DeepSeek: {response}")
        
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