import os
from dotenv import load_dotenv
import pathlib

# Print current working directory
current_dir = os.getcwd()
print(f"Current working directory: {current_dir}")

# Check if .env file exists in the current directory
env_path = os.path.join(current_dir, '.env')
env_example_path = os.path.join(current_dir, '.env.example')
print(f".env file exists: {os.path.exists(env_path)}")
print(f".env.example file exists: {os.path.exists(env_example_path)}")

# Try to read the file directly to see its contents
print("\nReading .env file directly:")
try:
    with open(env_path, 'r') as f:
        env_contents = f.readlines()
        print(f"Number of lines in .env: {len(env_contents)}")
        for line in env_contents:
            # Print each line but mask sensitive values
            if line.strip() and not line.startswith('#'):
                key = line.split('=')[0] if '=' in line else line
                value = "***MASKED***" if "KEY" in key or "SECRET" in key else line.split('=')[1] if '=' in line else ""
                print(f"{key}={value.strip()}")
except Exception as e:
    print(f"Error reading .env file: {e}")

# Try to load with explicit path
print("\nTrying to load with explicit path:")
dotenv_path = pathlib.Path(env_path)
load_dotenv(dotenv_path=dotenv_path, verbose=True)

# Print the loaded environment variables (without sensitive values)
print(f"Loaded SUPABASE_URL: {'[SET]' if os.getenv('SUPABASE_URL') else '[NOT SET]'}")
print(f"Loaded SUPABASE_KEY: {'[SET]' if os.getenv('SUPABASE_KEY') else '[NOT SET]'}")

# Print the actual values (be careful with sensitive data)
print(f"SUPABASE_URL value: {os.getenv('SUPABASE_URL')}")
print(f"SUPABASE_KEY value (first 10 chars): {os.getenv('SUPABASE_KEY')[:10] if os.getenv('SUPABASE_KEY') else 'None'}") 