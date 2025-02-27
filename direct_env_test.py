import os

# Function to read .env file and set environment variables directly
def load_env_manually(env_path):
    print(f"Manually loading environment from: {env_path}")
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
                    print(f"Set {key}={value if 'URL' in key else '***MASKED***'}")
    except Exception as e:
        print(f"Error reading .env file: {e}")

# Current directory
current_dir = os.getcwd()
print(f"Current working directory: {current_dir}")

# Path to .env file
env_path = os.path.join(current_dir, '.env')

# Load environment variables manually
load_env_manually(env_path)

# Print the environment variables
print("\nEnvironment variables after manual loading:")
print(f"SUPABASE_URL: {os.environ.get('SUPABASE_URL', 'Not set')}")
print(f"SUPABASE_KEY (first 10 chars): {os.environ.get('SUPABASE_KEY', 'Not set')[:10] if os.environ.get('SUPABASE_KEY') else 'Not set'}")

# Now update the config.py file to use os.environ directly
print("\nSuggested update for config.py:")
print("""
class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "default_secret_key")
    WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "default_webhook_secret")
    SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")
    GRANTS_API_URL: str = "https://apply07.grants.gov/grantsws/rest/opportunities/search"
""") 