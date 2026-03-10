import requests
import random
import time
import asyncio
import asyncpg
import numpy as np
from collections import defaultdict

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL     = "http://62.84.176.140:8080/api/v1"
DATABASE_URL = "postgresql://user:pass@localhost:5432/db"

# 2 users only
USER_PROFILES = [
    {"name": "Tech User 1",  "category": "Tech"},
    {"name": "Music User 1", "category": "Music"},
]

VIEWS_PER_USER = 150   # deep watch events
LIKES_PER_USER = 200   # like events (these become ground truth)
SKIPS_PER_USER = 30    # skip events on opposite category

# ── Scoring ───────────────────────────────────────────────────────────────────
def dcg(relevances):
    return sum(rel / np.log2(idx + 2) for idx, rel in enumerate(relevances))

def ndcg_at_k(recommended_ids, relevant_ids, k=10):
    top_k = recommended_ids[:k]
    relevances = [1 if vid in relevant_ids else 0 for vid in top_k]
    actual_dcg  = dcg(relevances)
    ideal_dcg   = dcg(sorted(relevances, reverse=True))
    return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0

def precision_at_k(recommended_ids, relevant_ids, k=10):
    top_k = recommended_ids[:k]
    hits  = sum(1 for vid in top_k if vid in relevant_ids)
    return hits / k

# ── Helpers ───────────────────────────────────────────────────────────────────
def register(email, name, password):
    r = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": password, "names": name
    })
    if r.status_code == 200:
        return r.json()["access_token"]
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email, "password": password
    })
    if r.status_code == 200:
        return r.json()["access_token"]
    raise Exception(f"Could not register or login {email}: {r.text}")

def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

def fire_view(token, video_id, watch_ratio):
    try:
        r = requests.post(f"{BASE_URL}/events", json={
            "video_id":    video_id,
            "event_type":  "VIEW",
            "watch_ratio": watch_ratio,
            "metadata":    {}
        }, headers=auth_headers(token), timeout=5)
        return r.status_code == 200
    except:
        return False

def fire_like(token, video_id):
    try:
        r = requests.post(f"{BASE_URL}/videos/{video_id}/like",
                          headers=auth_headers(token), timeout=5)
        return r.status_code == 200
    except:
        return False

def fire_skip(token, video_id):
    try:
        r = requests.post(f"{BASE_URL}/events", json={
            "video_id":    video_id,
            "event_type":  "SKIP",
            "watch_ratio": round(random.uniform(0.0, 0.1), 2),
            "metadata":    {}
        }, headers=auth_headers(token), timeout=5)
        return r.status_code == 200
    except:
        return False

