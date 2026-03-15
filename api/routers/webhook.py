"""
AURORA — SHIELD Webhook Handler
Receives moderation verdicts from SHIELD and acts on them.

SHIELD sends POST requests to /api/v1/shield/webhook after:
  1. AI pipeline completes (automatic verdict)
  2. Human moderator makes a decision in SHIELD dashboard (human override)

Verdict actions:
  APPROVE       → set streaming_ready = true
  REVIEW        → keep streaming_ready = false, wait for human override
  REMOVE        → set streaming_ready = false, delete file, mark removed
  CSAM          → set streaming_ready = false, delete file, suspend user, log critical
"""

import os
import shutil
import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db

logger = logging.getLogger("aurora.shield_webhook")

router = APIRouter()

VIDEO_STORAGE_PATH = os.getenv("VIDEO_STORAGE_PATH", "/app/storage/videos")

# ── Webhook payload model ────────────────────────────────────────────────────

class ShieldWebhookPayload(BaseModel):
    job_id:            str
    platform_video_id: str
    verdict:           str
    confidence:        float
    flags:             List[str] = []
    action_required:   bool = False
    human_reviewed:    Optional[bool] = False
    moderator_action:  Optional[str] = None


# ── Helper: delete video files from disk ─────────────────────────────────────

def delete_video_files(video_id: str) -> bool:
    """
    Deletes the video directory for a given video_id.
    Videos are stored at VIDEO_STORAGE_PATH/{video_id}/
    Returns True if deleted, False if directory not found.
    """
    # Check directory layout
    video_dir = os.path.join(VIDEO_STORAGE_PATH, video_id)
    if os.path.isdir(video_dir):
        try:
            shutil.rmtree(video_dir)
            logger.info(f"Deleted video files for {video_id} at {video_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete video files for {video_id}: {e}")
            return False
    else:
        # Try flat file layout: VIDEO_STORAGE_PATH/{video_id}.mp4 etc.
        deleted = False
        for ext in [".mp4", ".m3u8", ".ts", ".webm", ".m4v"]:
            path = os.path.join(VIDEO_STORAGE_PATH, video_id + ext)
            if os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"Deleted {path}")
                    deleted = True
                except Exception as e:
                    logger.error(f"Failed to delete {path}: {e}")
        return deleted


# ── Helper: get video and uploader from DB ────────────────────────────────────

async def get_video(db: AsyncSession, video_id: str) -> dict:
    """Fetch video row. Returns None if not found."""
    # Modified from prompt: creator_id instead of user_id
    result = await db.execute(
        text("SELECT id, creator_id, streaming_ready, status FROM videos WHERE id = :id"),
        {"id": video_id}
    )
    row = result.mappings().first()
    return dict(row) if row else None


# ── Webhook endpoint ──────────────────────────────────────────────────────────

@router.post("/shield/webhook")
async def shield_webhook(payload: ShieldWebhookPayload, db: AsyncSession = Depends(get_db)):
    """
    Receives moderation verdicts from SHIELD and acts on AURORA's database
    and file system accordingly.
    """
    video_id  = payload.platform_video_id
    verdict   = payload.verdict.upper()
    job_id    = payload.job_id
    human     = payload.human_reviewed or False
    mod_action = (payload.moderator_action or "").upper()

    logger.info(
        f"SHIELD webhook received | job={job_id} | video={video_id} | "
        f"verdict={verdict} | human={human} | mod_action={mod_action} | "
        f"confidence={payload.confidence:.4f} | flags={payload.flags}"
    )

    # Look up the video
    video = await get_video(db, video_id)
    if not video:
        # Video may have been deleted already — log and return 200
        # Returning 4xx would cause SHIELD to retry indefinitely
        logger.warning(f"Video {video_id} not found in database — ignoring webhook")
        return {"status": "ignored", "reason": "video not found"}

    # ── APPROVE ────────────────────────────────────────────────────────────────
    if verdict == "APPROVE":
        await db.execute(
            text("UPDATE videos SET streaming_ready = true WHERE id = :id"),
            {"id": video_id}
        )
        await db.commit()
        logger.info(f"Video {video_id} APPROVED — streaming_ready set to true")
        return {"status": "ok", "action": "approved", "video_id": video_id}

    # ── REVIEW ─────────────────────────────────────────────────────────────────
    if verdict == "REVIEW":
        # Keep streaming_ready = false — video is held pending human review
        # A human override webhook will arrive later from SHIELD dashboard
        await db.execute(
            text("UPDATE videos SET streaming_ready = false WHERE id = :id"),
            {"id": video_id}
        )
        await db.commit()
        logger.info(f"Video {video_id} HELD FOR REVIEW — awaiting moderator decision")
        return {"status": "ok", "action": "held_for_review", "video_id": video_id}

    # ── REMOVE ─────────────────────────────────────────────────────────────────
    if verdict == "REMOVE":
        # Mark removed in database
        await db.execute(
            text("""
                UPDATE videos
                SET streaming_ready = false,
                    status = 'REMOVED'
                WHERE id = :id
            """),
            {"id": video_id}
        )
        # Delete physical files
        deleted = delete_video_files(video_id)

        # If moderator action was BAN_ACCOUNT, suspend the user
        if mod_action == "BAN_ACCOUNT" and video.get("creator_id"):
            await db.execute(
                text("UPDATE users SET is_active = false WHERE id = :uid"),
                {"uid": video["creator_id"]}
            )
            logger.warning(f"User {video['creator_id']} account suspended (BAN_ACCOUNT)")

        await db.commit()
        logger.warning(
            f"Video {video_id} REMOVED | "
            f"files_deleted={deleted} | human={human} | mod_action={mod_action}"
        )
        return {
            "status": "ok", "action": "removed",
            "video_id": video_id, "files_deleted": deleted
        }

    # ── CSAM ───────────────────────────────────────────────────────────────────
    if verdict == "CSAM":
        # Step 1: Mark removed immediately
        await db.execute(
            text("""
                UPDATE videos
                SET streaming_ready = false,
                    status = 'CSAM_REMOVED'
                WHERE id = :id
            """),
            {"id": video_id}
        )

        # Step 2: Delete physical files
        deleted = delete_video_files(video_id)

        # Step 3: Suspend the uploading user's account
        # Do NOT notify the user — this could alert a bad actor
        if video.get("creator_id"):
            await db.execute(
                text("UPDATE users SET is_active = false WHERE id = :uid"),
                {"uid": video["creator_id"]}
            )
            logger.critical(
                f"CSAM — User {video['creator_id']} account suspended silently"
            )

        await db.commit()
        # Step 4: Log at CRITICAL level — this is a legal event
        logger.critical(
            f"CSAM CONTENT REMOVED | video={video_id} | job={job_id} | "
            f"user={video.get('creator_id')} | files_deleted={deleted} | "
            f"confidence={payload.confidence} | flags={payload.flags} | "
            f"ACTION REQUIRED: File NCMEC CyberTipline report manually at "
            f"https://www.missingkids.org/gethelpnow/cybertipline"
        )

        return {
            "status": "ok", "action": "csam_removed",
            "video_id": video_id, "files_deleted": deleted,
            "ncmec_report_required": True
        }

    # ── Unknown verdict ────────────────────────────────────────────────────────
    logger.error(f"Unknown verdict '{verdict}' received from SHIELD for video {video_id}")
    return {"status": "error", "reason": f"unknown verdict: {verdict}"}
