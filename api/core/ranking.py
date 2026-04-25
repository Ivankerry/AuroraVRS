import numpy as np
import logging
import json
import os
from sqlalchemy import text

logger = logging.getLogger(__name__)

MIN_EVENTS_FOR_MODEL = int(os.getenv("MIN_EVENTS_FOR_MODEL", "5000"))
PROBABILITY_FLOOR = 0.02
FLOAT_TOL = 1e-9


def _stable_softmax(values: list[float]) -> list[float]:
    if not values:
        return []
    max_v = max(values)
    exps = [np.exp(v - max_v) for v in values]
    denom = float(sum(exps))
    if denom <= FLOAT_TOL:
        return [1.0 / len(values)] * len(values)
    return [float(x / denom) for x in exps]


def _enforce_floor_and_sum(
    weights: dict[str, float],
    probability_floor: float = PROBABILITY_FLOOR
) -> dict[str, float]:
    if not weights:
        return {}

    keys = list(weights.keys())
    n = len(keys)

    if probability_floor <= 0:
        probability_floor = 0.0

    # If floor is mathematically impossible for the number of tags,
    # return a valid fallback distribution.
    if n * probability_floor >= 1.0:
        uniform = 1.0 / n
        return {k: uniform for k in keys}

    probs = {k: max(float(v), 0.0) for k, v in weights.items()}
    total = float(sum(probs.values()))
    if total <= FLOAT_TOL:
        uniform = 1.0 / n
        probs = {k: uniform for k in keys}
    else:
        probs = {k: (v / total) for k, v in probs.items()}

    fixed: set[str] = set()
    while True:
        violating = [k for k, v in probs.items() if (k not in fixed and v < probability_floor)]
        if not violating:
            break

        fixed.update(violating)
        fixed_mass = probability_floor * len(fixed)
        if fixed_mass >= 1.0:
            uniform = 1.0 / n
            return {k: uniform for k in keys}

        unfixed = [k for k in keys if k not in fixed]
        out: dict[str, float] = {k: probability_floor for k in fixed}
        remaining_mass = 1.0 - fixed_mass

        unfixed_sum = float(sum(probs[k] for k in unfixed))
        if not unfixed:
            probs = out
            break

        if unfixed_sum <= FLOAT_TOL:
            share = remaining_mass / len(unfixed)
            for k in unfixed:
                out[k] = share
        else:
            for k in unfixed:
                out[k] = (probs[k] / unfixed_sum) * remaining_mass
        probs = out

    # Final exactness correction for floating-point drift.
    drift = 1.0 - float(sum(probs.values()))
    if abs(drift) > 1e-12 and probs:
        anchor = max(probs, key=probs.get)
        probs[anchor] += drift

    return probs


def normalize_to_probability_distribution(
    weights: dict[str, float],
    probability_floor: float = PROBABILITY_FLOOR
) -> dict[str, float]:
    if not weights:
        return {}

    sanitized: dict[str, float] = {}
    for k, v in weights.items():
        try:
            fv = float(v)
            if np.isfinite(fv):
                sanitized[str(k)] = fv
        except Exception:
            continue

    if not sanitized:
        return {}

    vals = list(sanitized.values())
    total = float(sum(vals))
    already_probs = all(v >= 0.0 for v in vals) and abs(total - 1.0) <= 1e-6

    if already_probs:
        normalized = {k: (v / total if total > FLOAT_TOL else 0.0) for k, v in sanitized.items()}
    else:
        # Legacy [-1,1] or arbitrary scale fallback to softmax.
        probs = _stable_softmax(vals)
        normalized = {k: p for k, p in zip(sanitized.keys(), probs)}

    return _enforce_floor_and_sum(normalized, probability_floor=probability_floor)


def _take_mass_equally(
    probs: dict[str, float],
    keys: list[str],
    amount: float,
    probability_floor: float = PROBABILITY_FLOOR
) -> float:
    if amount <= FLOAT_TOL or not keys:
        return 0.0

    remaining = float(amount)
    removed = 0.0
    active = [k for k in keys if probs.get(k, 0.0) > probability_floor + FLOAT_TOL]

    while remaining > FLOAT_TOL and active:
        share = remaining / len(active)
        step_removed = 0.0
        next_active: list[str] = []

        for k in active:
            room = max(probs.get(k, 0.0) - probability_floor, 0.0)
            take = min(share, room)
            if take > 0.0:
                probs[k] = probs.get(k, 0.0) - take
                step_removed += take

            if probs.get(k, 0.0) > probability_floor + FLOAT_TOL:
                next_active.append(k)

        if step_removed <= FLOAT_TOL:
            break

        removed += step_removed
        remaining -= step_removed
        active = next_active

    return removed


