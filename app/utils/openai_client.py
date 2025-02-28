import os
import json
import logging
from openai import OpenAI
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

def get_openai_client():
    """
    Create and return an OpenAI client using the API key from environment variables.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        logger.error("OpenAI API key is not set in environment variables")
        raise ValueError("OpenAI API key is not set in environment variables")
    
    try:
        client = OpenAI(api_key=api_key)
        logger.info("OpenAI client created successfully")
        return client
    except Exception as e:
        logger.error(f"Error creating OpenAI client: {str(e)}")
        raise

async def generate_grant_summary(grant_data):
    """
    Generate a summary of a grant using OpenAI's GPT model.
    
    Args:
        grant_data (dict): The grant data to summarize
        
    Returns:
        dict: The summary in JSON format
    """
    try:
        client = get_openai_client()
        
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
        
        # Prepare the prompt for GPT
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
        """
        
        # System message for GPT
        system_message = """You've been given a grant opportunity listing. Help summarize the opportunity in simple terms.
You must format your output as a JSON value that adheres to a given "JSON Schema" instance.

"JSON Schema" is a declarative language that allows you to annotate and validate JSON documents.

For example, the example "JSON Schema" instance {"properties": {"foo": {"description": "a list of test words", "type": "array", "items": {"type": "string"}}}, "required": ["foo"]}
would match an object with one required property, "foo". The "type" property specifies "foo" must be an "array", and the "description" property semantically describes it as "a list of test words". The items within "foo" must be strings.
Thus, the object {"foo": ["bar", "baz"]} is a well-formatted instance of this example "JSON Schema". The object {"properties": {"foo": ["bar", "baz"]}} is not well-formatted.

Your output will be parsed and type-checked according to the provided schema instance, so make sure all fields in your output match the schema exactly and there are no trailing commas!

Here is the JSON Schema instance your output must adhere to:
{"type":"object","properties":{"goal":{"type":["string","null"]},"duration":{"type":"string"},"success_criteria":{"type":"array","items":{"type":"string"}},"good_to_know":{"type":"array","items":{"type":"string"}}},"additionalProperties":false,"$schema":"http://json-schema.org/draft-07/schema#"}
"""
        
        # Call the OpenAI API
        logger.info(f"Generating summary for grant: {title}")
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
        response_content = response.choices[0].message.content
        
        # Parse the JSON from the response
        # First, find the JSON block if it's wrapped in markdown code blocks
        if "```json" in response_content and "```" in response_content:
            json_start = response_content.find("```json") + 7
            json_end = response_content.rfind("```")
            json_str = response_content[json_start:json_end].strip()
        else:
            # If not wrapped in code blocks, use the entire response
            json_str = response_content
        
        # Parse the JSON
        summary = json.loads(json_str)
        
        logger.info(f"Successfully generated summary for grant: {title}")
        return summary
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return {"error": f"Error generating summary: {str(e)}"} 