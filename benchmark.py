import requests
import random
import time
import asyncio
import asyncpg
from collections import Counter

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL     = "http://localhost:8080/api/v1"
DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
EVENTS_COUNT = 100

USER_A_CATEGORY = "Tech"
USER_B_CATEGORY = "Music"

# ── Helpers ───────────────────────────────────────────────────────────────────
def register(email, name):
    print(f"    → Registering {name}...")
    r = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": "benchmark123", "names": name
    })
    if r.status_code == 200:
        print(f"    ✅ Registered successfully")
        return r.json()["access_token"]
    print(f"    ℹ️  Already exists, logging in...")
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email, "password": "benchmark123"
    })
    print(f"    ✅ Logged in successfully")
    return r.json()["access_token"]

def headers(token):
    return {"Authorization": f"Bearer {token}"}

def fire_events(token, liked_ids, disliked_ids, label, count=EVENTS_COUNT):
    print(f"\n  🔥 Firing {count} events for {label}...")
    print(f"     → Positive signals on {len(liked_ids)} target videos")
    print(f"     → Negative signals (SKIPs) on {len(disliked_ids)} opposite videos")

    success = 0
    failed  = 0
    likes   = 0
    skips   = 0

    for i in range(count):
        if random.random() < 0.75:
            video_id    = random.choice(liked_ids)
            watch_ratio = round(random.uniform(0.80, 1.0), 2)
            event_type  = "VIEW"
        else:
            video_id    = random.choice(disliked_ids)
            watch_ratio = round(random.uniform(0.0, 0.15), 2)
            event_type  = "SKIP"
            skips += 1

        try:
            r = requests.post(f"{BASE_URL}/events", json={
                "video_id":    video_id,
                "event_type":  event_type,
                "watch_ratio": watch_ratio,
                "metadata":    {}
            }, headers=headers(token), timeout=5)
            if r.status_code == 200:
                success += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"    ❌ Event {i+1} exception: {e}")

        if event_type == "VIEW" and i % 3 == 0:
            try:
                r = requests.post(f"{BASE_URL}/videos/{video_id}/like",
                                  headers=headers(token), timeout=5)
                if r.status_code == 200:
                    likes += 1
            except:
                pass

        if (i + 1) % 50 == 0:
            print(f"    📌 [{i+1}/{count}] — "
                  f"{success} views, {likes} likes, {skips} skips fired "
                  f"({failed} failed)")

        time.sleep(0.02)

    print(f"  ✅ Done — {success} events total "
          f"({likes} likes, {skips} skips, {failed} failed)")

