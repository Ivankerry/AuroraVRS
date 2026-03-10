import requests
import random
import time
import asyncio
import asyncpg

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL     = "http://localhost:8080/api/v1"
DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
MY_TOKEN     = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI5ZDkzYmY4OC1jMjhiLTRlOTgtYjIxNS1iZTA2ZGEzYzk5OWIiLCJyb2xlIjoiVVNFUiIsImV4cCI6MTc3MzA2ODgzNX0.vxiJM-GVwJpNZIboXvvmNBpvBKEvu-YsZwUpKJ3OSs8"

MY_INTERESTS  = ["Tech", "Gaming", "Education"]
AVOID_CATS    = ["Music", "Comedy"]
VIEWS_TO_FIRE = 120
LIKES_TO_FIRE = 40

# ── Helpers ───────────────────────────────────────────────────────────────────
def headers():
    return {"Authorization": f"Bearer {MY_TOKEN}"}

def fire_view(video_id, watch_ratio):
    try:
        r = requests.post(f"{BASE_URL}/events", json={
            "video_id":    video_id,
            "event_type":  "VIEW",
            "watch_ratio": watch_ratio,
            "metadata":    {}
        }, headers=headers(), timeout=5)
        return r.status_code == 200
    except:
        return False

def fire_like(video_id):
    try:
        r = requests.post(f"{BASE_URL}/videos/{video_id}/like",
                          headers=headers(), timeout=5)
        return r.status_code == 200
    except:
        return False

def fire_skip(video_id):
    try:
        r = requests.post(f"{BASE_URL}/events", json={
            "video_id":    video_id,
            "event_type":  "SKIP",
            "watch_ratio": round(random.uniform(0.0, 0.1), 2),
            "metadata":    {}
        }, headers=headers(), timeout=5)
        return r.status_code == 200
    except:
        return False

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    print("\n" + "=" * 55)
    print("   🎯 AURORA-VRS — Personalizing YOUR feed")
    print("=" * 55)
    print(f"  Interests : {', '.join(MY_INTERESTS)}")
    print(f"  Avoid     : {', '.join(AVOID_CATS)}")
    print(f"  Views     : {VIEWS_TO_FIRE}")
    print(f"  Likes     : {LIKES_TO_FIRE}")
    print("=" * 55)

    # ── Fetch video pools ─────────────────────────────────────────────────────
    print(f"\n📦 Loading videos from database...")
    conn = await asyncpg.connect(DATABASE_URL)

    target_ids = []
    for cat in MY_INTERESTS:
        ids = [str(r['id']) for r in await conn.fetch("""
            SELECT v.id FROM videos v
            JOIN video_categories vc ON v.id = vc.video_id
            JOIN categories c ON vc.category_id = c.id
            WHERE c.name = $1
              AND v.privacy = 'PUBLIC'
              AND v.status = 'READY'
              AND v.description != 'Imported from Kaggle ML Dataset'
            LIMIT 200
        """, cat)]
        target_ids.extend(ids)
        print(f"  ✅ {cat:<12} : {len(ids)} videos")

    avoid_ids = []
    for cat in AVOID_CATS:
        ids = [str(r['id']) for r in await conn.fetch("""
            SELECT v.id FROM videos v
            JOIN video_categories vc ON v.id = vc.video_id
            JOIN categories c ON vc.category_id = c.id
            WHERE c.name = $1
              AND v.privacy = 'PUBLIC'
              AND v.status = 'READY'
              AND v.description != 'Imported from Kaggle ML Dataset'
            LIMIT 100
        """, cat)]
        avoid_ids.extend(ids)

    await conn.close()

    if len(target_ids) < 10:
        print("  ❌ Not enough target videos found. Check your database.")
        return

    print(f"\n  Total target pool : {len(target_ids)} videos")
    print(f"  Total avoid pool  : {len(avoid_ids)} videos")

    # ── Fire deep watch VIEW events ───────────────────────────────────────────
    print(f"\n🔥 Firing {VIEWS_TO_FIRE} deep watch events on your interests...")
    view_count = 0
    for i in range(VIEWS_TO_FIRE):
        vid = random.choice(target_ids)
        if fire_view(vid, round(random.uniform(0.80, 1.0), 2)):
            view_count += 1
        if (i + 1) % 25 == 0:
            print(f"  📌 {view_count}/{VIEWS_TO_FIRE} views fired...")
        time.sleep(0.02)
    print(f"  ✅ {view_count} VIEW events fired")

    # ── Fire LIKE events ──────────────────────────────────────────────────────
    print(f"\n❤️  Firing {LIKES_TO_FIRE} likes on your interest videos...")
    like_pool  = random.sample(target_ids, min(LIKES_TO_FIRE * 2, len(target_ids)))
    like_count = 0
    for vid in like_pool:
        if like_count >= LIKES_TO_FIRE:
            break
        if fire_like(vid):
            like_count += 1
        time.sleep(0.02)
    print(f"  ✅ {like_count} LIKE events fired")

    # ── Fire SKIP events on avoided categories ────────────────────────────────
    if avoid_ids:
        print(f"\n⏭️  Firing 20 skips on avoided categories...")
        skip_count = 0
        for _ in range(20):
            vid = random.choice(avoid_ids)
            if fire_skip(vid):
                skip_count += 1
            time.sleep(0.02)
        print(f"  ✅ {skip_count} SKIP events fired")

    # ── Wait and remind ───────────────────────────────────────────────────────
    print(f"\n⏳ Waiting 15 seconds for interest vector to update...")
    for i in range(15, 0, -1):
        print(f"  ... {i}s")
        time.sleep(1)

    print(f"\n{'=' * 55}")
    print(f"  ✅ Done! Your feed is now personalized.")
    print(f"  Go fetch your feed in Postman:")
    print(f"  GET {BASE_URL}/feed")
    print(f"  Authorization: Bearer <your token>")
    print(f"{'=' * 55}\n")

if __name__ == "__main__":
    asyncio.run(main())