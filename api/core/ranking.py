import numpy as np
import logging
import json
import os
from sqlalchemy import text

logger = logging.getLogger(__name__)

MIN_EVENTS_FOR_MODEL = int(os.getenv("MIN_EVENTS_FOR_MODEL", "5000"))

async def get_interest_vector(user_id: str) -> dict:
    try:
        from core.db import get_redis
        redis = await get_redis()
        val = await redis.get(f"iv:{user_id}")
        if val:
            return json.loads(val)
    except Exception as e:
        logger.error(f"Error getting interest vector: {e}")
    return {}

async def update_interest_vector(user_id, tag_ids, event_type, watch_ratio, event_count) -> dict:
    try:
        from core.db import get_redis
        redis = await get_redis()
        
        iv = await get_interest_vector(user_id)
        
        signals = {
            'VIEW':    float(watch_ratio) if watch_ratio is not None else 0.0,
            'LIKE':    0.8,
            'SHARE':   1.2,
            'SKIP':   -0.3,
            'DISLIKE': -0.8,
            'COMMENT': 0.3,
        }
        signal = signals.get(event_type, 0.0)
        
        if event_count < 50:
            signal *= 3.0
            
        for tag_id in tag_ids:
            tag_id_str = str(tag_id)
            old_weight = float(iv.get(tag_id_str, 0.0))
            new_weight = 0.15 * signal + 0.85 * old_weight
            new_weight = max(-1.0, min(1.0, new_weight))
            iv[tag_id_str] = new_weight
            
        await redis.setex(f"iv:{user_id}", 86400, json.dumps(iv))
        
        # Also persist to Postgres so the worker trainer can read real tag weights
        try:
            from core.db import AsyncSessionLocal
            from sqlalchemy import text as sa_text
            async with AsyncSessionLocal() as db:
                await db.execute(sa_text("""
                    UPDATE user_interest_vectors
                    SET tag_weights = :tw, updated_at = NOW()
                    WHERE user_id = :user_id
                """), {"tw": json.dumps(iv), "user_id": user_id})
                await db.commit()
        except Exception as db_err:
            logger.warning(f"Could not persist tag_weights to Postgres: {db_err}")
        
        return iv
    except Exception as e:
        logger.error(f"Error updating interest vector: {e}")
        return {}

async def update_trending_score(video_id, engagement_velocity, region="global"):
    try:
        from core.db import get_redis
        redis = await get_redis()
        key = f"trending:{region}"
        await redis.zadd(key, {str(video_id): float(engagement_velocity)})
        await redis.zremrangebyrank(key, 0, -1001)
        await redis.expire(key, 86400)
    except Exception as e:
        logger.error(f"Error updating trending score: {e}")

async def get_trending_video_ids(region="global", limit=50) -> list[str]:
    try:
        from core.db import get_redis
        redis = await get_redis()
        key = f"trending:{region}"
        vals = await redis.zrevrange(key, 0, limit - 1)
        return [val.decode('utf-8') if isinstance(val, bytes) else val for val in vals]
    except Exception as e:
        logger.error(f"Error getting trending video ids: {e}")
        return []

