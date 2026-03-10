from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from pydantic import BaseModel
from core.db import get_db
from core.auth import get_optional_user_id
from core.ranking import update_interest_vector, update_trending_score
import json

router = APIRouter()

class EventCreate(BaseModel):
    video_id: str
    event_type: str
    watch_ratio: Optional[float] = None
    metadata: Optional[dict] = None

@router.post("/api/v1/events")
async def record_event(req: EventCreate, bg_tasks: BackgroundTasks, user_id: Optional[str] = Depends(get_optional_user_id), db: AsyncSession = Depends(get_db)):
    query = text("""
        INSERT INTO events (user_id, video_id, event_type, watch_ratio, metadata)
        VALUES (:user_id, :video_id, :event_type, :watch_ratio, :metadata)
        RETURNING id
    """)
    meta_json = json.dumps(req.metadata) if req.metadata else None
    await db.execute(query, {
        "user_id": user_id,
        "video_id": req.video_id,
        "event_type": req.event_type,
        "watch_ratio": req.watch_ratio,
        "metadata": meta_json
    })
    
    if user_id:
        # Update user interest vector counts
        uiv_query = text("""
            INSERT INTO user_interest_vectors (user_id, event_count)
            VALUES (:user_id, 1)
            ON CONFLICT (user_id) DO UPDATE SET event_count = user_interest_vectors.event_count + 1, updated_at = NOW()
            RETURNING event_count
        """)
        res = await db.execute(uiv_query, {"user_id": user_id})
        event_count = res.mappings().first()["event_count"]
        
        # Get tags AND categories for the video to track general semantic clusters
        tags_query = text("""
            SELECT tag_id FROM video_tags WHERE video_id = :video_id
            UNION ALL
            SELECT category_id AS tag_id FROM video_categories WHERE video_id = :video_id
        """)
        tags_res = await db.execute(tags_query, {"video_id": req.video_id})
        tag_ids = [str(r["tag_id"]) for r in tags_res.mappings().fetchall()]
        
        bg_tasks.add_task(update_interest_vector, user_id, tag_ids, req.event_type, req.watch_ratio, event_count)
        
    await db.commit()
    
    # Simple engagement velocity approximation
    if req.event_type in ["LIKE", "SHARE"]:
        velocity = 1.0
    elif req.event_type in ["SKIP", "DISLIKE"]:
        velocity = 0.0
    else:
        velocity = 0.5
    bg_tasks.add_task(update_trending_score, req.video_id, velocity)
    
    return {"status": "success"}
