import os
import requests
import asyncpg
import asyncio
import numpy as np
from collections import defaultdict
from tabulate import tabulate # Fallback to manual formatting if not on VPS

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL     = os.getenv("API_URL", "http://localhost:8080/api/v1")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

# Default password for simulated users
SIM_PASSWORD = "sim_user_pass_123"

async def get_token(email):
    try:
        r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": SIM_PASSWORD}, timeout=10)
        if r.status_code == 200:
            return r.json().get("access_token")
    except: pass
    return None

async def fetch_feed_count(token):
    try:
        r = requests.get(f"{BASE_URL}/feed", headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if r.status_code == 200:
            videos = r.json().get("videos", [])
            return len(videos), [v['id'] for v in videos]
    except: pass
    return 0, []

async def get_video_categories(conn, video_ids):
    if not video_ids: return {}
    rows = await conn.fetch("""
        SELECT v.id, c.name FROM videos v
        JOIN video_categories vc ON v.id = vc.video_id
        JOIN categories c ON vc.category_id = c.id
        WHERE v.id = ANY($1::uuid[])
    """, [id for id in video_ids])
    v_map = defaultdict(list)
    for r in rows:
        v_map[str(r['id'])].append(r['name'])
    return v_map

async def main():
    print("\n" + "═" * 80)
    print("       👥 AURORA-VRS: POPULATION RECOMMENDATION COVERAGE REPORT")
    print("═" * 80)

    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return

    # 1. Fetch all simulated users
    print("🔍 Searching for simulated users (@aurora.sim)...")
    users = await conn.fetch("SELECT email, names FROM users WHERE email LIKE '%@aurora.sim'")
    print(f"  Found {len(users)} simulated users.")

    if not users:
        print("❌ No simulated users found. Run advanced_behavior_seeder.py first.")
        await conn.close()
        return

    results = []
    global_seen_videos = set()
    category_reach = defaultdict(int)

    # 2. Process each user
    print(f"\n🚀 Scanning feed for {len(users)} users (this may take a minute)...")
    for idx, u in enumerate(users):
        email = u['email']
        name = u['names'] or "Unknown"
        
        token = await get_token(email)
        if not token:
            print(f"  [{idx+1:03}] ⚠️ Login failed for {email}")
            continue
            
        count, vids = await fetch_feed_count(token)
        for v in vids: global_seen_videos.add(v)
        
        # Check alignment (Top 10)
        v_cats = await get_video_categories(conn, vids[:10])
        # Note: We don't have user interests saved in DB directly in a structured way 
        # unless we parse their events. For this report, we'll focus on the "Count".
        
        results.append([name, email, count])
        print(f"  [{idx+1:03}/{len(users)}] {name:<25} | Received: {count} videos")

    # 3. Final Summary
    print("\n" + "═" * 80)
    print("📊 POPULATION COVERAGE SUMMARY")
    print("-" * 80)
    
    counts = [r[2] for r in results]
    avg_rec = np.mean(counts) if counts else 0
    min_rec = np.min(counts) if counts else 0
    max_rec = np.max(counts) if counts else 0
    
    print(f"  Total Users Scanned:      {len(results)}")
    print(f"  Average Recs Per User:    {avg_rec:.1f}")
    print(f"  Min Recommendations:      {min_rec}")
    print(f"  Max Recommendations:      {max_rec}")
    print(f"  Global Unique Videos:     {len(global_seen_videos)} items surfaced")
    
    # Check catalog reach if we can get total Ready videos
    total_ready = await conn.fetchval("SELECT count(*) FROM videos WHERE status = 'READY'")
    reach_pct = (len(global_seen_videos) / total_ready * 100) if total_ready else 0
    print(f"  Catalog Reach:            {reach_pct:.1f}% ({len(global_seen_videos)}/{total_ready})")
    print("═" * 80 + "\n")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
