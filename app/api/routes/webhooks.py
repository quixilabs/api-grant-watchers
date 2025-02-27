from fastapi import APIRouter, Depends, HTTPException, Request

router = APIRouter()

@router.post("/")
async def webhook_handler(request: Request):
    """
    Handle incoming webhooks.
    """
    return {"message": "Webhook received successfully"}
