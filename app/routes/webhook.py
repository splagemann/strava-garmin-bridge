"""
Strava webhook handler routes.
"""
from fastapi import APIRouter, Request, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, StravaAuth
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/strava")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token")
):
    """
    Verify Strava webhook subscription.
    Strava sends a GET request to verify the webhook endpoint.
    """
    logger.info(f"Webhook verification request: mode={hub_mode}, token={hub_verify_token}")

    # Verify the token
    if hub_verify_token != settings.STRAVA_WEBHOOK_VERIFY_TOKEN:
        logger.error("Invalid verify token")
        raise HTTPException(status_code=403, detail="Invalid verify token")

    # Return the challenge
    return {"hub.challenge": hub_challenge}


@router.post("/strava")
async def handle_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Strava webhook events.
    Processes activity creation events and triggers sync.
    """
    try:
        data = await request.json()
        logger.info(f"Received webhook event: {data}")

        # Extract event details
        object_type = data.get("object_type")
        aspect_type = data.get("aspect_type")
        owner_id = data.get("owner_id")
        object_id = data.get("object_id")

        # Only process activity creation events
        if object_type == "activity" and aspect_type == "create":
            logger.info(f"Processing activity creation: activity_id={object_id}, athlete_id={owner_id}")

            # Find user by athlete_id
            strava_auth = db.query(StravaAuth).filter(
                StravaAuth.athlete_id == str(owner_id)
            ).first()

            if not strava_auth:
                logger.warning(f"No user found for athlete_id {owner_id}")
                return {"status": "ignored", "reason": "user_not_found"}

            user = strava_auth.user

            # Check if user has Garmin configured
            if not user.garmin_auth:
                logger.warning(f"User {user.id} has no Garmin credentials")
                return {"status": "ignored", "reason": "garmin_not_configured"}

            # Queue Celery task for async processing
            from app.tasks.sync_tasks import sync_activity_task
            task = sync_activity_task.delay(user.id, object_id)

            logger.info(f"Queued sync task {task.id} for activity {object_id}, user {user.id}")

            return {
                "status": "queued",
                "activity_id": object_id,
                "user_id": user.id,
                "task_id": task.id
            }

        else:
            logger.info(f"Ignoring event: {object_type}.{aspect_type}")
            return {"status": "ignored", "reason": "not_activity_creation"}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        # Return 200 to prevent Strava from retrying
        return {"status": "error", "message": str(e)}


@router.post("/subscribe")
async def create_subscription():
    """
    Create a webhook subscription with Strava.
    This endpoint is for admin use to set up the webhook.
    """
    try:
        from app.services.strava_service import StravaService

        callback_url = f"{settings.BASE_URL}/webhook/strava"
        subscription = StravaService.create_webhook_subscription(callback_url)

        return {
            "message": "Webhook subscription created",
            "subscription": subscription
        }

    except Exception as e:
        logger.error(f"Error creating subscription: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
