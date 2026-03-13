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
# Use localhost for VPS local testing or the provided IP for remote
DEFAULT_URL = "http://localhost:8080/api/v1"
BASE_URL     = os.getenv("API_URL", DEFAULT_URL)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

# Admin Credentials (Default System Seeder user)
ADMIN_EMAIL = "seeder@aurora.vrs"
ADMIN_PASS  = "admin123" 

USER_PROFILES = [
    {"name": "Tech Enthusiast",   "cats": ["Tech"]},
    {"name": "Music Lover",        "cats": ["Music"]},
    {"name": "Gamer",             "cats": ["Gaming"]},
    {"name": "Educator",          "cats": ["Education"]},
    {"name": "Comedy Fan",         "cats": ["Comedy"]},
    {"name": "Tech/Gamer",        "cats": ["Tech", "Gaming"]},
    {"name": "Music/Comedy",      "cats": ["Music", "Comedy"]},
    {"name": "Omnivore",          "cats": ["Tech", "Music", "Gaming", "Comedy", "Education"]},
]

VIEWS_PER_USER = 20
LIKES_PER_USER = 10
SKIPS_PER_USER = 5

# ── Scoring ───────────────────────────────────────────────────────────────────
def dcg(relevances):
    return sum(rel / np.log2(idx + 2) for idx, rel in enumerate(relevances))

def ndcg_at_k(recommended_ids, relevant_ids, k=10):
    if not relevant_ids: return 0.0
    top_k = recommended_ids[:k]
    relevances = [1 if vid in relevant_ids else 0 for vid in top_k]
    actual_dcg  = dcg(relevances)
    # Ideal DCG is for a list where all top items are relevant (up to the number of relevant items we have)
    ideal_relevances = [1] * min(len(relevant_ids), k)
    ideal_dcg   = dcg(ideal_relevances)
    return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0

# ── Helpers ───────────────────────────────────────────────────────────────────
def login_or_register(email, name="Eval User", password="eval_pass_123!"):
    # Try Login
    try:
        r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=5)
        if r.status_code == 200: return r.json()["access_token"]
    except: pass
    
    # Try Register
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
        if event_type == "LIKE":
            url = f"{BASE_URL}/videos/{video_id}/like"
            r = requests.post(url, headers=auth_headers(token), timeout=5)
        else:
            url = f"{BASE_URL}/events"
            payload = {"video_id": video_id, "event_type": event_type, "watch_ratio": ratio}
            r = requests.post(url, json=payload, headers=auth_headers(token), timeout=5)
        return r.status_code in (200, 201)
    except: return False

def get_feed(token):
    try:
        r = requests.get(f"{BASE_URL}/feed", headers=auth_headers(token), timeout=10)
        if r.status_code == 200:
            return [v["id"] for v in r.json().get("videos", [])]
    except: pass
    return []