def _add_mass_equally(probs: dict[str, float], keys: list[str], amount: float) -> None:
    if amount <= FLOAT_TOL or not keys:
        return
    share = amount / len(keys)
    for k in keys:
        probs[k] = probs.get(k, 0.0) + share


async def update_interest_vector_hmm(
    user_id: str,
    event_tags: list[str],
    event_signal: float,
    event_count: int,
    current_weights: dict[str, float],
    *,
    is_watch_event: bool = False
) -> dict[str, float]:
    del user_id  # Keep signature explicit while function remains pure.

    probs = normalize_to_probability_distribution(current_weights)
    unique_tags = list(dict.fromkeys(str(t) for t in event_tags if t is not None))

    if not unique_tags:
        return probs

    if not probs:
        seed = {t: 1.0 / len(unique_tags) for t in unique_tags}
        return _enforce_floor_and_sum(seed)

    # Ensure new event tags exist in the distribution before redistribution math.
    new_tags = [t for t in unique_tags if t not in probs]
    if new_tags:
        existing = list(probs.keys())
        for t in new_tags:
            probs[t] = 0.0

        seed_needed = PROBABILITY_FLOOR * len(new_tags)
        removed = _take_mass_equally(probs, existing, seed_needed, probability_floor=PROBABILITY_FLOOR)
        _add_mass_equally(probs, new_tags, removed)
        probs = _enforce_floor_and_sum(probs)

    alpha = 0.8 if int(event_count) < 50 else 0.2
    if is_watch_event and float(event_signal) >= 0.6:
        alpha = 0.5

    signal = float(event_signal)
    delta = alpha * abs(signal)
    if delta <= FLOAT_TOL:
        return _enforce_floor_and_sum(probs)

    targets = [t for t in unique_tags if t in probs]
    if not targets:
        return _enforce_floor_and_sum(probs)

    target_set = set(targets)
    others = [k for k in probs.keys() if k not in target_set]

    if signal > 0.0:
        if not others:
            return _enforce_floor_and_sum(probs)
        shifted = _take_mass_equally(probs, others, delta, probability_floor=PROBABILITY_FLOOR)
        _add_mass_equally(probs, targets, shifted)
    elif signal < 0.0:
        shifted = _take_mass_equally(probs, targets, delta, probability_floor=PROBABILITY_FLOOR)
        if others:
            _add_mass_equally(probs, others, shifted)
        else:
            # Single-tag safety: no place to move probability, so keep distribution stable.
            _add_mass_equally(probs, targets, shifted)

    return _enforce_floor_and_sum(probs)

async def get_interest_vector(user_id: str) -> dict:
    try:
        from core.db import get_redis
        redis = await get_redis()
        val = await redis.get(f"iv:{user_id}")
        if val:
            return json.loads(val)
            
        # Hydration: Fallback to Postgres if Redis cache expired (24h TTL)
        from core.db import AsyncSessionLocal
        from sqlalchemy import text as sa_text
        async with AsyncSessionLocal() as db:
            result = await db.execute(sa_text(
                "SELECT tag_weights FROM user_interest_vectors WHERE user_id = :user_id"
            ), {"user_id": user_id})
            row = result.mappings().first()
            if row and row['tag_weights']:
                weights = json.loads(row['tag_weights']) if isinstance(row['tag_weights'], str) else row['tag_weights']
                # Rehydrate Redis for 24 hours
                await redis.setex(f"iv:{user_id}", 86400, json.dumps(weights))
                return weights

    except Exception as e:
        logger.error(f"Error getting interest vector: {e}")
    return {}

