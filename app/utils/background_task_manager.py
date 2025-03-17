import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.utils.supabase import get_supabase_client
from app.utils.deepseek_client import generate_grant_summary

logger = logging.getLogger(__name__)

class BackgroundTaskManager:
    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
        self.client = get_supabase_client()

    async def create_task_status(self, task_type: str, total_items: int) -> str:
        """Create a new task status record and return its ID."""
        result = self.client.table("background_task_status").insert({
            "task_type": task_type,
            "status": "running",
            "total_items": total_items,
            "processed_items": 0,
            "failed_items": 0
        }).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]["id"]
        raise Exception("Failed to create task status record")

    async def update_task_status(self, task_id: str, updates: Dict[str, Any]):
        """Update the status of a background task."""
        updates["last_updated_at"] = datetime.now(timezone.utc).isoformat()
        self.client.table("background_task_status").update(updates).eq("id", task_id).execute()

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a background task."""
        result = self.client.table("background_task_status").select("*").eq("id", task_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    async def process_grant_summaries(self, task_id: str, force_regenerate: bool = False):
        """Process grant summaries in the background with rate limiting."""
        try:
            # Get all grants
            result = self.client.table("grants").select("*").execute()
            if not result.data:
                await self.update_task_status(task_id, {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat()
                })
                return

            total_grants = len(result.data)
            processed = 0
            failed = 0

            for grant in result.data:
                try:
                    # Skip if already has a summary and not force regenerating
                    if grant.get("synopsis_summary") and not force_regenerate:
                        processed += 1
                        await self.update_task_status(task_id, {
                            "processed_items": processed,
                            "current_item_id": grant.get("id")
                        })
                        continue

                    # Generate summary
                    summary = await generate_grant_summary(grant)
                    
                    if "error" in summary:
                        failed += 1
                        logger.error(f"Failed to generate summary for grant {grant.get('id')}: {summary['error']}")
                    else:
                        # Update grant with summary
                        self.client.table("grants").update({
                            "synopsis_summary": summary
                        }).eq("id", grant.get("id")).execute()
                        processed += 1

                    # Update task status
                    await self.update_task_status(task_id, {
                        "processed_items": processed,
                        "failed_items": failed,
                        "current_item_id": grant.get("id")
                    })

                    # Wait for 15 seconds before processing next grant
                    await asyncio.sleep(15)  # 15 seconds

                except Exception as e:
                    failed += 1
                    logger.error(f"Error processing grant {grant.get('id')}: {str(e)}")
                    await self.update_task_status(task_id, {
                        "processed_items": processed,
                        "failed_items": failed,
                        "current_item_id": grant.get("id"),
                        "error_message": str(e)
                    })

            # Mark task as completed
            await self.update_task_status(task_id, {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat()
            })

        except Exception as e:
            logger.error(f"Background task error: {str(e)}")
            await self.update_task_status(task_id, {
                "status": "failed",
                "error_message": str(e),
                "completed_at": datetime.now(timezone.utc).isoformat()
            })

    async def start_grant_summary_task(self, force_regenerate: bool = False) -> str:
        """Start a new background task for generating grant summaries."""
        try:
            # Get total number of grants
            result = self.client.table("grants").select("*", count="exact").execute()
            total_grants = result.count if hasattr(result, 'count') else 0

            # Create task status record
            task_id = await self.create_task_status("grant_summary", total_grants)
            
            # Start the background task
            task = asyncio.create_task(self.process_grant_summaries(task_id, force_regenerate))
            self.tasks[task_id] = task
            
            return task_id
        except Exception as e:
            logger.error(f"Error starting grant summary task: {str(e)}")
            raise

    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all active background tasks."""
        result = self.client.table("background_task_status").select("*").eq("status", "running").execute()
        return {task["id"]: task for task in result.data}

    async def stop_task(self, task_id: str):
        """Stop a specific background task."""
        if task_id in self.tasks:
            self.tasks[task_id].cancel()
            del self.tasks[task_id]
            await self.update_task_status(task_id, {
                "status": "stopped",
                "completed_at": datetime.now(timezone.utc).isoformat()
            })

# Create a singleton instance
task_manager = BackgroundTaskManager() 