import requests
import random
import time
import asyncio
import asyncpg
import numpy as np
from collections import defaultdict
import os

# ── Config ────────────────────────────────────────────────────────────────────
# If running inside Docker, use service names. If running from host, use VPS IP.
BASE_URL     = os.getenv("API_URL", "http://62.84.176.140:8080/api/v1")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

# Milestone 2: 20 Users, Overlapping Interests
USER_PROFILES = [
    {"name": "Tech Enthusiast",   "cats": ["Tech"]},
    {"name": "Music Lover",        "cats": ["Music"]},
    {"name": "Gamer",             "cats": ["Gaming"]},
    {"name": "Educator",          "cats": ["Education"]},
    {"name": "Comedy Fan",         "cats": ["Comedy"]},
    
    # Overlapping Interests (The "Blending" Test)
    {"name": "Tech/Gamer",        "cats": ["Tech", "Gaming"]},
    {"name": "Music/Comedy",      "cats": ["Music", "Comedy"]},
    {"name": "Edu/Tech",          "cats": ["Education", "Tech"]},
    {"name": "Gamer/Comedy",      "cats": ["Gaming", "Comedy"]},
    {"name": "Music/Tech",        "cats": ["Music", "Tech"]},
    {"name": "Gaming/Edu",        "cats": ["Gaming", "Education"]},
    {"name": "Comedy/Edu",        "cats": ["Comedy", "Education"]},
    {"name": "Tech/Music/Gamer",  "cats": ["Tech", "Music", "Gaming"]},
    {"name": "Omnivore",          "cats": ["Tech", "Music", "Gaming", "Comedy", "Education"]},
    
    # Duplicate categories to reach 20
    {"name": "Tech Lead",         "cats": ["Tech"]},
    {"name": "Indie Listener",    "cats": ["Music"]},
    {"name": "Pro Gamer",         "cats": ["Gaming"]},
    {"name": "Professor",         "cats": ["Education"]},
    {"name": "Joke Teller",       "cats": ["Comedy"]},
    {"name": "Hardware Geek",     "cats": ["Tech", "Gaming"]},
]

VIEWS_PER_USER = 100   # Sufficient for interaction signal
LIKES_PER_USER = 150   # Ground truth
SKIPS_PER_USER = 20    # Negative signal

# ── Scoring ───────────────────────────────────────────────────────────────────
def dcg(relevances):
    return sum(rel / np.log2(idx + 2) for idx, rel in enumerate(relevances))

def ndcg_at_k(recommended_ids, relevant_ids, k=10):
    top_k = recommended_ids[:k]
    relevances = [1 if vid in relevant_ids else 0 for vid in top_k]
    actual_dcg  = dcg(relevances)
    ideal_dcg   = dcg(sorted(relevances, reverse=True))
    return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0

# ── Helpers ───────────────────────────────────────────────────────────────────
def register(email, name, password):
    try:
        r = requests.post(f"{BASE_URL}/auth/register", json={
            "email": email, "password": password, "names": name
        }, timeout=10)
        if r.status_code == 200: return r.json()["access_token"]
    except: pass
    
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email, "password": password
    }, timeout=10)
    if r.status_code == 200: return r.json()["access_token"]
    raise Exception(f"Could not register/login {email}")

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

def fire_event(token, video_id, event_type, ratio=None):
    try:
        url = f"{BASE_URL}/videos/{video_id}/like" if event_type == "LIKE" else f"{BASE_URL}/events"
        payload = {"video_id": video_id, "event_type": event_type, "watch_ratio": ratio, "metadata": {}} if event_type != "LIKE" else None
        r = requests.post(url, json=payload, headers=auth_headers(token), timeout=5)
        return r.status_code == 200
    except: return False