async def update_interest_vector(
    user_id: str,
    tag_ids: list[str],
    event_type: str,
    watch_ratio: float | None,
    event_count: int
) -> dict[str, float]:
    try:
        from core.db import get_redis
        redis = await get_redis()
        
        iv = await get_interest_vector(user_id)
        
        signals = {
            'VIEW':    float(watch_ratio) if watch_ratio is not None else 0.0,
            'WATCH':   float(watch_ratio) if watch_ratio is not None else 0.0,
            'LIKE':    0.6,
            'SAVE':    1.2,
            'SHARE':   1.0,
            'SKIP':   -0.5,
            'DISLIKE': -1.0,
            'COMMENT': 0.4,
        }
        normalized_event = str(event_type or "").upper()
        signal = signals.get(normalized_event, 0.0)

        iv = await update_interest_vector_hmm(
            user_id=user_id,
            event_tags=[str(tag_id) for tag_id in tag_ids],
            event_signal=signal,
            event_count=int(event_count),
            current_weights=iv,
            is_watch_event=normalized_event in {"VIEW", "WATCH"}
        )
            
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

async def clear_user_feed_cache(user_id: str):
    try:
        from core.db import get_redis
        redis = await get_redis()
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=f"feed_cache:{user_id}:*", count=100)
            if keys:
                await redis.delete(*keys)
            if cursor == 0:
                break
    except Exception as e:
        logger.error(f"Error clearing feed cache for {user_id}: {e}")

async def update_trending_score(video_id, engagement_velocity, region="global"):
    try:
        from core.db import get_redis
        redis = await get_redis()
        key = f"trending:{region}"
        
        # 1. Update existing trending pool
        vid_str = str(video_id)
        velocity = float(engagement_velocity)
        await redis.zadd(key, {vid_str: velocity})
        await redis.zremrangebyrank(key, 0, -1001)
        await redis.expire(key, 86400)

        # 2. Z-Score Viral Detection
        all_items = await redis.zrange(key, 0, -1, withscores=True)
        if len(all_items) < 10:
            return  # Not enough data for statistical significance

        scores = [float(s) for _, s in all_items]
        mean = np.mean(scores)
        std = np.std(scores) or 0.0001 # Prevent div by zero

        z = (velocity - mean) / std
        tier = None
        
        if z > 15:   tier = "MEGA_VIRAL"
        elif z > 10: tier = "VIRAL"
        elif z > 5:  tier = "HOT"
        elif z > 2:  tier = "WATCH"

        if tier:
            # Store tier for rapid multiplier lookup
            tier_key = f"viral_tier:{vid_str}"
            await redis.setex(tier_key, 300, tier)
            
            # Proactive Invalidation for VIRAL and MEGA_VIRAL
            if tier in ["VIRAL", "MEGA_VIRAL"]:
                notify_key = f"viral_tier_notified:{vid_str}"
                already_notified = await redis.get(notify_key)
                
                if not already_notified:
                    logger.info(f"🚀 PROACTIVE INVALIDATION: {vid_str} reached {tier} (z={z:.2f}).")
                    await redis.setex(notify_key, 600, "1")
                    
                    # SCAN and delete feed_cache:*
                    cursor = 0
                    while True:
                        cursor, keys = await redis.scan(cursor, match="feed_cache:*", count=100)
                        if keys:
                            await redis.delete(*keys)
                        if cursor == 0:
                            break
    except Exception as e:
        logger.error(f"Error updating trending score: {e}")

async def get_viral_multiplier(video_id: str) -> float:
    try:
        from core.db import get_redis
        redis = await get_redis()
        tier = await redis.get(f"viral_tier:{video_id}")
        if not tier: return 1.0
        
        multipliers = {
            b"WATCH": 1.5,
            b"HOT": 2.0,
            b"VIRAL": 3.0,
            b"MEGA_VIRAL": 5.0,
            # Handle cases where redis might return strings based on client config
            "WATCH": 1.5,
            "HOT": 2.0,
            "VIRAL": 3.0,
            "MEGA_VIRAL": 5.0
        }
        return multipliers.get(tier, 1.0)
    except Exception:
        return 1.0

async def get_video_tier(video_id: str) -> str | None:
    try:
        from core.db import get_redis
        redis = await get_redis()
        tier = await redis.get(f"viral_tier:{video_id}")
        if not tier: return None
        return tier.decode('utf-8') if isinstance(tier, bytes) else tier
    except Exception:
        return None

async def get_rollout_stage(video_id: str, redis) -> int:
    try:
        stage = await redis.get(f"rollout_stage:{video_id}")
        return int(stage) if stage else 1
    except Exception: return 1

async def record_rollout_serves(db, redis, video_ids: list[str]):
    try:
        for vid in video_ids:
            count = await redis.incr(f"rollout_count:{vid}")
            # Evaluate advancement every 100 serves
            if count % 100 == 0:
                await evaluate_rollout_advancement(db, redis, vid)
    except Exception as e:
        logger.error(f"Error recording rollout serves: {e}")

