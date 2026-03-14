from fastapi import APIRouter, Request, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db, get_redis
from core.ranking import score_video, get_candidates, get_interest_vector, MIN_EVENTS_FOR_MODEL, get_video_tier
import numpy as np
import json
import logging
from sqlalchemy import text

from core.auth import get_optional_user_id

logger = logging.getLogger(__name__)

router = APIRouter()

async def _cold_start_feed(
    db, redis, video_type: str, page: int,
    user_id: Optional[str], seen_ids: set
) -> dict:
    query = """
    SELECT v.*, array_agg(vt.tag_id) as tag_ids, array_agg(t.name) as tags, array_agg(vc.category_id) as category_ids, array_agg(c.name) as categories
    FROM videos v
    LEFT JOIN video_tags vt ON v.id = vt.video_id
    LEFT JOIN tags t ON t.id = vt.tag_id
    LEFT JOIN video_categories vc ON v.id = vc.video_id
    LEFT JOIN categories c ON c.id = vc.category_id
    WHERE v.status = 'READY' AND v.privacy = 'PUBLIC'
      AND v.type = :video_type
    GROUP BY v.id
    ORDER BY RANDOM()
    LIMIT 100
    """
    result = await db.execute(text(query), {"video_type": video_type})
    rows = [dict(r) for r in result.mappings().fetchall()]
    filtered = [r for r in rows if str(r['id']) not in seen_ids]
    
    for v in filtered:
        tags = v.get('tags', [])
        tags = [t for t in tags if t]
        v['tags'] = list(dict.fromkeys(tags))
        
        categories = v.get('categories', [])
        categories = [c for c in categories if c]
        v['categories'] = list(dict.fromkeys(categories))
        
        v.pop('tag_ids', None)
        v.pop('category_ids', None)

    return {
        "videos": filtered,
        "next_cursor": None,
        "has_more": False
    }