async def poll_ml_status(token):
    print("  🔍 Polling ML Status...")
    for _ in range(15): # Wait up to 2.5 mins
        try:
            r = requests.get(f"{BASE_URL}/ml/status", headers=auth_headers(token), timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get("two_tower_active"):
                    print(f"  ✅ Model Status: ACTIVE (FAISS items: {data.get('faiss_size')})")
                    return True
                print(f"  ⏳ Model Status: Loading... (Loaded: {data.get('model_loaded')}, FAISS: {data.get('faiss_ready')})")
        except: pass
        time.sleep(10)
    return False

# ── Evaluation ────────────────────────────────────────────────────────────────
async def evaluate_users(conn, users_data, title="Evaluation"):
    print(f"\n📊 {title}")
    print(f"{'User':<22} {'Interests':<25} {'Hits@10':<8} {'NDCG@10':<10} {'Align@10'}")
    print("-" * 100)
    
    total_ndcg = []
    total_align = []

    for user in users_data:
        feed = get_feed(user["token"])
        if not feed:
            print(f"{user['name']:<22} {'EMPTY FEED':<25}")
            continue
            
        feed_cats = await get_video_categories(conn, feed[:10])
        align_count = 0
        for vid in feed[:10]:
            v_cats = feed_cats.get(vid, [])
            if any(c in user["cats"] for c in v_cats):
                align_count += 1
        
        score_ndcg = ndcg_at_k(feed, user["gt"])
        hits = sum(1 for vid in feed[:10] if vid in user["gt"])
        
        total_ndcg.append(score_ndcg)
        total_align.append(align_count / 10.0)
        
        interests_str = ", ".join(user["cats"])[:25]
        print(f"{user['name']:<22} {interests_str:<25} {hits:<8} {score_ndcg:<10.4f} {align_count}/10")

    avg_ndcg = np.mean(total_ndcg) if total_ndcg else 0
    avg_align = np.mean(total_align) if total_align else 0
    print("-" * 100)
    print(f"{'AVERAGE':<48} {avg_ndcg:.4f}     {avg_align*100:.1f}%")
    return avg_ndcg, avg_align

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    print("\n" + "═" * 100)
    print("       🧪 AURORA-VRS: ACCURATE NDCG & PERSONALIZATION EVALUATION")
    print("═" * 100)

    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ Could not connect to database: {e}")
        return

    # 1. Check for seeded content
    print("\n📦 PHASE 1: Checking Data Availability")
    all_cats_rows = await conn.fetch("SELECT name FROM categories")
    all_available_cats = [r['name'] for r in all_cats_rows]
    print(f"  Available Categories: {len(all_available_cats)}")
    
    cat_pools = {}
    for cat in all_available_cats:
        ids = [str(r['id']) for r in await conn.fetch("""
            SELECT v.id FROM videos v
            JOIN video_categories vc ON v.id = vc.video_id
            JOIN categories c ON vc.category_id = c.id
            WHERE c.name = $1 AND v.privacy = 'PUBLIC' AND v.status = 'READY'
            LIMIT 100
        """, cat)]
        if ids: cat_pools[cat] = ids
    
    if not cat_pools:
        print("❌ CRITICAL: No videos found in any categories. Is Phase 1 of Seeder finished?")
        await conn.close()
        return

    # 2. Cold-Start Validation (Injecting targeted behavior for new users)
    print("\n🚀 PHASE 2: Generating Test Interactions (Cold-Start)")
    timestamp = int(time.time())
    new_users = []
    
    for idx, profile in enumerate(USER_PROFILES):
        name = f"Test_{profile['name']}_{timestamp}"
        email = f"eval_{idx}_{timestamp}@aurora.com"
        token = login_or_register(email, name)
        if not token: continue
        
        # Filter for cats we have videos for
        valid_cats = [c for c in profile['cats'] if c in cat_pools]
        if not valid_cats: continue

        print(f"  [{idx+1}/{len(USER_PROFILES)}] {profile['name']:<18} | Generating {VIEWS_PER_USER} views...")
        gt_likes = set()
        
        for _ in range(VIEWS_PER_USER):
            cat = random.choice(valid_cats)
            vid = random.choice(cat_pools[cat])
            fire_event(token, vid, "VIEW", ratio=0.9)
            
        for _ in range(LIKES_PER_USER):
            cat = random.choice(valid_cats)
            vid = random.choice(cat_pools[cat])
            if fire_event(token, vid, "LIKE"):
                gt_likes.add(vid)
                
        new_users.append({"name": profile['name'], "cats": valid_cats, "token": token, "gt": gt_likes})

    # 3. Trigger Model Refresh (So the system "sees" these new interactions)
    print("\n🔄 Triggering Model & Index Refresh...")
    admin_token = login_or_register(ADMIN_EMAIL, "System Admin", ADMIN_PASS)
    if admin_token:
        try:
            r = requests.post(f"{BASE_URL}/ml/rebuild-index", headers=auth_headers(admin_token), timeout=45)
            if r.status_code == 200:
                print("  ✅ ML Rebuild Triggered.")
            else:
                print(f"  ⚠️ Trigger returned {r.status_code}: {r.text}")
        except Exception as e:
            print(f"  ⚠️ ML Sync Trigger failed: {e}")
    else:
        print("  ⚠️ Admin Login Failed (seeder@aurora.vrs). Try manual rebuild or wait 30 minutes.")

    # Wait for the model to update
    if not await poll_ml_status(admin_token if admin_token else new_users[0]['token']):
        print("  ⚠️ Model is not active or took too long. Results may be random/empty.")

    # 4. Evaluation
    avg_ndcg, avg_align = await evaluate_users(conn, new_users, "ACCURACY EVALUATION SUMMARY")

    print("\n" + "═" * 100)
    if avg_align > 0.7 and avg_ndcg > 0.1:
        print("  🏆 RESULT: EXCELLENT. The model is accurately learning and personalizing.")
    elif avg_align > 0.4:
        print("  🥈 RESULT: PASSABLE. Personalization is working, but ranking is still loose.")
    else:
        print("  🥉 RESULT: WEAK. Ensure seeder Phase 2 (events) is deep enough.")
    print("═" * 100 + "\n")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())