async def evaluate_rollout_advancement(db, redis, video_id: str):
    try:
        # 1. Fetch current stats
        query = text("SELECT view_count, like_count, avg_watch_ratio FROM videos WHERE id = :id")
        res = await db.execute(query, {"id": video_id})
        vid_data = res.mappings().first()
        if not vid_data: return

        views = float(vid_data['view_count'] or 1)
        likes = float(vid_data['like_count'] or 0)
        watch_ratio = float(vid_data['avg_watch_ratio'] or 0.0)
        like_rate = likes / max(views, 1)

        # 2. Get current stage
        current_stage = await get_rollout_stage(video_id, redis)
        if current_stage >= 4: return

        # 3. Define thresholds
        thresholds = {
            1: {"watch": 0.4, "like": 0.0, "max_aud": 500},
            2: {"watch": 0.5, "like": 0.05, "max_aud": 5000},
            3: {"watch": 0.6, "like": 0.08, "max_aud": 50000}
        }
        
        t = thresholds.get(current_stage)
        if not t: return

        # 4. Success check -> Advance
        # 4. Phase 1: Follower-First Gate (TikTok 2026)
        # If video is in Stage 1 and has very few views, it must perform well 
        # with followers before Phase 2 (Interest Cluster) testing.
        if watch_ratio > t["watch"] and like_rate >= t["like"]:
            await redis.set(f"rollout_stage:{video_id}", current_stage + 1)
            logger.info(f"✅ Video {video_id} passed Gate {current_stage}. ADVANCED to Stage {current_stage + 1}")
            return

        # 5. Failure check -> Removal
        count = int(await redis.get(f"rollout_count:{video_id}") or 0)
        if count >= t["max_aud"]:
            await redis.sadd("rollout_failed", video_id)
            await redis.expire("rollout_failed", 86400)
            logger.warning(f"❌ Video {video_id} FAILED rollout at Stage {current_stage}. Removed from Discovery.")
            
    except Exception as e:
        logger.error(f"Error in evaluate_rollout_advancement: {e}")

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
    # ... (existing get_candidates implementation remains same, just ensuring context) ...
    try:
        candidates = {}
        
        # 1. Trending (Boost popular videos)
        trending_ids = await get_trending_video_ids(region, limit=100)
        if trending_ids:
            query1 = "SELECT v.*, array_agg(vt.tag_id) as tag_ids, array_agg(t.name) as tags, array_agg(vc.category_id) as category_ids, array_agg(c.name) as categories FROM videos v LEFT JOIN video_tags vt ON v.id = vt.video_id LEFT JOIN tags t ON t.id = vt.tag_id LEFT JOIN video_categories vc ON v.id = vc.video_id LEFT JOIN categories c ON c.id = vc.category_id WHERE v.id = ANY(:ids) AND v.status = 'READY' AND v.privacy = 'PUBLIC' GROUP BY v.id"
            result1 = await db.execute(text(query1), {"ids": trending_ids})
            for r in result1.mappings().fetchall(): candidates[str(r['id'])] = dict(r)
            
        # 2. Followed creators
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
            
        # 3. Tag similarity
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
                
        # 4. Regional
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
        
        # 5. Discovery (Upgraded with Staged Rollout)
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
        LIMIT 200
        """
        result5 = await db.execute(text(query5))
        discovery_rows = result5.mappings().fetchall()
        
        from core.db import get_redis
        redis = await get_redis()
        
        failed_rollout = await redis.smembers("rollout_failed")
        failed_set = {f.decode() if isinstance(f, bytes) else f for f in failed_rollout}
        
        for r in discovery_rows:
            vid_str = str(r['id'])
            if vid_str in failed_set: continue
            
            views = r['view_count'] or 0
            
            # Grandfathering: Already popular videos skip to Stage 4
            if views >= 100:
                await redis.set(f"rollout_stage:{vid_str}", 4)
                candidates[vid_str] = dict(r)
                continue

            stage = await get_rollout_stage(vid_str, redis)
            if stage >= 4:
                candidates[vid_str] = dict(r)
                continue
                
            # Phase 1 Gate (Stage 1): Only show to followers or high-intent clusters
            if stage == 1:
                # If we know the user is a follower (already in candidates via query2)
                # or if we are in discovery, we add it but it will be ranked lower
                # unless interest (similarity) is extremely high.
                # However, to be strict with Phase 1:
                is_follower = any(vid_str == str(f.get('id')) for f in candidates.values() if f.get('creator_id'))
                if not is_follower:
                    # Allow 10% chance for random interest testing if not a follower
                    import random
                    if random.random() > 0.1: continue

            count = int(await redis.get(f"rollout_count:{vid_str}") or 0)
            thresholds = {1: 500, 2: 5000, 3: 50000}
            max_aud = thresholds.get(stage, 0)
            
            if count < max_aud:
                candidates[vid_str] = dict(r)
        
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
    candidates: list[dict], # Now receives the whole pool as requested
    user_embedding: np.ndarray | None,
    video_embeddings_map: dict[str, np.ndarray],
    interest_vector: dict,
) -> list[tuple[float, dict]]:
    if not candidates:
        return []

    # 1. Compute Raw Metrics for the Pool
    pool_metrics = []
    for v in candidates:
        views = float(v.get('view_count', 1) or 1)
        likes = float(v.get('like_count', 0) or 0)
        comments = float(v.get('comment_count', 0) or 0)
        shares = float(v.get('share_count', 0) or 0)
        saves = float(v.get('save_count', 0) or 0)
        
        m = {
            "watch_ratio": float(v.get('avg_watch_ratio') or 0.0),
            "like_rate": likes / max(views, 1),
            "comment_rate": comments / max(views, 1),
            "share_rate": shares / max(views, 1),
            "save_rate": saves / max(views, 1),
            "video": v
        }
        pool_metrics.append(m)

    # 2. Compute Pool Min/Max for Normalization
    def get_min_max(key):
        vals = [m[key] for m in pool_metrics]
        return min(vals), max(vals)

    watch_min, watch_max = get_min_max("watch_ratio")
    like_min, like_max   = get_min_max("like_rate")
    comm_min, comm_max   = get_min_max("comment_rate")
    share_min, share_max = get_min_max("share_rate")
    save_min, save_max   = get_min_max("save_rate")

    def normalize(val, v_min, v_max):
        if v_max == v_min: return 0.5
        return (val - v_min) / (v_max - v_min)

    # 3. Final Scoring Loop
    scored_videos = []
    for m in pool_metrics:
        video = m["video"]
        vid_str = str(video.get('id'))
        
        # A. Normalized Metrics
        n_watch = normalize(m["watch_ratio"], watch_min, watch_max)
        n_like  = normalize(m["like_rate"], like_min, like_max)
        n_comm  = normalize(m["comment_rate"], comm_min, comm_max)
        n_share = normalize(m["share_rate"], share_min, share_max)
        n_save  = normalize(m["save_rate"], save_min, save_max)

        # B. Similarity Component (Unnormalized)
        similarity = 0.0
        v_emb = video_embeddings_map.get(vid_str)
        if user_embedding is not None and v_emb is not None:
            # Use dot product (already 0.0-1.0 if normalized correctly in trainer)
            similarity = float(np.dot(user_embedding, v_emb[:128]))
        else:
            # Fallback: Tag Similarity (unnormalized overlap score)
            tag_ids = [str(t) for t in video.get('tag_ids', []) if t] + [str(c) for c in video.get('category_ids', []) if c]
            for t_id in tag_ids:
                similarity += float(interest_vector.get(str(t_id), 0.0))
            # Normalize similarity to prevent filter bubbles (Echo Chamber)
            similarity = max(0.0, min(1.0, similarity))
        
        # C. TikTok 2026 Core Ranking Formula
        # Relative Importance: Completion(10), Save(8), Share(6), Comment(4), Like(2)
        eng_score = n_watch*0.35 + n_save*0.25 + n_share*0.2 + n_comm*0.13 + n_like*0.07
        
        # Interest-First Balance (50% Interest / 50% Engagement)
        base_score = similarity*0.5 + eng_score*0.5

        # D. TikTok 2026 Skip Penalty (-50 points logic relative to +10)
        # If watch ratio is exceptionally low (<10%), penalize heavily
        if m["watch_ratio"] < 0.1:
            base_score -= 1.0 # Massive penalty (multi-factor of top positive)

        # D. Viral Boost (applied after normalization)
        viral_multiplier = await get_viral_multiplier(vid_str)
        final_score = base_score * viral_multiplier
        
        scored_videos.append((final_score, video))

    return scored_videos
