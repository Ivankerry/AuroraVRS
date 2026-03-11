from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
import uuid
import shutil
import os
import json
from pydantic import BaseModel
from core.db import get_db
from core.auth import get_current_user_id, get_optional_user_id

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])

class UploadStart(BaseModel):
    title: str
    description: Optional[str] = None
    type: str
    privacy: str = "PUBLIC"

class CommentCreate(BaseModel):
    content: str
    
class PrivacyUpdate(BaseModel):
    privacy: str

@router.post("/upload")
async def upload_video(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    type: str = Form(...),
    privacy: str = Form("PUBLIC"),
    category_ids: str = Form("[]"),
    tag_ids: str = Form("[]"),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    # 1. Save file to disk
    v_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"{v_id}{file_ext}"
    storage_path = "/app/storage/videos"
    file_path = os.path.join(storage_path, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. Add to database
    manifest_url = f"/api/v1/videos/content/{filename}"
    
    try:
        query = text("""
            INSERT INTO videos (id, creator_id, title, description, type, privacy, status, manifest_url) 
            VALUES (:v_id, :creator_id, :title, :description, :type, :privacy, 'READY', :manifest_url)
            RETURNING id
        """)
        await db.execute(query, {
            "v_id": v_id,
            "creator_id": user_id, 
            "title": title, 
            "description": description,
            "type": type, 
            "privacy": privacy,
            "manifest_url": manifest_url
        })
        
        # 3. Handle categories
        cats = json.loads(category_ids)
        for cat_id in cats:
            await db.execute(text("INSERT INTO video_categories (video_id, category_id) VALUES (:v_id, :cat_id)"), {"v_id": v_id, "cat_id": cat_id})
            
        # 4. Handle tags
        tags = json.loads(tag_ids)
        for tag_id in tags:
            await db.execute(text("INSERT INTO video_tags (video_id, tag_id) VALUES (:v_id, :tag_id)"), {"v_id": v_id, "tag_id": tag_id})
            
        await db.commit()
    except Exception as e:
        await db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return {"status": "success", "video_id": v_id, "manifest_url": manifest_url}

@router.post("/upload/start")
async def start_upload(req: UploadStart, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    query = text("""
        INSERT INTO videos (creator_id, title, description, type, privacy, status) 
        VALUES (:creator_id, :title, :description, :type, :privacy, 'UPLOADING')
        RETURNING id
    """)
    result = await db.execute(query, {
        "creator_id": user_id, "title": req.title, "description": req.description,
        "type": req.type, "privacy": req.privacy
    })
    video = result.mappings().first()
    await db.commit()
    # In a real app we'd generate an S3 presigned URL here
    return {"video_id": str(video["id"]), "upload_url": f"https://files.example.com/upload/{video['id']}"}

@router.post("/upload/complete")
async def complete_upload(video_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    query = text("UPDATE videos SET status = 'PROCESSING' WHERE id = :id AND creator_id = :creator_id AND status = 'UPLOADING' RETURNING id")
    result = await db.execute(query, {"id": video_id, "creator_id": user_id})
    if not result.mappings().first():
        raise HTTPException(status_code=404, detail="Video not found or invalid state")
    await db.commit()
    # In a real app we'd trigger ffmpeg via a message queue here
    # For simulation, just mark it ready
    mark_ready = text("UPDATE videos SET status = 'READY', duration_sec = 60, manifest_url = 'dummy.m3u8' WHERE id = :id")
    await db.execute(mark_ready, {"id": video_id})
    await db.commit()
    return {"status": "success"}

@router.get("/upload/{id}/status")
async def get_upload_status(id: str, db: AsyncSession = Depends(get_db)):
    query = text("SELECT status FROM videos WHERE id = :id")
    result = await db.execute(query, {"id": id})
    video = result.mappings().first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"status": video["status"]}

@router.get("/")
async def get_videos(page: int = 1, limit: int = 20, db: AsyncSession = Depends(get_db)):
    offset = (page - 1) * limit
    query = text("SELECT * FROM videos WHERE status = 'READY' AND privacy = 'PUBLIC' ORDER BY created_at DESC LIMIT :limit OFFSET :offset")
    result = await db.execute(query, {"limit": limit, "offset": offset})
    return [dict(r) for r in result.mappings().fetchall()]

@router.get("/search")
async def search_videos(q: str, db: AsyncSession = Depends(get_db)):
    query = text("SELECT * FROM videos WHERE status = 'READY' AND privacy = 'PUBLIC' AND title ILIKE :q LIMIT 20")
    result = await db.execute(query, {"q": f"%{q}%"})
    return [dict(r) for r in result.mappings().fetchall()]

@router.get("/{id}")
async def get_video(id: str, user_id: Optional[str] = Depends(get_optional_user_id), db: AsyncSession = Depends(get_db)):
    query = text("SELECT * FROM videos WHERE id = :id")
    result = await db.execute(query, {"id": id})
    video = result.mappings().first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    if video["privacy"] == "PRIVATE" and str(video["creator_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Private video")
        
    return dict(video)

@router.delete("/{id}")
async def delete_video(id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    query = text("DELETE FROM videos WHERE id = :id AND creator_id = :creator_id RETURNING id")
    result = await db.execute(query, {"id": id, "creator_id": user_id})
    if not result.mappings().first():
        raise HTTPException(status_code=404, detail="Video not found or not owner")
    await db.commit()
    return {"status": "success"}

@router.patch("/{id}/privacy")
async def update_privacy(id: str, req: PrivacyUpdate, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    query = text("UPDATE videos SET privacy = :privacy WHERE id = :id AND creator_id = :creator_id RETURNING id")
    result = await db.execute(query, {"id": id, "creator_id": user_id, "privacy": req.privacy})
    if not result.mappings().first():
        raise HTTPException(status_code=404, detail="Video not found or not owner")
    await db.commit()
    return {"status": "success"}

@router.post("/{id}/view")
async def record_view(id: str, db: AsyncSession = Depends(get_db)):
    query = text("UPDATE videos SET view_count = view_count + 1 WHERE id = :id")
    await db.execute(query, {"id": id})
    await db.commit()
    return {"status": "success"}

@router.post("/{id}/like")
async def like_video(id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    try:
        q1 = text("INSERT INTO likes (user_id, video_id) VALUES (:user_id, :video_id) ON CONFLICT DO NOTHING RETURNING user_id")
        res = await db.execute(q1, {"user_id": user_id, "video_id": id})
        if res.mappings().first():
            q2 = text("UPDATE videos SET like_count = like_count + 1 WHERE id = :id")
            await db.execute(q2, {"id": id})
            # Remove dislike if exists
            q3 = text("DELETE FROM dislikes WHERE user_id = :user_id AND video_id = :video_id RETURNING user_id")
            res3 = await db.execute(q3, {"user_id": user_id, "video_id": id})
            if res3.mappings().first():
                q4 = text("UPDATE videos SET dislike_count = dislike_count - 1 WHERE id = :id")
                await db.execute(q4, {"id": id})
        await db.commit()
    except Exception:
        await db.rollback()
    return {"status": "success"}

@router.post("/{id}/dislike")
async def dislike_video(id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    try:
        q1 = text("INSERT INTO dislikes (user_id, video_id) VALUES (:user_id, :video_id) ON CONFLICT DO NOTHING RETURNING user_id")
        res = await db.execute(q1, {"user_id": user_id, "video_id": id})
        if res.mappings().first():
            q2 = text("UPDATE videos SET dislike_count = dislike_count + 1 WHERE id = :id")
            await db.execute(q2, {"id": id})
            # Remove like if exists
            q3 = text("DELETE FROM likes WHERE user_id = :user_id AND video_id = :video_id RETURNING user_id")
            res3 = await db.execute(q3, {"user_id": user_id, "video_id": id})
            if res3.mappings().first():
                q4 = text("UPDATE videos SET like_count = like_count - 1 WHERE id = :id")
                await db.execute(q4, {"id": id})
        await db.commit()
    except Exception:
        await db.rollback()
    return {"status": "success"}

@router.get("/{id}/comments")
async def get_comments(id: str, db: AsyncSession = Depends(get_db)):
    query = text("""
        SELECT c.*, u.names, u.avatar_url 
        FROM comments c 
        JOIN users u ON u.id = c.user_id 
        WHERE c.video_id = :id 
        ORDER BY c.created_at DESC LIMIT 50
    """)
    result = await db.execute(query, {"id": id})
    return [dict(r) for r in result.mappings().fetchall()]

@router.post("/{id}/comments")
async def create_comment(id: str, req: CommentCreate, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    query = text("INSERT INTO comments (user_id, video_id, content) VALUES (:user_id, :video_id, :content) RETURNING id")
    await db.execute(query, {"user_id": user_id, "video_id": id, "content": req.content})
    update_q = text("UPDATE videos SET comment_count = comment_count + 1 WHERE id = :id")
    await db.execute(update_q, {"id": id})
    await db.commit()
    return {"status": "success"}
