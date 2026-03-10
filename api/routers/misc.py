from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from pydantic import BaseModel
from core.db import get_db
from core.auth import get_current_user_id, require_admin

router = APIRouter()

class NameRequest(BaseModel):
    name: str

class NotificationUpdate(BaseModel):
    read: bool

@router.get("/api/v1/content/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    query = text("SELECT * FROM categories ORDER BY name")
    result = await db.execute(query)
    return [dict(r) for r in result.mappings().fetchall()]

@router.post("/api/v1/content/categories", dependencies=[Depends(require_admin)])
async def create_category(req: NameRequest, db: AsyncSession = Depends(get_db)):
    query = text("INSERT INTO categories (name) VALUES (:name) RETURNING id")
    try:
        result = await db.execute(query, {"name": req.name})
        await db.commit()
        return {"id": str(result.mappings().first()["id"])}
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Category exists")

@router.get("/api/v1/content/tags")
async def get_tags(db: AsyncSession = Depends(get_db)):
    query = text("SELECT * FROM tags ORDER BY name")
    result = await db.execute(query)
    return [dict(r) for r in result.mappings().fetchall()]

@router.post("/api/v1/content/tags")
async def create_tag(req: NameRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    query = text("INSERT INTO tags (name) VALUES (:name) RETURNING id")
    try:
        result = await db.execute(query, {"name": req.name.lower()})
        await db.commit()
        return {"id": str(result.mappings().first()["id"])}
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Tag exists")

@router.get("/api/v1/notifications")
async def get_notifications(user_id: str = Depends(get_current_user_id)):
    return [] # stubbed

@router.patch("/api/v1/notifications/{id}")
async def update_notification(id: str, req: NotificationUpdate, user_id: str = Depends(get_current_user_id)):
    return {"status": "success"} # stubbed

@router.get("/api/v1/analytics/videos/{id}")
async def get_video_analytics(id: str, db: AsyncSession = Depends(get_db)):
    query = text("SELECT view_count, like_count, dislike_count, comment_count, share_count, avg_watch_ratio FROM videos WHERE id = :id")
    result = await db.execute(query, {"id": id})
    video = result.mappings().first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return dict(video)