@router.get("/api/v1/feed")
async def get_feed(
    request: Request, 
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    video_type: str = Query("QUICK"),
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_db)
):
    app = request.app
    redis = await get_redis()
    
    # 1. Fetch user metadata and session data
    interest_vector = {}
    event_count = 0
    account_age_days = 0 
    region = "global"
    seen_ids = set()
    
    if user_id:
        try:
            # Check cache first (New Key Convention)
            cache_key = f"feed_cache:{user_id}:{page}"
            cached_feed = await redis.get(cache_key)
            if cached_feed:
                cached_data = json.loads(cached_feed)
                if isinstance(cached_data, list):
                    return {
                        "videos": cached_data,
                        "next_cursor": None,
                        "has_more": False
                    }
                return cached_data
                
            interest_vector = await get_interest_vector(user_id)
            user_result = await db.execute(text("""
                SELECT u.created_at, COALESCE(us.location, 'global') AS region
                FROM users u
                LEFT JOIN user_settings us ON us.user_id = u.id
                WHERE u.id = :user_id
            """), {"user_id": user_id})
            user_row = user_result.mappings().first()
            if user_row:
                region = user_row['region'] or "global"
                import datetime
                created_at = user_row['created_at']
                if created_at.tzinfo:
                    created_at = created_at.replace(tzinfo=None)
                account_age_days = (datetime.datetime.utcnow() - created_at).days
                
            seen_raw = await redis.get(f"session:{user_id}")
            seen_ids = set(json.loads(seen_raw).get("seen", [])) if seen_raw else set()
            
            iv_result = await db.execute(text("SELECT event_count FROM user_interest_vectors WHERE user_id = :user_id"), {"user_id": user_id})
            iv_row = iv_result.mappings().first()
            if iv_row:
                event_count = iv_row['event_count']
        except Exception as e:
            logger.error(f"Feed error getting user metadata: {e}")
            
    # Cold start if no basic data
    if not user_id and not interest_vector:
        return await _cold_start_feed(db, redis, video_type, page, user_id, seen_ids)

    model = getattr(app.state, 'two_tower_model', None)
    faiss_idx = getattr(app.state, 'faiss_index', None)
    
    # 2. Encode user and search FAISS if applicable
    user_embedding = None
    candidates = []
    
    if (
        model is not None
        and user_id is not None
        and event_count >= MIN_EVENTS_FOR_MODEL
        and faiss_idx is not None 
        and faiss_idx.is_ready()
    ):
        import asyncio
        try:
            user_embedding = await asyncio.to_thread(
                model.encode_user, user_id, interest_vector, event_count, account_age_days
            )
            candidate_vids = await faiss_idx.search(user_embedding, 100)
            if candidate_vids:
                # remove seen
                candidate_vids = [v for v in candidate_vids if v not in seen_ids]
                # fetch details from db
                if candidate_vids:
                    query = """
                    SELECT v.*, array_agg(vt.tag_id) as tag_ids, array_agg(t.name) as tags, array_agg(vc.category_id) as category_ids, array_agg(c.name) as categories
                    FROM videos v
                    LEFT JOIN video_tags vt ON v.id = vt.video_id
                    LEFT JOIN tags t ON t.id = vt.tag_id
                    LEFT JOIN video_categories vc ON v.id = vc.video_id
                    LEFT JOIN categories c ON c.id = vc.category_id
                    WHERE v.id = ANY(:candidate_vids) AND v.status = 'READY' AND v.privacy = 'PUBLIC'
                    GROUP BY v.id
                    """
                    cand_res = await db.execute(text(query), {"candidate_vids": candidate_vids})
                    candidates = [dict(r) for r in cand_res.mappings().fetchall()]
        except Exception as e:
            logger.error(f"ML candidate generation failed: {e}")
            user_embedding = None
            candidates = []

    # 3. Fallback to SQL candidates if ML missing/failed/skipped
    if not candidates:
        candidates = await get_candidates(user_id, db, seen_ids, region, interest_vector, limit=100)
    
    # 4. Score logic (Refactored for Pool Normalization)
    scored_videos = []
    if candidates:
        # Fetch video embeddings for the whole pool
        video_embeddings_map = {}
        cand_ids = [str(r['id']) for r in candidates]
        query_vecs = "SELECT video_id, vector FROM video_tag_vectors WHERE video_id = ANY(:cand_ids)"
        try:
            vec_res = await db.execute(text(query_vecs), {"cand_ids": cand_ids})
            vec_rows = vec_res.mappings().fetchall()
            for vr in vec_rows:
                vec_str = vr['vector']
                if vec_str:
                    if isinstance(vec_str, str):
                        vec = json.loads(vec_str)
                    else: vec = vec_str
                    video_embeddings_map[str(vr['video_id'])] = np.array(vec, dtype=np.float32)
        except Exception as e:
            logger.error(f"Error fetching vectors for scoring: {e}")

        # Call refactored score_video with entire pool
        scored_videos = await score_video(
            candidates,
            user_embedding,
            video_embeddings_map,
            interest_vector
        )
                
    if not scored_videos and not candidates:
        return await _cold_start_feed(db, redis, video_type, page, user_id, seen_ids)
        
    scored_videos.sort(key=lambda x: x[0], reverse=True)
    final_feed = [v[1] for v in scored_videos[:limit]]
    has_more = len(scored_videos) > limit
    
    import base64
    next_cursor = None
    if has_more and final_feed:
        last_vid_id = str(final_feed[-1]['id'])
        next_cursor = base64.b64encode(last_vid_id.encode('utf-8')).decode('utf-8')
        
    for v in final_feed:
        # Viral Tier Enrichment
        v['viral_tier'] = await get_video_tier(str(v['id']))
        
        tags = v.get('tags', [])
        tags = [t for t in tags if t]
        v['tags'] = list(dict.fromkeys(tags))
        
        categories = v.get('categories', [])
        categories = [c for c in categories if c]
        v['categories'] = list(dict.fromkeys(categories))
        
        v.pop('tag_ids', None)
        v.pop('category_ids', None)
    
    response_dict = {
        "videos": final_feed,
        "has_more": has_more,
        "next_cursor": next_cursor
    }
    
    # Session update, Caching & Rollout Tracking
    try:
        if final_feed:
            # Track rollout serves for potential advancement
            from core.ranking import record_rollout_serves
            await record_rollout_serves(db, redis, [str(v['id']) for v in final_feed])

        if user_id and final_feed:
            # deduplication update - keep only last 500
            new_seen = list(seen_ids) + [str(v['id']) for v in final_feed]
            if new_seen:
                await redis.set(
                    f"session:{user_id}",
                    json.dumps({"seen": new_seen[-500:]}),
                    ex=3600
                )
                
        # cache write
        def default_serializer(obj):
            import datetime
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()
            import uuid
            if isinstance(obj, uuid.UUID):
                return str(obj)
            raise TypeError("Type not serializable")
            
        if user_id:
            # Tiered TTL Logic
            ttl = 300
            for v in final_feed:
                tier = v.get('viral_tier')
                if tier in ["VIRAL", "MEGA_VIRAL"]:
                    ttl = 20
                    break
                elif tier == "HOT" or tier == "WATCH":
                    ttl = 60

            await redis.set(
                f"feed_cache:{user_id}:{page}", 
                json.dumps(response_dict, default=default_serializer),
                ex=ttl
            )
    except Exception as e:
        logger.error(f"Error updating feed session/cache: {e}")
    
    return response_dict