def get_feed(token):
    try:
        r = requests.get(f"{BASE_URL}/feed", headers=auth_headers(token), timeout=10)
        return [v["id"] for v in r.json().get("videos", [])]
    except: return []

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    print("\n" + "═" * 80)
    print("       🧪 AURORA-VRS MILESTONE 2: MULTI-INTEREST VECTOR BLENDING EVAL")
    print("═" * 80)
    print(f"  Users         : {len(USER_PROFILES)}")
    print(f"  Complexity    : Single, Dual, and Triple Interest Profiles")
    print("═" * 80)

    conn = await asyncpg.connect(DATABASE_URL)
    
    # Load Video Pools
    all_cats = list(set([c for p in USER_PROFILES for c in p["cats"]]))
    cat_pools = {}
    for cat in all_cats:
        ids = [str(r['id']) for r in await conn.fetch("""
            SELECT v.id FROM videos v
            JOIN video_categories vc ON v.id = vc.video_id
            JOIN categories c ON vc.category_id = c.id
            WHERE c.name = $1 AND v.privacy = 'PUBLIC' AND v.status = 'READY'
            LIMIT 500
        """, cat)]
        cat_pools[cat] = ids
        print(f"  📦 Pool [{cat:<10}]: {len(ids)} videos")

    # Step 2: Generation
    timestamp = int(time.time())
    users_data = []
    
    print(f"\n🚀 GENERATING INTERACTION SIGNALS...")
    for idx, profile in enumerate(USER_PROFILES):
        p_cats = profile["cats"]
        name   = profile["name"]
        email  = f"m2_{idx}_{timestamp}@aurora.com"
        token  = register(email, name, "eval_pass_123!")
        
        print(f"  [{idx+1:02}/20] {name:<18} | Interests: {', '.join(p_cats)}")
        
        ground_truth_likes = set()
        
        # Mix categories for views/likes
        for _ in range(VIEWS_PER_USER):
            cat = random.choice(p_cats)
            vid = random.choice(cat_pools[cat])
            fire_event(token, vid, "VIEW", ratio=round(random.uniform(0.8, 1.0), 2))
            
        for _ in range(LIKES_PER_USER):
            cat = random.choice(p_cats)
            vid = random.choice(cat_pools[cat])
            if fire_event(token, vid, "LIKE"):
                ground_truth_likes.add(vid)
                
        # Skip garbage
        other_cats = [c for c in all_cats if c not in p_cats]
        if other_cats:
            for _ in range(SKIPS_PER_USER):
                cat = random.choice(other_cats)
                if cat_pools.get(cat):
                    vid = random.choice(cat_pools[cat])
                    fire_event(token, vid, "SKIP", ratio=0.05)
        
        users_data.append({"name": name, "cats": p_cats, "token": token, "gt": ground_truth_likes})

    print(f"\n⏳ WAITING 30s FOR VECTOR PROPAGATION & WORKER PROCESSING...")
    for i in range(30, 0, -1):
        if i % 5 == 0: print(f"  ... {i}s remaining")
        time.sleep(1)

    # Step 3: Evaluation
    print(f"\n📊 TRIGGERING MODEL SYNC & REBUILD ON VPS...")
    try:
        # Note: This requires the first test user to be promoted to ADMIN
        r = requests.post(f"{BASE_URL}/ml/rebuild-index", headers=auth_headers(users_data[0]["token"]), timeout=15)
        if r.status_code == 200:
            print("  ✅ ML Sync Triggered (Retrain scheduled + FAISS reload)")
        else:
            print(f"  ⚠️  ML Sync Status: {r.status_code}. (Hint: Promote first user to ADMIN)")
    except Exception as e:
        print(f"  ⚠️  ML Sync Trigger failed: {e}")

    print(f"\n⏳ WAITING 60s FOR WORKER TO GESTATE & RELOAD MODEL...")
    for i in range(60, 0, -1):
        if i % 15 == 0: print(f"  ... {i}s remaining")
        time.sleep(1)

    print(f"\n📊 EVALUATING FEED ALIGNMENT & PRECORE SCORES...")
    print(f"\n{'User':<20} {'Interests':<25} {'Hits@10':<8} {'NDCG@10':<10} {'Align@10'}")
    print("-" * 80)
    
    total_ndcg = []
    total_align = []

    for user in users_data:
        feed = get_feed(user["token"])
        if not feed:
            print(f"{user['name']:<20} {'EMPTY FEED':<25}")
            continue
            
        # Get cat metadata for feed
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
        
        interests_str = ", ".join(user["cats"])
        print(f"{user['name']:<20} {interests_str:<25} {hits:<8} {score_ndcg:<10.4f} {align_count}/10")

    await conn.close()

    print("\n" + "═" * 80)
    print("  🏁 MILESTONE 2 SUMMARY")
    print("═" * 80)
    avg_ndcg = np.mean(total_ndcg) if total_ndcg else 0
    avg_align = np.mean(total_align) if total_align else 0
    
    print(f"  Avg NDCG@10           : {avg_ndcg:.4f}")
    print(f"  Avg Interest Align@10 : {avg_align*100:.1f}%")
    
    if avg_align > 0.7 and avg_ndcg > 0.15:
        print("\n  ✅ SUCCESS: System handles multi-interest blending effectively.")
    elif avg_align > 0.5:
        print("\n  🟡 WARNING: Personalization is working, but ranking (NDCG) is loose.")
    else:
        print("\n  ❌ FAILURE: Recommendations are not aligning with user multi-interest profiles.")
    print("═" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())