def get_feed(token, label):
    print(f"  📡 Fetching feed for {label}...")
    try:
        r = requests.get(f"{BASE_URL}/feed", headers=headers(token), timeout=10)
        videos = r.json().get("videos", [])
        print(f"  ✅ Got {len(videos)} videos in feed")
        return videos
    except Exception as e:
        print(f"  ❌ Failed to fetch feed: {e}")
        return []

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    print("\n" + "=" * 60)
    print("       🧪 AURORA-VRS TWO-TOWER BENCHMARK v3")
    print(f"       Tech vs Music Edition")
    print("=" * 60)
    print("  Strategy:")
    print(f"  • {EVENTS_COUNT} events per user")
    print(f"  • User A trained on {USER_A_CATEGORY}")
    print(f"  • User B trained on {USER_B_CATEGORY}")
    print("  • 75% deep watches on TARGET category")
    print("  • 25% SKIPs on OPPOSITE category")
    print("  • Likes fired every 3rd positive event")
    print("=" * 60)

    # ── Step 1: Fetch video IDs ───────────────────────────────────────────────
    print(f"\n📦 STEP 1: Fetching videos from database...")
    conn = await asyncpg.connect(DATABASE_URL)

    tech_ids = [str(r['id']) for r in await conn.fetch("""
        SELECT v.id FROM videos v
        JOIN video_categories vc ON v.id = vc.video_id
        JOIN categories c ON vc.category_id = c.id
        WHERE c.name = 'Tech' AND v.privacy = 'PUBLIC' AND v.status = 'READY'
        LIMIT 100
    """)]

    music_ids = [str(r['id']) for r in await conn.fetch("""
        SELECT v.id FROM videos v
        JOIN video_categories vc ON v.id = vc.video_id
        JOIN categories c ON vc.category_id = c.id
        WHERE c.name = 'Music' AND v.privacy = 'PUBLIC' AND v.status = 'READY'
        LIMIT 100
    """)]

    await conn.close()

    print(f"  ✅ Tech  videos available : {len(tech_ids)}")
    print(f"  ✅ Music videos available : {len(music_ids)}")

    if len(tech_ids) < 10 or len(music_ids) < 10:
        print("  ❌ Not enough videos found. Check your database.")
        return

    # ── Step 2: Register users ────────────────────────────────────────────────
    print(f"\n👤 STEP 2: Creating benchmark users...")
    timestamp = int(time.time())
    token_a = register(f"bench_tech_{timestamp}@test.com", "Benchmark Tech User")
    token_b = register(f"bench_music_{timestamp}@test.com", "Benchmark Music User")
    print(f"  ✅ Both users ready")

    # ── Step 3: Fire events ───────────────────────────────────────────────────
    print(f"\n💻 STEP 3: Training User A...")
    print(f"  Target: TECH ✅  |  Avoid: MUSIC ❌")
    fire_events(token_a, tech_ids, music_ids, "User A (Tech fan)")

    print(f"\n🎵 STEP 4: Training User B...")
    print(f"  Target: MUSIC ✅  |  Avoid: TECH ❌")
    fire_events(token_b, music_ids, tech_ids, "User B (Music fan)")

    # ── Step 4: Wait ──────────────────────────────────────────────────────────
    print(f"\n⏳ STEP 5: Waiting for Redis interest vectors to update...")
    for i in range(15, 0, -1):
        print(f"  ... {i}s")
        time.sleep(1)
    print(f"  ✅ Done waiting")

    # ── Step 5: Fetch feeds ───────────────────────────────────────────────────
    print(f"\n📡 STEP 6: Fetching personalized feeds...")
    feed_a = get_feed(token_a, "User A (Tech fan)")
    feed_b = get_feed(token_b, "User B (Music fan)")

    # ── Step 6: Look up categories ────────────────────────────────────────────
    print(f"\n🔍 STEP 7: Resolving video categories from database...")
    conn = await asyncpg.connect(DATABASE_URL)

    async def get_categories_for_feed(feed):
        if not feed:
            return []
        ids = [v["id"] for v in feed]
        placeholders = ", ".join(f"${i+1}" for i in range(len(ids)))
        rows = await conn.fetch(f"""
            SELECT v.id, c.name as category FROM videos v
            JOIN video_categories vc ON v.id = vc.video_id
            JOIN categories c ON vc.category_id = c.id
            WHERE v.id IN ({placeholders})
        """, *ids)
        return [r["category"] for r in rows]

    cats_a = await get_categories_for_feed(feed_a)
    cats_b = await get_categories_for_feed(feed_b)
    await conn.close()

    print(f"  ✅ User A categories resolved: {len(cats_a)} entries")
    print(f"  ✅ User B categories resolved: {len(cats_b)} entries")

    # ── Step 7: Results ───────────────────────────────────────────────────────
    count_a = Counter(cats_a)
    count_b = Counter(cats_b)

    print(f"\n{'=' * 60}")
    print(f"  📊 STEP 8: RESULTS")
    print(f"{'=' * 60}")

    print(f"\n  💻 USER A — Trained on TECH — Feed Breakdown:")
    print(f"  {'Category':<14} {'Bar':<30} Count")
    print(f"  {'-' * 54}")
    for cat, count in count_a.most_common():
        bar    = "█" * count
        marker = " ← 🎯 TARGET" if cat == "Tech"  else \
                 " ← ❌ AVOID"  if cat == "Music" else ""
        print(f"  {cat:<14} {bar:<30} ({count}){marker}")

    print(f"\n  🎵 USER B — Trained on MUSIC — Feed Breakdown:")
    print(f"  {'Category':<14} {'Bar':<30} Count")
    print(f"  {'-' * 54}")
    for cat, count in count_b.most_common():
        bar    = "█" * count
        marker = " ← 🎯 TARGET" if cat == "Music" else \
                 " ← ❌ AVOID"  if cat == "Tech"  else ""
        print(f"  {cat:<14} {bar:<30} ({count}){marker}")

    # ── Step 8: Verdict ───────────────────────────────────────────────────────
    tech_in_a  = count_a.get("Tech", 0)
    music_in_b = count_b.get("Music", 0)
    music_in_a = count_a.get("Music", 0)
    tech_in_b  = count_b.get("Tech", 0)
    total_a    = sum(count_a.values()) or 1
    total_b    = sum(count_b.values()) or 1
    tech_pct   = (tech_in_a  / total_a) * 100
    music_pct  = (music_in_b / total_b) * 100
    avoid_a    = (music_in_a / total_a) * 100
    avoid_b    = (tech_in_b  / total_b) * 100
    overlap    = len(set(v["id"] for v in feed_a) & set(v["id"] for v in feed_b))
    overlap_pct = (overlap / max(len(feed_a), 1)) * 100

    print(f"\n{'=' * 60}")
    print(f"  🏁 FINAL VERDICT")
    print(f"{'=' * 60}")
    print(f"  User A — Tech  (target) in feed : {tech_in_a}/{total_a} ({tech_pct:.1f}%)")
    print(f"  User A — Music (avoid)  in feed : {music_in_a}/{total_a} ({avoid_a:.1f}%)")
    print(f"  User B — Music (target) in feed : {music_in_b}/{total_b} ({music_pct:.1f}%)")
    print(f"  User B — Tech  (avoid)  in feed : {tech_in_b}/{total_b} ({avoid_b:.1f}%)")
    print(f"  Overlapping videos between feeds : {overlap} ({overlap_pct:.1f}%)")

    print()
    if tech_pct >= 40 and music_pct >= 40:
        print(f"  ✅ PASSED — Model is strongly personalized!")
        print(f"     Users with opposite tastes are getting very different feeds.")
    elif tech_pct >= 25 or music_pct >= 25:
        print(f"  ⚠️  PARTIAL — Some personalization detected.")
        print(f"     The model is working but could use more training cycles.")
    else:
        print(f"  ❌ FAILED — Feeds are too similar.")
        print(f"     The model needs more training or a threshold adjustment.")

    if overlap_pct < 25:
        print(f"  ✅ Feed diversity is strong — only {overlap_pct:.1f}% overlap.")
    elif overlap_pct < 50:
        print(f"  ⚠️  Moderate overlap ({overlap_pct:.1f}%) — improving but not there yet.")
    else:
        print(f"  ❌ High overlap ({overlap_pct:.1f}%) — feeds are too similar.")

    print(f"\n{'=' * 60}\n")

if __name__ == "__main__":
    asyncio.run(main())