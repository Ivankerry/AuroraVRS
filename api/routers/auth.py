from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from core.db import get_db
from core.auth import (
    hash_password, verify_password, create_access_token, 
    create_refresh_token, get_current_user_id
)

router = APIRouter()

class RegisterRequest(BaseModel):
    email: str
    password: str
    names: str

class LoginRequest(BaseModel):
    email: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/api/v1/auth/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    pwd_hash = hash_password(req.password)
    try:
        query = text("""
            INSERT INTO users (names, email, password_hash)
            VALUES (:names, :email, :password_hash)
            RETURNING id, role
        """)
        result = await db.execute(query, {
            "names": req.names,
            "email": req.email,
            "password_hash": pwd_hash
        })
        user = result.mappings().first()
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
        
    user_id = str(user["id"])
    role = user["role"]
    access_token = create_access_token(user_id, role)
    refresh_token = create_refresh_token()
    
    expires_at = datetime.utcnow() + timedelta(days=30)
    rt_query = text("""
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES (:user_id, :token_hash, :expires_at)
    """)
    await db.execute(rt_query, {
        "user_id": user_id,
        "token_hash": refresh_token,
        "expires_at": expires_at
    })
    await db.commit()
    
    return {"access_token": access_token, "refresh_token": refresh_token}

@router.post("/api/v1/auth/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    query = text("SELECT id, password_hash, role FROM users WHERE email = :email")
    result = await db.execute(query, {"email": req.email})
    user = result.mappings().first()
    
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    user_id = str(user["id"])
    role = user["role"]
    access_token = create_access_token(user_id, role)
    refresh_token = create_refresh_token()
    
    expires_at = datetime.utcnow() + timedelta(days=30)
    rt_query = text("""
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES (:user_id, :token_hash, :expires_at)
    """)
    await db.execute(rt_query, {
        "user_id": user_id,
        "token_hash": refresh_token,
        "expires_at": expires_at
    })
    
    update_login = text("UPDATE users SET last_login = NOW() WHERE id = :id")
    await db.execute(update_login, {"id": user_id})
    await db.commit()
    
    return {"access_token": access_token, "refresh_token": refresh_token}

@router.post("/api/v1/auth/refresh")
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    query = text("""
        SELECT r.user_id, u.role, r.expires_at 
        FROM refresh_tokens r
        JOIN users u ON u.id = r.user_id
        WHERE r.token_hash = :token_hash
    """)
    result = await db.execute(query, {"token_hash": req.refresh_token})
    rt = result.mappings().first()
    
    if not rt or rt["expires_at"] < datetime.utcnow().replace(tzinfo=rt["expires_at"].tzinfo if rt["expires_at"].tzinfo else None):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
        
    user_id = str(rt["user_id"])
    role = rt["role"]
    access_token = create_access_token(user_id, role)
    return {"access_token": access_token}

@router.post("/api/v1/auth/logout")
async def logout(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    query = text("DELETE FROM refresh_tokens WHERE token_hash = :token_hash")
    await db.execute(query, {"token_hash": req.refresh_token})
    await db.commit()
    return {"status": "success"}

@router.post("/api/v1/auth/change-password")
async def change_password(req: ChangePasswordRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    query = text("SELECT password_hash FROM users WHERE id = :id")
    result = await db.execute(query, {"id": user_id})
    user = result.mappings().first()
    
    if not user or not verify_password(req.old_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Invalid old password")
        
    new_hash = hash_password(req.new_password)
    update_query = text("UPDATE users SET password_hash = :hash WHERE id = :id")
    await db.execute(update_query, {"hash": new_hash, "id": user_id})
    await db.commit()
    return {"status": "success"}