async def get_candidates(user_id, db, seen_ids, region, interest_vector, limit=100) -> list[dict]:
    try:
        candidates = {}
        
        # 1. Trending (Boost popular videos)
        trending_ids = await get_trending_video_ids(region, limit=100)
        if trending_ids:
            query1 = "SELECT v.*, array_agg(vt.tag_id) as tag_ids, array_agg(t.name) as tags, array_agg(vc.category_id) as category_ids, array_agg(c.name) as categories FROM videos v LEFT JOIN video_tags vt ON v.id = vt.video_id LEFT JOIN tags t ON t.id = vt.tag_id LEFT JOIN video_categories vc ON v.id = vc.video_id LEFT JOIN categories c ON c.id = vc.category_id WHERE v.id = ANY(:ids) AND v.status = 'READY' AND v.privacy = 'PUBLIC' GROUP BY v.id"
            result1 = await db.execute(text(query1), {"ids": trending_ids})
            for r in result1.mappings().fetchall(): candidates[str(r['id'])] = dict(r)
            
        # 2. Followed creators (Most recent from follows)
        if user_id:
            query2 = """
            SELECT v.*, array_agg(vt.tag_id) as tag_ids, array_agg(t.name) as tags, array_agg(vc.category_id) as category_ids, array_agg(c.name) as categories 
            FROM videos v 
            JOIN follows f ON v.creator_id = f.following_id 
            LEFT JOIN video_tags vt ON v.id = vt.video_id
            LEFT JOIN tags t ON t.id = vt.tag_id
            LEFT JOIN video_categories vc ON v.id = vc.video_id
            LEFT JOIN categories c ON c.id = vc.category_id
            WHERE f.follower_id = :user_id AND v.status = 'READY' AND v.privacy = 'PUBLIC'
            GROUP BY v.id ORDER BY v.created_at DESC LIMIT 100
            """
            result2 = await db.execute(text(query2), {"user_id": user_id})
            for r in result2.mappings().fetchall(): candidates[str(r['id'])] = dict(r)
            
        # 3. Tag similarity (Direct interest matches)
        if interest_vector:
            top_tags = sorted(interest_vector.items(), key=lambda x: x[1], reverse=True)[:10]
            tag_ids = [t[0] for t in top_tags]
            if tag_ids:
                query3 = """
                SELECT v.*, array_agg(vt.tag_id) as tag_ids, array_agg(t.name) as tags, array_agg(vc.category_id) as category_ids, array_agg(c.name) as categories 
                FROM videos v 
                JOIN video_tags vt2 ON v.id = vt2.video_id 
                LEFT JOIN video_tags vt ON v.id = vt.video_id
                LEFT JOIN tags t ON t.id = vt.tag_id
                LEFT JOIN video_categories vc ON v.id = vc.video_id
                LEFT JOIN categories c ON c.id = vc.category_id
                WHERE vt2.tag_id = ANY(:tag_ids) AND v.status = 'READY' AND v.privacy = 'PUBLIC'
                GROUP BY v.id ORDER BY RANDOM() LIMIT 100
                """
                result3 = await db.execute(text(query3), {"tag_ids": tag_ids})
                for r in result3.mappings().fetchall(): candidates[str(r['id'])] = dict(r)
                
        # 4. Regional (Local community)
        query4 = """
        SELECT v.*, array_agg(vt.tag_id) as tag_ids, array_agg(t.name) as tags, array_agg(vc.category_id) as category_ids, array_agg(c.name) as categories 
        FROM videos v 
        JOIN users u ON u.id = v.creator_id 
        JOIN user_settings us ON us.user_id = u.id
        LEFT JOIN video_tags vt ON v.id = vt.video_id
        LEFT JOIN tags t ON t.id = vt.tag_id
        LEFT JOIN video_categories vc ON v.id = vc.video_id
        LEFT JOIN categories c ON c.id = vc.category_id
        WHERE us.location = :region AND v.status = 'READY' AND v.privacy = 'PUBLIC'
        GROUP BY v.id ORDER BY RANDOM() LIMIT 50
        """
        result4 = await db.execute(text(query4), {"region": region})
        for r in result4.mappings().fetchall(): candidates[str(r['id'])] = dict(r)
        
        # 5. Discovery / Cold start pool (Videos with low views or recently created)
        query5 = """
        SELECT v.*, array_agg(vt.tag_id) as tag_ids, array_agg(t.name) as tags, array_agg(vc.category_id) as category_ids, array_agg(c.name) as categories 
        FROM videos v 
        LEFT JOIN video_tags vt ON v.id = vt.video_id
        LEFT JOIN tags t ON t.id = vt.tag_id
        LEFT JOIN video_categories vc ON v.id = vc.video_id
        LEFT JOIN categories c ON c.id = vc.category_id
        WHERE (v.view_count < 100 OR v.created_at > NOW() - INTERVAL '72 hours')
        AND v.status = 'READY' AND v.privacy = 'PUBLIC'
        GROUP BY v.id 
        ORDER BY RANDOM() 
        LIMIT 100
        """
        result5 = await db.execute(text(query5))
        for r in result5.mappings().fetchall(): candidates[str(r['id'])] = dict(r)
        
        # Deduplication and remove seen_ids
        final_candidates = []
        seen_set = set(seen_ids)
        for vid, row in candidates.items():
            if vid not in seen_set:
                final_candidates.append(row)
                
        return final_candidates
    except Exception as e:
        logger.error(f"Error getting candidates: {e}")
        return []

async def score_video(
    video: dict,
    user_embedding: np.ndarray | None,
    video_embedding: np.ndarray | None,
    interest_vector: dict,
    video_tag_ids: list[str],
) -> float:
    if user_embedding is not None and video_embedding is not None:
        return float(np.dot(user_embedding, video_embedding))
        
    watch_ratio = float(video.get('avg_watch_ratio') or 0.0)
    views = float(video.get('view_count', 1) or 1)
    likes = float(video.get('like_count', 0) or 0)
    comments = float(video.get('comment_count', 0) or 0)
    
    like_rate = likes / max(views, 1)
    comment_rate = comments / max(views, 1)
    
    similarity = 0.0
    for tag_id in video_tag_ids:
        similarity += float(interest_vector.get(str(tag_id), 0.0))
        
    score = watch_ratio*0.5 + like_rate*0.2 + comment_rate*0.1 + similarity*0.2
    return score
