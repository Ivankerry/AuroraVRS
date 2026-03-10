from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.db import get_db
from core.auth import get_current_user_id
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class UserUpdate(BaseModel):
    names: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

@router.get("/api/v1/users/me")
async def get_me(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    query = text("SELECT id, names, email, bio, avatar_url, role FROM users WHERE id = :id")
    result = await db.execute(query, {"id": user_id})
    user = result.mappings().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)

@router.put("/api/v1/users/me")
async def update_me(req: UserUpdate, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    updates = []
    params = {"id": user_id}
    if req.names is not None:
        updates.append("names = :names")
        params["names"] = req.names
    if req.bio is not None:
        updates.append("bio = :bio")
        params["bio"] = req.bio
    if req.avatar_url is not None:
        updates.append("avatar_url = :avatar_url")
        params["avatar_url"] = req.avatar_url
        
    if updates:
        query = text(f"UPDATE users SET {', '.join(updates)}, updated_at = NOW() WHERE id = :id")
        await db.execute(query, params)
        await db.commit()
    return {"status": "success"}

@router.get("/api/v1/users/{id}")
async def get_user(id: str, db: AsyncSession = Depends(get_db)):
    query = text("SELECT id, names, bio, avatar_url FROM users WHERE id = :id")
    result = await db.execute(query, {"id": id})
    user = result.mappings().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)

@router.post("/api/v1/users/{id}/follow")
async def follow_user(id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    if id == user_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    try:
        query = text("INSERT INTO follows (follower_id, following_id) VALUES (:follower_id, :following_id) ON CONFLICT DO NOTHING")
        await db.execute(query, {"follower_id": user_id, "following_id": id})
        await db.commit()
    except Exception as e:
        await db.rollback()
    return {"status": "success"}

@router.delete("/api/v1/users/{id}/follow")
async def unfollow_user(id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    query = text("DELETE FROM follows WHERE follower_id = :follower_id AND following_id = :following_id")
    await db.execute(query, {"follower_id": user_id, "following_id": id})
    await db.commit()
    return {"status": "success"}

@router.get("/api/v1/users/{id}/followers")
async def get_followers(id: str, db: AsyncSession = Depends(get_db)):
    query = text("""
        SELECT u.id, u.names, u.avatar_url 
        FROM follows f 
        JOIN users u ON u.id = f.follower_id 
        WHERE f.following_id = :id
    """)
    result = await db.execute(query, {"id": id})
    return [dict(r) for r in result.mappings().fetchall()]

@router.get("/api/v1/users/{id}/following")
async def get_following(id: str, db: AsyncSession = Depends(get_db)):
    query = text("""
        SELECT u.id, u.names, u.avatar_url 
        FROM follows f 
        JOIN users u ON u.id = f.following_id 
        WHERE f.follower_id = :id
    """)
    result = await db.execute(query, {"id": id})
    return [dict(r) for r in result.mappings().fetchall()]