def get_feed(token):
    try:
        r = requests.get(f"{BASE_URL}/feed", headers=auth_headers(token), timeout=10)
        return [v["id"] for v in r.json().get("videos", [])]
    except:
        return []

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    print("\n" + "=" * 65)
    print("       🧪 AURORA-VRS NDCG & PRECISION@10 EVALUATION")
    print("=" * 65)
    print(f"  Users         : {len(USER_PROFILES)}")
    print(f"  Views/user    : {VIEWS_PER_USER}")
    print(f"  Likes/user    : {LIKES_PER_USER}  ← ground truth")
    print(f"  Skips/user    : {SKIPS_PER_USER}  ← negative signal")
    print("=" * 65)

    # ── Step 1: Fetch category video pools ───────────────────────────────────
    print(f"\n📦 STEP 1: Loading video pools from database...")
    conn = await asyncpg.connect(DATABASE_URL)

    categories = list(set(p["category"] for p in USER_PROFILES))
    category_videos = {}

    for cat in categories:
        ids = [str(r['id']) for r in await conn.fetch("""
            SELECT v.id FROM videos v
            JOIN video_categories vc ON v.id = vc.video_id
            JOIN categories c ON vc.category_id = c.id
            WHERE c.name = $1 AND v.privacy = 'PUBLIC' AND v.status = 'READY'
            LIMIT 500
        """, cat)]
        category_videos[cat] = ids
        print(f"  ✅ {cat:<12} : {len(ids)} videos available")

    await conn.close()

    # ── Step 2: Create users and fire events ──────────────────────────────────
    print(f"\n👤 STEP 2: Creating users and firing events...")
    timestamp  = int(time.time())
    user_results = []

    for idx, profile in enumerate(USER_PROFILES):
        cat      = profile["category"]
        name     = profile["name"]
        email    = f"ndcg_{cat.lower()}_{idx}_{timestamp}@test.com"
        password = "ndcg_test_123!"

        print(f"\n  [{idx+1}/{len(USER_PROFILES)}] {name} (loves {cat})")
        print(f"    → Registering...")
        token = register(email, name, password)
        print(f"    ✅ Registered")

        target_pool   = category_videos.get(cat, [])
        opposite_cats = [c for c in categories if c != cat]
        opposite_pool = []
        for oc in opposite_cats:
            opposite_pool.extend(category_videos.get(oc, [])[:50])

        if len(target_pool) < 10:
            print(f"    ❌ Not enough videos for {cat}, skipping")
            continue

        # Fire deep watch VIEW events
        view_count = 0
        for i in range(VIEWS_PER_USER):
            vid = random.choice(target_pool)
            if fire_view(token, vid, round(random.uniform(0.80, 1.0), 2)):
                view_count += 1
            if (i + 1) % 50 == 0:
                print(f"    📌 Views: {view_count}/{VIEWS_PER_USER}")
            time.sleep(0.02)
        print(f"    ✅ {view_count} VIEW events fired (deep watches)")

        # Fire LIKE events — these are our ground truth
        liked_video_ids = set()
        like_pool = random.sample(target_pool, min(LIKES_PER_USER * 3, len(target_pool)))
        like_count = 0
        for vid in like_pool:
            if like_count >= LIKES_PER_USER:
                break
            if fire_like(token, vid):
                liked_video_ids.add(vid)
                like_count += 1
            if like_count % 50 == 0 and like_count > 0:
                print(f"    📌 Likes: {like_count}/{LIKES_PER_USER}")
            time.sleep(0.02)
        print(f"    ✅ {like_count} LIKE events fired → ground truth set ({len(liked_video_ids)} videos)")

        # Fire SKIP events on opposite category
        skip_count = 0
        if opposite_pool:
            for _ in range(SKIPS_PER_USER):
                vid = random.choice(opposite_pool)
                if fire_skip(token, vid):
                    skip_count += 1
                time.sleep(0.02)
        print(f"    ✅ {skip_count} SKIP events fired on opposite categories")

        user_results.append({
            "name":       name,
            "category":   cat,
            "token":      token,
            "liked_ids":  liked_video_ids,
            "like_count": like_count,
        })

    # ── Step 3: Wait for interest vectors ────────────────────────────────────
    print(f"\n⏳ STEP 3: Waiting 20 seconds for all interest vectors to update...")
    for i in range(20, 0, -1):
        print(f"  ... {i}s")
        time.sleep(1)
    print(f"  ✅ Done")

    # ── Step 4: Fetch feeds and calculate scores ──────────────────────────────
    print(f"\n📊 STEP 4: Fetching feeds and calculating scores...")
    print()

    all_ndcg      = []
    all_precision = []

    print(f"  {'User':<22} {'Cat':<12} {'Liked':<8} {'Hits@10':<10} {'NDCG@10':<10} Precision@10")
    print(f"  {'-' * 72}")

    for user in user_results:
        feed_ids = get_feed(user["token"])
        time.sleep(0.5)

        if not feed_ids:
            print(f"  {user['name']:<22} {user['category']:<12} — feed empty, skipping")
            continue

        ndcg_score = ndcg_at_k(feed_ids, user["liked_ids"], k=10)
        prec_score = precision_at_k(feed_ids, user["liked_ids"], k=10)
        hits       = sum(1 for vid in feed_ids[:10] if vid in user["liked_ids"])

        all_ndcg.append(ndcg_score)
        all_precision.append(prec_score)

        if ndcg_score >= 0.3:
            grade = "🟢 Strong"
        elif ndcg_score >= 0.1:
            grade = "🟡 Partial"
        else:
            grade = "🔴 Weak"

        print(f"  {user['name']:<22} {user['category']:<12} {user['like_count']:<8} "
              f"{hits:<10} {ndcg_score:<10.4f} {prec_score:.4f}  {grade}")

    # ── Step 5: Final summary ─────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print(f"  🏁 FINAL SCORES")
    print(f"{'=' * 65}")

    if all_ndcg:
        avg_ndcg = np.mean(all_ndcg)
        avg_prec = np.mean(all_precision)

        print(f"  Average NDCG@10      : {avg_ndcg:.4f}")
        print(f"  Average Precision@10 : {avg_prec:.4f}")
        print()

        if avg_ndcg >= 0.3:
            print(f"  ✅ STRONG — Model is surfacing liked content effectively!")
        elif avg_ndcg >= 0.1:
            print(f"  ⚠️  PARTIAL — Model shows some personalization signal.")
            print(f"      More training cycles will improve this score.")
        else:
            print(f"  ❌ WEAK — Model is not surfacing liked content well.")
            print(f"      Ground truth videos rarely appear in top 10 recommendations.")

        print()
        print(f"  📌 Industry reference points:")
        print(f"     NDCG@10 > 0.40  = Production-grade (Netflix/YouTube level)")
        print(f"     NDCG@10 > 0.20  = Good for early-stage system")
        print(f"     NDCG@10 > 0.10  = Model is learning, needs more data")
        print(f"     NDCG@10 < 0.05  = Essentially random recommendations")
        print(f"\n  Your score: {avg_ndcg:.4f} → ", end="")
        if avg_ndcg >= 0.4:
            print("Production-grade! 🚀")
        elif avg_ndcg >= 0.2:
            print("Good for early-stage! Keep training.")
        elif avg_ndcg >= 0.1:
            print("Learning. More events and training needed.")
        else:
            print("Needs work. Consider more training cycles.")
    else:
        print("  ❌ No scores calculated — check API connection.")

    print(f"\n{'=' * 65}\n")

if __name__ == "__main__":
    asyncio.run(main())