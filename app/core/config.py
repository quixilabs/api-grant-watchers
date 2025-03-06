import os
import logging
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field

# Set up logging
logger = logging.getLogger(__name__)

# Function to read .env file and set environment variables directly
def load_env_manually(env_path):
    logger.info(f"Manually loading environment from: {env_path}")
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
                    if 'KEY' in key or 'SECRET' in key:
                        logger.info(f"Set {key}=[MASKED]")
                    else:
                        logger.info(f"Set {key}={value}")
        return True
    except Exception as e:
        logger.error(f"Error reading .env file: {e}")
        return False

# Try to load environment variables manually first
env_path = os.path.join(os.getcwd(), '.env')
if os.path.exists(env_path):
    load_env_manually(env_path)
else:
    logger.warning(f".env file not found at {env_path}")
    # Fallback to python-dotenv
    logger.info("Falling back to python-dotenv")
    load_dotenv(verbose=True)

# Log the loaded environment variables (without sensitive values)
logger.info(f"Loaded SUPABASE_URL: {'[SET]' if os.environ.get('SUPABASE_URL') else '[NOT SET]'}")
logger.info(f"Loaded SUPABASE_KEY: {'[SET]' if os.environ.get('SUPABASE_KEY') else '[NOT SET]'}")
logger.info(f"Loaded OPENAI_API_KEY: {'[SET]' if os.environ.get('OPENAI_API_KEY') else '[NOT SET]'}")
logger.info(f"Loaded DEEPSEEK_API_KEY: {'[SET]' if os.environ.get('DEEPSEEK_API_KEY') else '[NOT SET]'}")
logger.info(f"SUPABASE_URL value: {os.environ.get('SUPABASE_URL', '')}")
logger.info(f"SUPABASE_KEY value (first 10 chars): {os.environ.get('SUPABASE_KEY', '')[:10] if os.environ.get('SUPABASE_KEY') else 'None'}")

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "default_secret_key")
    WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "default_webhook_secret")
    SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    GRANTS_API_URL: str = "https://apply07.grants.gov/grantsws/rest/opportunities/search"
    BEEHIIV_API_KEY: str = os.environ.get("BEEHIIV_API_KEY", "")
    BEEHIIV_PUBLICATION_ID: str = os.environ.get("BEEHIIV_PUBLICATION_ID", "")
    
    # DeepSeek API
    DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
    
    # Project name
    PROJECT_NAME: str = "Grants Webhooks API"
    
    # Add Mailgun settings
    mailgun_api_key: str = Field(alias="MAILGUN_API_KEY")
    mailgun_domain: str = Field(alias="MAILGUN_DOMAIN")
    mailgun_from_email: str = Field(alias="MAILGUN_FROM_EMAIL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings()
logger.info(f"Settings initialized with SUPABASE_URL: {settings.SUPABASE_URL}")
logger.info(f"Settings initialized with SUPABASE_KEY: {'[SET]' if settings.SUPABASE_KEY else '[NOT SET]'}")
logger.info(f"Settings initialized with OPENAI_API_KEY: {'[SET]' if settings.OPENAI_API_KEY else '[NOT SET]'}")
logger.info(f"Settings initialized with DEEPSEEK_API_KEY: {'[SET]' if settings.DEEPSEEK_API_KEY else '[NOT SET]'}")
