import asyncio
import os
import random
from datetime import datetime, timedelta
import asyncpg

DATABASE_URL = "postgresql://user:pass@localhost:5432/db"

async def seed_clustered_data():
    conn = await asyncpg.connect(DATABASE_URL)
    
    print("Fetching metadata to build user Personas...")
    users = await conn.fetch("SELECT id FROM users")
    user_ids = [str(u['id']) for u in users]
    
    video_rows = await conn.fetch("""
        SELECT v.id, vc.category_id 
        FROM videos v
        JOIN video_categories vc ON vc.video_id = v.id
    """)
    videos_by_cat = {}
    for r in video_rows:
        cid = str(r['category_id'])
        vid = str(r['id'])
        videos_by_cat.setdefault(cid, []).append(vid)
        
    all_categories = list(videos_by_cat.keys())
    print(f"Assigning {len(all_categories)} distinct category niches across {len(user_ids)} users...")
    
    # Give every user a "favorite" content niche
    user_personas = {uid: random.choice(all_categories) for uid in user_ids}
    
    print("Generating 30,000 heavily clustered events to hit the 50k milestone...")
    events = []
    now = datetime.utcnow()
    
    for _ in range(30000):
        uid = random.choice(user_ids)
        fav_cat = user_personas[uid]
        
        # 85% of the time, the user interacts with their Favorite Category
        if random.random() < 0.85:
            vid = random.choice(videos_by_cat[fav_cat])
            # They love it, so they produce Positive signals
            etype = random.choices(['LIKE', 'SHARE', 'VIEW'], weights=[0.3, 0.1, 0.6])[0]
            ratio = random.uniform(0.75, 1.0) if etype == 'VIEW' else None
        else:
            # 15% of the time, they stumble onto a category they don't like
            other_cats = [c for c in all_categories if c != fav_cat]
            other_cat = random.choice(other_cats)
            vid = random.choice(videos_by_cat[other_cat])
            # They hate it, producing Negative signals
            etype = random.choices(['DISLIKE', 'SKIP', 'VIEW'], weights=[0.3, 0.4, 0.3])[0]
            ratio = random.uniform(0.0, 0.25) if etype == 'VIEW' else None
            
        created = now - timedelta(days=random.uniform(0, 2))
        events.append((uid, vid, etype, ratio, created))
        
    await conn.executemany("""
        INSERT INTO events (user_id, video_id, event_type, watch_ratio, created_at)
        VALUES ($1, $2, $3, $4, $5)
    """, events)
    
    print("Updating SQL aggregates...")
    await conn.execute("""
        UPDATE videos SET 
            view_count = (SELECT count(*) FROM events WHERE video_id = videos.id AND event_type = 'VIEW'),
            like_count = (SELECT count(*) FROM events WHERE video_id = videos.id AND event_type = 'LIKE')
    """)
    
    for uid in user_ids:
        await conn.execute("""
            UPDATE user_interest_vectors 
            SET event_count = (SELECT count(*) FROM events WHERE user_id = $1)
            WHERE user_id = $1
        """, uid)
        
    print("\n✅ Intelligence Injected!")
    print("Total rows will now cross 50,000. Redis will trigger the next Two-Tower Training Cycle in ~60 seconds...")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(seed_clustered_data())
