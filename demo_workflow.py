from prefect import flow, task
from prefect.logging import get_run_logger
from typing import Dict, Any

@task(name="Greet User")
def greet_user(name: str) -> Dict[str, Any]:
    """
    A simple task that greets a user
    
    Args:
        name: Name of the user to greet
        
    Returns:
        Dictionary containing the greeting message
    """
    logger = get_run_logger()
    greeting = f"Hello, {name}!"
    logger.info(greeting)
    
    return {
        "message": greeting,
        "success": True
    }

@flow(name="Hello World Flow")
def hello_world_flow(name: str = "World") -> Dict[str, Any]:
    """
    A simple flow that demonstrates basic Prefect functionality
    
    Args:
        name: Name to greet (default: "World")
        
    Returns:
        Dictionary containing the flow results
    """
    logger = get_run_logger()
    logger.info(f"Starting Hello World flow for {name}")
    
    # Call the greet_user task
    result = greet_user(name=name)
    
    if result["success"]:
        logger.info("Flow completed successfully")
    else:
        logger.error("Flow failed")
    
    return result

if __name__ == "__main__":
    # Example usage
    hello_world_flow(name="Prefect User")
