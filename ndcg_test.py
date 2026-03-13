import requests
import random
import time
import asyncio
import asyncpg
import numpy as np
from collections import defaultdict
import os
import json

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL     = os.getenv("API_URL", "http://localhost:8080/api/v1")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

# Admin Credentials
ADMIN_EMAIL = "testone@gmail.com"
ADMIN_PASS  = "test123" 

USER_PROFILES = [
    {"name": "Tech Enthusiast",   "cats": ["Tech"]},
    {"name": "Music Lover",        "cats": ["Music"]},
    {"name": "Gamer",             "cats": ["Gaming"]},
    {"name": "Educator",          "cats": ["Education"]},
    {"name": "Pet Lover",         "cats": ["Pets", "Animals"]},
    {"name": "Tech/Gamer",        "cats": ["Tech", "Gaming"]},
    {"name": "Traveler",          "cats": ["Travel", "Nature"]},
    {"name": "Omnivore",          "cats": ["Tech", "Music", "Gaming", "Comedy", "Education", "Sports"]},
]

# ── Scoring ───────────────────────────────────────────────────────────────────
def dcg(relevances):
    return sum(rel / np.log2(idx + 2) for idx, rel in enumerate(relevances))

def ndcg_at_k(recommended_ids, relevant_ids, k=10):
    if not relevant_ids: return 0.0
    top_k = recommended_ids[:k]
    relevances = [1 if vid in relevant_ids else 0 for vid in top_k]
    actual_dcg  = dcg(relevances)
    ideal_relevances = [1] * min(len(relevant_ids), k)
    ideal_dcg   = dcg(ideal_relevances)
    return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0

# ── Helpers ───────────────────────────────────────────────────────────────────
def login_or_register(email, name="Eval User", password="eval_pass_123!"):
    try:
        r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=5)
        if r.status_code == 200: return r.json()["access_token"]
    except: pass
    try:
        r = requests.post(f"{BASE_URL}/auth/register", json={"email": email, "password": password, "names": name}, timeout=5)
        if r.status_code == 200: return r.json()["access_token"]
    except: pass
    return None

def auth_headers(token): return {"Authorization": f"Bearer {token}"}

async def get_video_categories(conn, video_ids):
    if not video_ids: return {}
    rows = await conn.fetch("""
        SELECT v.id, c.name FROM videos v
        JOIN video_categories vc ON v.id = vc.video_id
        JOIN categories c ON vc.category_id = c.id
        WHERE v.id = ANY($1::uuid[])
    """, [id for id in video_ids])
    v_cats = defaultdict(list)
    for r in rows:
        v_cats[str(r['id'])].append(r['name'])
    return v_cats

def fire_event(token, video_id, event_type, ratio=1.0):
    try:
        url = f"{BASE_URL}/videos/{video_id}/like" if event_type == "LIKE" else f"{BASE_URL}/events"
        payload = {"video_id": video_id, "event_type": event_type, "watch_ratio": ratio} if event_type != "LIKE" else None
        r = requests.post(url, json=payload, headers=auth_headers(token), timeout=5)
        return r.status_code in (200, 201)
    except: return False

def get_feed(token):
    try:
        r = requests.get(f"{BASE_URL}/feed", headers=auth_headers(token), timeout=10)
        return r.json().get("videos", [])
    except: return []

async def poll_ml_status(token):
    print("  🔍 Polling ML Status...")
    for _ in range(15):
        try:
            r = requests.get(f"{BASE_URL}/ml/status", headers=auth_headers(token), timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get("two_tower_active"):
                    print(f"  ✅ Model Status: ACTIVE (FAISS items: {data.get('faiss_size')})")
                    return True
        except: pass
        time.sleep(10)
    return False

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    print("\n" + "═" * 110)
    print("       🧪 AURORA-VRS: ADVANCED ALIGNMENT & NDCG EVALUATION (LOCAL DB)")
    print("═" * 110)

    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return

    # 1. Fetch Pools from LOCAL DB
    print("\n📦 PHASE 1: Fetching catalog pools...")
    cat_rows = await conn.fetch("SELECT name FROM categories")
    db_cats = [r['name'] for r in cat_rows]
    
    cat_pools = {}
    for cat in db_cats:
        ids = [str(r['video_id']) for r in await conn.fetch("""
            SELECT vc.video_id FROM video_categories vc
            JOIN videos v ON v.id = vc.video_id
            JOIN categories c ON c.id = vc.category_id
            WHERE c.name = $1 AND v.status = 'READY'
            LIMIT 50
        """, cat)]
        if ids: cat_pools[cat] = ids

    # 2. Setup Evaluation Users
    print("\n🚀 PHASE 2: Setting up test users...")
    timestamp = int(time.time())
    eval_users = []
    
    for idx, profile in enumerate(USER_PROFILES):
        valid_cats = [c for c in profile['cats'] if c in cat_pools]
        if not valid_cats: continue
        
        email = f"eval_adv_{idx}_{timestamp}@aurora.test"
        token = login_or_register(email, profile['name'])
        if not token: continue
        
        gt_likes = set()
        print(f"  Preparing {profile['name']:<18} | Interests: {', '.join(valid_cats)}")
        
        # Give them some "History" so the model has something to rank
        for _ in range(15):
            cat = random.choice(valid_cats)
            vid = random.choice(cat_pools[cat])
            fire_event(token, vid, "VIEW", ratio=0.95)
            if random.random() < 0.4:
                fire_event(token, vid, "LIKE")
                gt_likes.add(vid)

        eval_users.append({"name": profile['name'], "cats": valid_cats, "token": token, "gt": gt_likes})

    # 3. Model Refresh
    print("\n🔄 Refreshing ML Engine...")
    admin_token = login_or_register(ADMIN_EMAIL, "Admin", ADMIN_PASS)
    if admin_token:
        requests.post(f"{BASE_URL}/ml/rebuild-index", headers=auth_headers(admin_token), timeout=45)
    await poll_ml_status(admin_token if admin_token else eval_users[0]['token'])

    # 4. Detailed Alignment Evaluation
    print(f"\n📊 ADVANCED EVALUATION RESULTS")
    print(f"{'User Persona':<22} {'Interests':<30} {'Retrieved':<10} {'Aligned':<8} {'Align %':<10} {'NDCG@10'}")
    print("-" * 110)
    
    total_align_scores = []
    total_ndcg_scores = []

    for user in eval_users:
        feed = get_feed(user["token"])
        retrieved_count = len(feed)
        top_10 = feed[:10]
        
        feed_vids = [v['id'] for v in top_10]
        feed_cats = await get_video_categories(conn, feed_vids)
        
        align_count = 0
        for vid in feed_vids:
            v_cats = feed_cats.get(vid, [])
            if any(c in user["cats"] for c in v_cats):
                align_count += 1
        
        align_pct = (align_count / len(top_10)) * 100 if top_10 else 0
        score_ndcg = ndcg_at_k(feed_vids, user["gt"])
        
        total_align_scores.append(align_pct)
        total_ndcg_scores.append(score_ndcg)
        
        ints_str = ", ".join(user["cats"])[:30]
        print(f"{user['name']:<22} {ints_str:<30} {retrieved_count:<10} {align_count:<8} {align_pct:>6.1f}%    {score_ndcg:.4f}")

    print("-" * 110)
    avg_align = np.mean(total_align_scores) if total_align_scores else 0
    avg_ndcg = np.mean(total_ndcg_scores) if total_ndcg_scores else 0
    print(f"{'TOTAL AVERAGE':<62} {avg_align:>14.1f}%    {avg_ndcg:.4f}")
    print("═" * 110 + "\n")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())