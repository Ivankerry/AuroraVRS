import asyncio
import asyncpg
import json

import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

async def backfill():
    print("🔌 Connecting to DB...")
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Check current count
    count = await conn.fetchval("SELECT COUNT(*) FROM user_interest_vectors")
    print(f"Current user_interest_vectors rows: {count}")
    
    print("🧹 Wiping user_interest_vectors...")
    await conn.execute("TRUNCATE user_interest_vectors CASCADE")
    
    print("⚡ Aggregating user event counts and tags...")
    
    query = """
    WITH user_events AS (
        SELECT user_id, video_id, event_type, watch_ratio
        FROM events
    ),
    event_counts AS (
        SELECT user_id, COUNT(*) as ev_cnt 
        FROM user_events 
        GROUP BY user_id
    ),
    video_all_tags AS (
        SELECT video_id, tag_id::TEXT as tag_id FROM video_tags
        UNION ALL
        SELECT video_id, category_id::TEXT as tag_id FROM video_categories
    ),
    user_tag_scores AS (
        SELECT 
            ue.user_id,
            vat.tag_id,
            SUM(
                CASE 
                    WHEN ue.event_type = 'LIKE' THEN 0.8
                    WHEN ue.event_type = 'SHARE' THEN 1.2
                    WHEN ue.event_type = 'SKIP' THEN -0.3
                    WHEN ue.event_type = 'DISLIKE' THEN -0.8
                    WHEN ue.event_type = 'COMMENT' THEN 0.3
                    ELSE COALESCE(ue.watch_ratio, 0.0)
                END
            ) as weight
        FROM user_events ue
        JOIN video_all_tags vat ON ue.video_id = vat.video_id
        GROUP BY ue.user_id, vat.tag_id
    )
    SELECT 
        ec.user_id, 
        ec.ev_cnt,
        json_object_agg(uts.tag_id, 
            LEAST(GREATEST(
                CASE WHEN ec.ev_cnt < 50 THEN uts.weight * 3.0 ELSE uts.weight END
            , -1.0), 1.0)
        ) as interest_vector
    FROM event_counts ec
    JOIN user_tag_scores uts ON ec.user_id = uts.user_id
    GROUP BY ec.user_id, ec.ev_cnt
    """
    
    print("Executing massive aggregation via Postgres Native Engine...")
    rows = await conn.fetch(query)
    print(f"✅ Aggregated {len(rows)} users' vector data.")
    
    print("Writing reconstructed interest vectors back to Postgres...")
    batch = []
    for r in rows:
        batch.append((r['user_id'], r['ev_cnt'], r['interest_vector']))
        
    await conn.executemany("""
        INSERT INTO user_interest_vectors (user_id, event_count, tag_weights, updated_at)
        VALUES ($1, $2, $3::jsonb, NOW())
    """, batch)
    
    print(f"✅ Successfully wrote {len(batch)} users to user_interest_vectors.")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(backfill())
