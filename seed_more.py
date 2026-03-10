import asyncio
import os
import random
from datetime import datetime, timedelta
import asyncpg

DATABASE_URL = "postgresql://user:pass@localhost:5432/db"

async def seed_more_events():
    print(f"Connecting to {DATABASE_URL}...")
    conn = await asyncpg.connect(DATABASE_URL)
    
    print("Fetching existing users and videos...")
    user_rows = await conn.fetch("SELECT id FROM users")
    user_ids = [str(r['id']) for r in user_rows]
    
    video_rows = await conn.fetch("SELECT id FROM videos")
    video_ids = [str(r['id']) for r in video_rows]
    
    if not user_ids or not video_ids:
        print("No users or videos found. Run seed.py first.")
        await conn.close()
        return

    print("Generating 15,000 MORE EVENTS to trigger the 10,000 model training milestone...")
    events = []
    event_types = ['VIEW', 'LIKE', 'DISLIKE', 'SHARE', 'COMMENT', 'SKIP', 'SEARCH', 'PROFILE_VISIT']
    
    # Shifting the interaction weights slightly so the model learns a "new trend"
    # and outperforms the old weights
    weights = [0.4, 0.25, 0.05, 0.1, 0.05, 0.05, 0.05, 0.05]
    
    now = datetime.utcnow()
    for _ in range(15000):
        uid = random.choice(user_ids)
        vid = random.choice(video_ids)
        etype = random.choices(event_types, weights=weights)[0]
        ratio = random.uniform(0.1, 1.0) if etype == 'VIEW' else None
        
        # Spread events over last 7 days targeting recent trends
        created = now - timedelta(days=random.uniform(0, 7))
        events.append((uid, vid, etype, ratio, created))
        
    await conn.executemany("""
        INSERT INTO events (user_id, video_id, event_type, watch_ratio, created_at)
        VALUES ($1, $2, $3, $4, $5)
    """, events)
    
    print("Updating video statistics...")
    await conn.execute("""
        UPDATE videos SET 
            view_count = (SELECT count(*) FROM events WHERE video_id = videos.id AND event_type = 'VIEW'),
            like_count = (SELECT count(*) FROM events WHERE video_id = videos.id AND event_type = 'LIKE')
    """)
    
    print("Updating user interaction counts...")
    for uid in user_ids:
        await conn.execute("""
            UPDATE user_interest_vectors 
            SET event_count = (SELECT count(*) FROM events WHERE user_id = $1)
            WHERE user_id = $1
        """, uid)
    
    print("\n✅ Injected 15,000 new interactions!")
    print("The backend worker will notice the database size crossed the 10,000 milestone and trigger training.")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(seed_more_events())
