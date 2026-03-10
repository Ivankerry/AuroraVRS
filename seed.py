import asyncio
import os
import random
from datetime import datetime, timedelta
import asyncpg
import bcrypt

DATABASE_URL = "postgresql://user:pass@localhost:5432/db"

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

async def seed_db():
    print(f"Connecting to {DATABASE_URL}...")
    conn = await asyncpg.connect(DATABASE_URL)
    
    print("Clearing old data...")
    await conn.execute("TRUNCATE TABLE users, videos, tags, categories CASCADE")
    
    print("Creating USERS...")
    users = []
    for i in range(1, 51):
        users.append((
            f"User {i}", f"user{i}@example.com", hash_pw("password123"), "USER"
        ))
    # Add an admin
    users.append(("Admin User", "admin@example.com", hash_pw("admin123"), "ADMIN"))
    
    await conn.executemany("""
        INSERT INTO users (names, email, password_hash, role) 
        VALUES ($1, $2, $3, $4)
    """, users)
    
    user_rows = await conn.fetch("SELECT id FROM users")
    user_ids = [str(r['id']) for r in user_rows]
    
    print("Creating TAGS & CATEGORIES...")
    tags = [f"Tag{i}" for i in range(1, 31)]
    await conn.executemany("INSERT INTO tags (name) VALUES ($1)", [(t,) for t in tags])
    tag_rows = await conn.fetch("SELECT id FROM tags")
    tag_ids = [str(r['id']) for r in tag_rows]
    
    categories = ["Gaming", "Education", "Comedy", "Music", "Vlogs"]
    await conn.executemany("INSERT INTO categories (name) VALUES ($1)", [(c,) for c in categories])
    cat_rows = await conn.fetch("SELECT id FROM categories")
    cat_ids = [str(r['id']) for r in cat_rows]
    
    print("Creating VIDEOS...")
    videos = []
    for i in range(1, 201):
        creator = random.choice(user_ids)
        videos.append((
            creator, f"Video Title {i}", "A cool video description.", "QUICK", "PUBLIC", "READY", 60.0
        ))
    
    await conn.executemany("""
        INSERT INTO videos (creator_id, title, description, type, privacy, status, duration_sec)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
    """, videos)
    
    video_rows = await conn.fetch("SELECT id FROM videos")
    video_ids = [str(r['id']) for r in video_rows]
    
    print("Assigning Tags & Categories to Videos...")
    vtags = []
    vcats = []
    for vid in video_ids:
        for t in random.sample(tag_ids, k=random.randint(1, 5)):
            vtags.append((vid, t))
        for c in random.sample(cat_ids, k=random.randint(1, 2)):
            vcats.append((vid, c))
            
    await conn.executemany("INSERT INTO video_tags (video_id, tag_id) VALUES ($1, $2)", vtags)
    await conn.executemany("INSERT INTO video_categories (video_id, category_id) VALUES ($1, $2)", vcats)
    
    print("Generating 6000 EVENTS to trigger model training...")
    events = []
    event_types = ['VIEW', 'LIKE', 'DISLIKE', 'SHARE', 'COMMENT', 'SKIP', 'SEARCH', 'PROFILE_VISIT']
    weights = [0.5, 0.15, 0.05, 0.05, 0.05, 0.1, 0.05, 0.05]
    
    now = datetime.utcnow()
    for _ in range(6000):
        uid = random.choice(user_ids)
        vid = random.choice(video_ids)
        etype = random.choices(event_types, weights=weights)[0]
        ratio = random.uniform(0.1, 1.0) if etype == 'VIEW' else None
        
        # Spread events over last 14 days
        created = now - timedelta(days=random.uniform(0, 14))
        events.append((uid, vid, etype, ratio, created))
        
    await conn.executemany("""
        INSERT INTO events (user_id, video_id, event_type, watch_ratio, created_at)
        VALUES ($1, $2, $3, $4, $5)
    """, events)
    
    print("Calculating User Interest Vectors & Video Stats (Simulation)...")
    
    # Update video basic counters
    await conn.execute("""
        UPDATE videos SET 
            view_count = (SELECT count(*) FROM events WHERE video_id = videos.id AND event_type = 'VIEW'),
            like_count = (SELECT count(*) FROM events WHERE video_id = videos.id AND event_type = 'LIKE')
    """)
    
    # Init user_interest_vectors so the training query doesn't discard them for having 0 events
    for uid in user_ids:
        # give everyone 150 events to easily bypass MIN_EVENTS_FOR_MODEL
        await conn.execute("""
            INSERT INTO user_interest_vectors (user_id, event_count) VALUES ($1, 150)
            ON CONFLICT (user_id) DO UPDATE SET event_count = 150
        """, uid)
    
    print("\n✅ Seeding Complete!")
    print(f"Created {len(users)} users, {len(videos)} videos, and 6000 interactions.")
    print("The worker container should pick up the 5000 milestone and start training within 60 seconds.")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(seed_db())
