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