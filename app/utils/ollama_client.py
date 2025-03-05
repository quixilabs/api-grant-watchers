import logging
import httpx
import json
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

OLLAMA_API_URL = "http://localhost:11434/api/chat"

async def get_ollama_client():
    """
    Get an Ollama client instance.
    """
    return httpx.AsyncClient()

async def check_ollama_model(model_name: str = "llama2:latest") -> bool:
    """
    Check if the specified Ollama model is installed.
    
    Args:
        model_name (str): Name of the model to check
        
    Returns:
        bool: True if model is installed, False otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:11434/api/tags")
            response.raise_for_status()
            result = response.json()
            
            # Check if model exists in the list
            models = [model["name"] for model in result.get("models", [])]
            if model_name not in models:
                logger.error(f"Model {model_name} is not installed. Available models: {models}")
                return False
            return True
            
    except Exception as e:
        logger.error(f"Error checking Ollama model: {str(e)}")
        return False

async def check_ollama_server() -> bool:
    """
    Check if the Ollama server is running and accessible.
    
    Returns:
        bool: True if server is running and accessible, False otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:11434/api/version")
            return response.status_code == 200
    except httpx.ConnectError:
        logger.error("Could not connect to Ollama server. Is it running?")
        return False
    except Exception as e:
        logger.error(f"Error checking Ollama server: {str(e)}")
        return False

async def generate_with_ollama(prompt: str, system_message: Optional[str] = None) -> str:
    """
    Generate text using Ollama's API with the llama2 model.
    
    Args:
        prompt (str): The prompt to send to the model
        system_message (str, optional): System message to set context
        
    Returns:
        str: The generated response
    """
    try:
        # First check if Ollama server is running
        if not await check_ollama_server():
            raise Exception("Ollama server is not running. Please start it with: ollama serve")
            
        # Then check if the model is installed
        if not await check_ollama_model():
            raise Exception("llama2:latest model is not installed. Please run: ollama pull llama2")
            
        url = "http://localhost:11434/api/chat"
        
        # Prepare the messages array
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        # Prepare the request data
        data = {
            "model": "llama2:latest",  # Using the correct model name with version
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 2048,
                "stop": ["\n\n", "```"]  # Stop on double newline or code block
            }
        }
        
        logger.debug(f"Sending request to Ollama with data: {json.dumps(data, indent=2)}")
        
        # Create a client with increased timeout
        timeout_settings = httpx.Timeout(
            connect=5.0,  # 5 seconds to establish connection
            read=60.0,    # 60 seconds to read response
            write=5.0,    # 5 seconds to write request
            pool=5.0      # 5 seconds to get connection from pool
        )
        
        async with httpx.AsyncClient(timeout=timeout_settings) as client:
            try:
                response = await client.post(url, json=data)
                response.raise_for_status()
                result = response.json()
                
                logger.debug(f"Ollama response: {json.dumps(result, indent=2)}")
                
                if "message" in result and "content" in result["message"]:
                    return result["message"]["content"]
                else:
                    logger.error(f"Unexpected response format: {result}")
                    raise Exception(f"Unexpected response format: {result}")
                    
            except httpx.TimeoutException as e:
                logger.error(f"Request timed out: {str(e)}")
                raise Exception(f"Request timed out after {timeout_settings.read} seconds. The model might be taking too long to respond.")
            except httpx.ConnectError as e:
                logger.error(f"Connection error: {str(e)}")
                raise Exception("Could not connect to Ollama server. Is it running?")
            except httpx.HTTPError as e:
                logger.error(f"HTTP error occurred: {str(e)}")
                logger.error(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response content'}")
                raise
                
    except Exception as e:
        logger.error(f"Error generating with Ollama: {str(e)}")
        logger.error(f"Full error details: {type(e).__name__}: {str(e)}")
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