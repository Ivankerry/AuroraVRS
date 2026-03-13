import os
import random
import time
import requests
import asyncpg
import asyncio
from typing import List, Dict

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = os.getenv("API_URL", "http://localhost:8080/api/v1")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

PERSONA_COUNT = 100
EVENTS_PER_USER_AVG = 150

# ── Personas ──────────────────────────────────────────────────────────────────
# A persona library with varied interest profiles
ARCHETYPES = [
    {"name": "Sports Fanatic", "core_cats": ["Sports", "Fitness"]},
    {"name": "Gamer Pro", "core_cats": ["Gaming", "Tech"]},
    {"name": "Cooking Hobbyist", "core_cats": ["Food", "Lifestyle"]},
    {"name": "Movie Buff", "core_cats": ["Entertainment", "Movies"]},
    {"name": "Traveler", "core_cats": ["Travel", "Nature"]},
    {"name": "Tech Geek", "core_cats": ["Tech", "Electronics"]},
    {"name": "Fitness Freak", "core_cats": ["Fitness", "Health"]},
    {"name": "Pet Lover", "core_cats": ["Pets", "Animals"]},
    {"name": "Artist", "core_cats": ["Art", "Design"]},
    {"name": "News Junkie", "core_cats": ["News", "Politics"]},
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def register_and_login(email, name):
    password = "sim_user_pass_123"
    try:
        r = requests.post(f"{BASE_URL}/auth/register", json={"email": email, "password": password, "names": name}, timeout=10)
        if r.status_code in (200, 201):
            return r.json().get("access_token")
    except: pass
    
    try:
        r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
        if r.status_code == 200:
            return r.json().get("access_token")
    except: pass
    return None

def fire_api_event(token, video_id, event_type, watch_ratio=1.0):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        if event_type == "LIKE":
            requests.post(f"{BASE_URL}/videos/{video_id}/like", headers=headers, timeout=5)
        elif event_type == "DISLIKE":
            requests.post(f"{BASE_URL}/videos/{video_id}/dislike", headers=headers, timeout=5)
        else:
            payload = {"video_id": video_id, "event_type": event_type, "watch_ratio": watch_ratio}
            requests.post(f"{BASE_URL}/events", json=payload, headers=headers, timeout=5)
    except: pass

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    print("\n🚀 AURORA-VRS ADVANCED BEHAVIOR SIMULATOR")
    print("═" * 50)
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    # 1. Fetch available categories and videos from LOCAL DB
    print("🔍 Fetching videos from local database...")
    cat_rows = await conn.fetch("SELECT id, name FROM categories")
    db_categories = {r['name']: r['id'] for r in cat_rows}
    
    video_pools = {}
    for cat_name, cat_id in db_categories.items():
        v_rows = await conn.fetch("""
            SELECT vc.video_id FROM video_categories vc
            JOIN videos v ON v.id = vc.video_id
            WHERE vc.category_id = $1 AND v.status = 'READY'
        """, cat_id)
        if v_rows:
            video_pools[cat_name] = [str(r['video_id']) for r in v_rows]
            print(f"  📦 Pool [{cat_name:<10}]: {len(v_rows)} videos")

    if not video_pools:
        print("❌ Error: No videos found in any categories. Is the seeder finished?")
        await conn.close()
        return

    # 2. Simulate 100+ Users
    print(f"\n👥 Simulating {PERSONA_COUNT} users...")
    total_events = 0
    all_cat_names = list(video_pools.keys())
    
    for i in range(PERSONA_COUNT):
        arch = random.choice(ARCHETYPES)
        name = f"{arch['name']} {i+1}"
        email = f"sim_user_{i}_{int(time.time())}@aurora.sim"
        
        token = register_and_login(email, name)
        if not token:
            print(f"  ⚠️ Skipping {name} (Register failed)")
            continue

        # Interests: Core + some random noise
        interests = [c for c in arch['core_cats'] if c in video_pools]
        if not interests: # Fallback if persona cats don't exist in DB
            interests = [random.choice(all_cat_names)]
            
        noise_cat = random.choice(all_cat_names)
        if noise_cat not in interests:
            interests.append(noise_cat)

        event_count = random.randint(50, EVENTS_PER_USER_AVG * 2)
        print(f"  [{i+1:03}/100] {name:<20} | Interests: {', '.join(interests)} | Firing {event_count} events...")
        
        for _ in range(event_count):
            coin = random.random()
            
            # High Engagement (Likely core interest)
            if coin < 0.7:
                cat = random.choice(interests)
                vid = random.choice(video_pools[cat])
                
                # Interaction Type
                sub_coin = random.random()
                if sub_coin < 0.6: # High Watch Ratio
                    fire_api_event(token, vid, "VIEW", watch_ratio=random.uniform(0.7, 1.0))
                if sub_coin < 0.3: # Like
                    fire_api_event(token, vid, "LIKE")
                if sub_coin < 0.1: # Share
                    fire_api_event(token, vid, "SHARE")
            
            # Low Engagement / Negative (Likely non-interest)
            else:
                other_cats = [c for c in all_cat_names if c not in interests]
                if not other_cats: other_cats = [random.choice(all_cat_names)]
                
                cat = random.choice(other_cats)
                vid = random.choice(video_pools[cat])
                
                neg_coin = random.random()
                if neg_coin < 0.5: # Skip
                    fire_api_event(token, vid, "VIEW", watch_ratio=random.uniform(0.01, 0.15))
                if neg_coin < 0.1: # Dislike
                    fire_api_event(token, vid, "DISLIKE")

            total_events += 1

    print("\n" + "═" * 50)
    print(f"✅ SIMULATION COMPLETE. Total Events Fired: {total_events:,}")
    print("═" * 50)
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
