from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile, Form
import logging
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
logger = logging.getLogger(__name__)

class UploadStart(BaseModel):
    title: str
    description: Optional[str] = None
    type: str
    privacy: str = "PUBLIC"

class VideoRegister(BaseModel):
    id: str  # Pre-defined UUID or item_id
    title: str
    description: Optional[str] = "Imported"
    type: str = "QUICK"
    privacy: str = "PUBLIC"
    manifest_url: str
    categories: List[str] = []
    tags: List[str] = []
    view_count: int = 0
    like_count: int = 0

class CommentCreate(BaseModel):
    content: str
    
class PrivacyUpdate(BaseModel):
    privacy: str

@router.post("/upload")
async def upload_video(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    type: Optional[str] = Form("QUICK"),
    privacy: str = Form("PUBLIC"),
    category_ids: Optional[str] = Form("[]"),
    tag_ids: Optional[str] = Form("[]"),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    # Sanitize JSON inputs
    if not category_ids or category_ids.strip() == "":
        category_ids = "[]"
    if not tag_ids or tag_ids.strip() == "":
        tag_ids = "[]"

    # Normalize type to match DB constraints
    if type and type.upper() == "LONG":
        type = "LONGFORM"
    elif not type:
        type = "QUICK"
    else:
        type = type.upper()

    # 1. Save file to disk
    v_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"{v_id}{file_ext}"
    storage_path = os.getenv("VIDEO_STORAGE_PATH", "/app/storage/videos")
    file_path = os.path.join(storage_path, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"❌ FILE SYSTEM ERROR: Could not save video to {file_path}. Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File system error: {str(e)}")
    
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
        try:
            cats = json.loads(category_ids)
            if not isinstance(cats, list):
                cats = [cats] if cats else []
        except:
            cats = []

        for cat_id in cats:
            if cat_id:
                await db.execute(text("INSERT INTO video_categories (video_id, category_id) VALUES (:v_id, :cat_id)"), {"v_id": v_id, "cat_id": cat_id})
            
        # 4. Handle tags
        try:
            tags = json.loads(tag_ids)
            if not isinstance(tags, list):
                tags = [tags] if tags else []
        except:
            tags = []

        for tag_id in tags:
            if tag_id:
                await db.execute(text("INSERT INTO video_tags (video_id, tag_id) VALUES (:v_id, :tag_id)"), {"v_id": v_id, "tag_id": tag_id})
            
        await db.commit()
    except Exception as e:
        await db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"❌ DATABASE ERROR during upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return {"status": "success", "video_id": v_id, "manifest_url": manifest_url}

@router.post("/register")
async def register_video(req: VideoRegister, user_id: Optional[str] = Depends(get_optional_user_id), db: AsyncSession = Depends(get_db)):
    # Use provided user_id if present (e.g. from token), else use a default system/seeder user
    creator_id = user_id or "00000000-0000-0000-0000-000000000000"
    
    try:
        # 1. Ensure the creator user exists (System user for seeding)
        if not user_id:
            await db.execute(text("""
                INSERT INTO users (id, names, email, role) 
                VALUES (:creator_id, 'System Seeder', 'seeder@aurora.vrs', 'ADMIN') 
                ON CONFLICT (id) DO NOTHING
            """), {"creator_id": creator_id})

        # 2. Register Video
        query = text("""
            INSERT INTO videos (id, creator_id, title, description, type, privacy, status, manifest_url, view_count, like_count) 
            VALUES (:v_id, :creator_id, :title, :description, :type, :privacy, 'READY', :manifest_url, :view_count, :like_count)
            ON CONFLICT (id) DO UPDATE SET 
                title = EXCLUDED.title, 
                view_count = EXCLUDED.view_count,
                like_count = EXCLUDED.like_count,
                updated_at = NOW()
            RETURNING id
        """)
        await db.execute(query, {
            "v_id": req.id,
            "creator_id": creator_id, 
            "title": req.title, 
            "description": req.description,
            "type": req.type, 
            "privacy": req.privacy,
            "manifest_url": req.manifest_url,
            "view_count": req.view_count,
            "like_count": req.like_count
        })
        
        # Categories mapping (MicroLens names or IDs)
        for cat_name in req.categories:
            # Find or Create category
            cat_res = await db.execute(text("INSERT INTO categories (name) VALUES (:name) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id"), {"name": cat_name})
            cat_id = cat_res.scalar()
            if cat_id:
                await db.execute(text("INSERT INTO video_categories (video_id, category_id) VALUES (:v_id, :cat_id) ON CONFLICT DO NOTHING"), {"v_id": req.id, "cat_id": cat_id})
        
        # Tags mapping
        for tag_name in req.tags:
            tag_res = await db.execute(text("INSERT INTO tags (name) VALUES (:name) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id"), {"name": tag_name})
            tag_id = tag_res.scalar()
            if tag_id:
                await db.execute(text("INSERT INTO video_tags (video_id, tag_id) VALUES (:v_id, :tag_id) ON CONFLICT DO NOTHING"), {"v_id": req.id, "tag_id": tag_id})
        
        await db.commit()
        
        # 5. Trending Boost (Background)
        from core.ranking import update_trending_score
        import math
        # Initial velocity based on historical popularity (log-scaled)
        velocity = math.log1p(req.like_count * 2 + (req.view_count / 10))
        await update_trending_score(req.id, velocity)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"status": "success", "video_id": req.id}

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
    query = """
    SELECT v.*, 
           array_agg(t.name) FILTER (WHERE t.name IS NOT NULL) as tags,
           array_agg(c.name) FILTER (WHERE c.name IS NOT NULL) as categories
    FROM videos v
    LEFT JOIN video_tags vt ON v.id = vt.video_id
    LEFT JOIN tags t ON t.id = vt.tag_id
    LEFT JOIN video_categories vc ON v.id = vc.video_id
    LEFT JOIN categories c ON c.id = vc.category_id
    WHERE v.id = :id
    GROUP BY v.id
    """
    result = await db.execute(text(query), {"id": id})
    video = result.mappings().first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    if video["privacy"] == "PRIVATE" and str(video["creator_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Private video")
        
    video_dict = dict(video)
    
    # Standardize tags/categories to remove duplicates/empty
    video_dict['tags'] = list(dict.fromkeys([t for t in video_dict.get('tags', []) if t]))
    video_dict['categories'] = list(dict.fromkeys([c for c in video_dict.get('categories', []) if c]))
    video_dict.pop('tag_ids', None)
    video_dict.pop('category_ids', None)

    from core.ranking import get_video_tier
    video_dict["viral_tier"] = await get_video_tier(id)
    return video_dict

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
