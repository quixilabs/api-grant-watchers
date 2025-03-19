import subprocess
import sys
import os
import traceback

def run_command(command, env=None):
    """Run a shell command and print output"""
    print(f"Running: {command}")
    
    # Create a copy of the current environment
    cmd_env = os.environ.copy()
    
    # Update with any additional environment variables
    if env:
        cmd_env.update(env)
    
    try:
        # Run with shell=False for better error handling
        args = command.split()
        result = subprocess.run(args, capture_output=True, text=True, env=cmd_env)
        
        print(f"Command exit code: {result.returncode}")
        
        if result.stdout:
            print(f"Command stdout: {result.stdout}")
        
        if result.returncode != 0:
            if result.stderr:
                print(f"Command stderr: {result.stderr}")
            else:
                print("Command failed but no stderr output was captured")
            return False
        
        return True
    except Exception as e:
        print(f"Exception running command: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        # Get the absolute paths to the workflow files
        main_workflow_path = os.path.abspath("prefect_workflows.py")
        org_workflow_path = os.path.abspath("organization_workflow.py")
        details_workflow_path = os.path.abspath("grant_details_workflow.py")
        print(f"Main workflow path: {main_workflow_path}")
        print(f"Organization workflow path: {org_workflow_path}")
        print(f"Grant details workflow path: {details_workflow_path}")
        
        # Get the Prefect server URL (default is http://127.0.0.1:4200)
        server_url = os.getenv("PREFECT_API_URL", "https://api.prefect.cloud/api")
        # server_url = "https://api.prefect.cloud/api/accounts/quixi-labs/workspaces/default"
        # # server_url = "https://api.prefect.cloud/api"
        
        print(f"Creating deployments using Prefect 3.0 CLI (connecting to {server_url})...")
        
        # Set up environment with PREFECT_API_URL
        env = {"PREFECT_API_URL": server_url}
        
        # Try a simpler command first to verify Prefect is working
        print("Checking Prefect version...")
        if not run_command("prefect version", env):
            print("Failed to get Prefect version. Please check your Prefect installation.")
            sys.exit(1)
        
        # Create the work pool if it doesn't exist
        print("\nCreating work pool 'default'...")
        create_pool_cmd = "prefect work-pool create default --type process"
        run_command(create_pool_cmd, env)  # Continue even if it fails (might already exist)
        
        # Create daily deployment with correct --pool flag
        print("\nCreating daily deployment...")
        daily_cmd = f"prefect deploy {main_workflow_path}:grant_processing_pipeline -n daily-grant-processing --pool default --param date_range=1"
        if not run_command(daily_cmd, env):
            print("Failed to create daily deployment. Trying alternative syntax...")
            # Try alternative syntax
            alt_daily_cmd = f"python -m prefect deploy {main_workflow_path}:grant_processing_pipeline -n daily-grant-processing --pool default --param date_range=1"
            if not run_command(alt_daily_cmd, env):
                sys.exit(1)
        
        # Create weekly deployment with correct --pool flag
        print("\nCreating weekly deployment...")
        weekly_cmd = f"prefect deploy {main_workflow_path}:grant_processing_pipeline -n weekly-grant-processing --pool default --param date_range=7"
        if not run_command(weekly_cmd, env):
            print("Failed to create weekly deployment. Trying alternative syntax...")
            # Try alternative syntax
            alt_weekly_cmd = f"python -m prefect deploy {main_workflow_path}:grant_processing_pipeline -n weekly-grant-processing --pool default --param date_range=7"
            if not run_command(alt_weekly_cmd, env):
                sys.exit(1)
        
        # Create organization-specific workflow deployment
        print("\nCreating organization workflow deployment...")
        org_cmd = f"prefect deploy {org_workflow_path}:organization_grant_processing_pipeline -n organization-grant-processing --pool default"
        if not run_command(org_cmd, env):
            print("Failed to create organization workflow deployment. Trying alternative syntax...")
            # Try alternative syntax
            alt_org_cmd = f"python -m prefect deploy {org_workflow_path}:organization_grant_processing_pipeline -n organization-grant-processing --pool default"
            if not run_command(alt_org_cmd, env):
                sys.exit(1)
        
        # Create grant details workflow deployment
        print("\nCreating grant details workflow deployment...")
        details_cmd = f"prefect deploy {details_workflow_path}:grant_details_summaries_pipeline -n grant-details-summaries --pool default"
        if not run_command(details_cmd, env):
            print("Failed to create grant details workflow deployment. Trying alternative syntax...")
            # Try alternative syntax
            alt_details_cmd = f"python -m prefect deploy {details_workflow_path}:grant_details_summaries_pipeline -n grant-details-summaries --pool default"
            if not run_command(alt_details_cmd, env):
                sys.exit(1)
        
        print("\nDeployments created successfully!")
        print("- daily-grant-processing: For processing grants from the last day")
        print("- weekly-grant-processing: For processing grants from the last week")
        print("- organization-grant-processing: For processing a specific organization")
        print("- grant-details-summaries: For processing all grants to ensure they have details and summaries")
        print("\nTo run these deployments manually:")
        print(f"PREFECT_API_URL={server_url} prefect deployment run grant-processing-pipeline/daily-grant-processing")
        print(f"PREFECT_API_URL={server_url} prefect deployment run grant-processing-pipeline/weekly-grant-processing")
        print(f"PREFECT_API_URL={server_url} prefect deployment run organization-grant-processing-pipeline/organization-grant-processing --param organization_name_or_id=\"Organization Name\" --param date_range=30")
        print(f"PREFECT_API_URL={server_url} prefect deployment run grant-details-summaries/grant-details-summaries --param max_details_grants=100 --param max_summary_grants=20")
        print("\nTo start a worker:")
        print(f"PREFECT_API_URL={server_url} prefect worker start --pool default")
    except Exception as e:
        print(f"Error in deployment script: {str(e)}")
        traceback.print_exc()
        sys.exit(1) 