import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from core.config import get_settings
from core.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import secrets

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hash.encode('utf-8'))

def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode = {"sub": user_id, "role": role, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def create_refresh_token() -> str:
    return secrets.token_urlsafe(32)

def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return user_id
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def get_optional_user_id(token: Optional[str] = Depends(oauth2_scheme_optional)) -> Optional[str]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None

async def require_admin(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)) -> str:
    query = text("SELECT role FROM users WHERE id = :id")
    result = await db.execute(query, {"id": user_id})
    row = result.mappings().first()
    if not row or row["role"] != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return user_id
