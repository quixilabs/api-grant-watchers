import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default_secret_key")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "default_webhook_secret")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    GRANTS_API_URL: str = "https://apply07.grants.gov/grantsws/rest/opportunities/search"
    
    # Project name
    PROJECT_NAME: str = "Grants Webhooks API"

settings = Settings()
