import asyncio
import logging
import uuid
import time
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

# Global dictionary to store task status
tasks = {}

class TaskStatus:
    """Class to track the status of a background task"""
    def __init__(self, task_id: str, task_type: str, organization_id: str):
        self.id = task_id
        self.task_type = task_type
        self.organization_id = organization_id
        self.status = "pending"  # pending, running, completed, failed
        self.total_items = 0
        self.processed_items = 0
        self.matched_items = 0
        self.failed_items = 0
        self.current_item_id = None
        self.current_item_name = None
        self.started_at = None
        self.completed_at = None
        self.last_updated_at = datetime.now().isoformat()
        self.error = None
        self.result = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task status to dictionary"""
        return {
            "id": self.id,
            "task_type": self.task_type,
            "organization_id": self.organization_id,
            "status": self.status,
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "matched_items": self.matched_items,
            "failed_items": self.failed_items,
            "current_item_id": self.current_item_id,
            "current_item_name": self.current_item_name,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "last_updated_at": self.last_updated_at,
            "progress_percentage": self.get_progress_percentage(),
            "error": self.error
        }
    
    def get_progress_percentage(self) -> int:
        """Calculate progress percentage"""
        if self.total_items == 0:
            return 0
        return int((self.processed_items / self.total_items) * 100)
    
    def update(self, **kwargs):
        """Update task status"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_updated_at = datetime.now().isoformat()

async def run_background_task(
    task_id: str,
    organization_id: str,
    task_func: Callable,
    *args,
    **kwargs
) -> None:
    """
    Run a task in the background and track its status
    
    Args:
        task_id: Unique identifier for the task
        organization_id: ID of the organization
        task_func: Async function to run
        args: Positional arguments for task_func
        kwargs: Keyword arguments for task_func
    """
    task_status = tasks.get(task_id)
    if not task_status:
        logger.error(f"Task {task_id} not found")
        return
    
    try:
        # Update task status to running
        task_status.update(
            status="running",
            started_at=datetime.now().isoformat()
        )
        
        # Run the task
        result = await task_func(task_id, *args, **kwargs)
        
        # Update task status to completed
        task_status.update(
            status="completed",
            completed_at=datetime.now().isoformat(),
            result=result
        )
        
    except Exception as e:
        logger.error(f"Error in background task {task_id}: {str(e)}")
        # Update task status to failed
        task_status.update(
            status="failed",
            completed_at=datetime.now().isoformat(),
            error=str(e)
        )

def create_task(task_type: str, organization_id: str) -> str:
    """
    Create a new task and return its ID
    
    Args:
        task_type: Type of task (e.g., "grant_matching")
        organization_id: ID of the organization
        
    Returns:
        str: Task ID
    """
    task_id = str(uuid.uuid4())
    tasks[task_id] = TaskStatus(task_id, task_type, organization_id)
    return task_id

def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the status of a task
    
    Args:
        task_id: ID of the task
        
    Returns:
        Optional[Dict[str, Any]]: Task status or None if not found
    """
    task = tasks.get(task_id)
    if task:
        return task.to_dict()
    return None

def get_organization_tasks(organization_id: str) -> List[Dict[str, Any]]:
    """
    Get all tasks for an organization
    
    Args:
        organization_id: ID of the organization
        
    Returns:
        List[Dict[str, Any]]: List of task statuses
    """
    return [
        task.to_dict() 
        for task in tasks.values() 
        if task.organization_id == organization_id
    ]

def update_task_status(task_id: str, **kwargs) -> bool:
    """
    Update the status of a task
    
    Args:
        task_id: ID of the task
        kwargs: Key-value pairs to update
        
    Returns:
        bool: True if task was updated, False otherwise
    """
    task = tasks.get(task_id)
    if task:
        task.update(**kwargs)
        return True
    return False 