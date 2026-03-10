import requests
import random
import time

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL    = "http://localhost:8080/api/v1"
ACCESS_TOKEN = input("Paste your access_token and press Enter:\n> ").strip()

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# ── Step 1: Fetch videos from the feed ───────────────────────────────────────
print("\n📡 Fetching videos from feed...")
resp = requests.get(f"{BASE_URL}/feed", headers=HEADERS)
videos = resp.json().get("videos", [])

if not videos:
    print("❌ No videos returned from feed. Make sure Docker is running.")
    exit()

video_ids = [v["id"] for v in videos]
print(f"✅ Got {len(video_ids)} videos to interact with.\n")

# ── Step 2: Fire 120 events ───────────────────────────────────────────────────
EVENT_TYPES = ["VIEW", "LIKE", "SHARE", "SKIP"]
WEIGHTS     = [0.55, 0.20, 0.10, 0.15]   # mirrors seed_clusters.py distribution

success = 0
failed  = 0

print("🔥 Firing 120 events...")
for i in range(120):
    video_id   = random.choice(video_ids)
    event_type = random.choices(EVENT_TYPES, weights=WEIGHTS, k=1)[0]

    # Watch ratio logic — positive signals watch more
    if event_type in ("VIEW", "LIKE", "SHARE"):
        watch_ratio = round(random.uniform(0.65, 1.0), 2)
    else:  # SKIP
        watch_ratio = round(random.uniform(0.0, 0.25), 2)

    payload = {
        "video_id":   video_id,
        "event_type": event_type,
        "watch_ratio": watch_ratio,
        "metadata":   {}
    }

    try:
        r = requests.post(f"{BASE_URL}/events", json=payload, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            success += 1
            print(f"  [{i+1:03d}] ✅ {event_type:<6} | watch_ratio={watch_ratio} | video={video_id[:8]}...")
        else:
            failed += 1
            print(f"  [{i+1:03d}] ❌ {event_type:<6} | status={r.status_code} | {r.text[:60]}")
    except Exception as e:
        failed += 1
        print(f"  [{i+1:03d}] ❌ Exception: {e}")

    time.sleep(0.05)  # small delay to avoid hammering the API

# ── Step 3: Summary ───────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
print(f"✅ Successful events : {success}")
print(f"❌ Failed events     : {failed}")
print(f"{'─'*50}")

if success >= 100:
    print("\n🎉 You've crossed the 100-event threshold!")
    print("   Now hit GET /api/v1/feed in Postman — the Two-Tower model should kick in.\n")
else:
    print(f"\n⚠️  Only {success} events recorded. Re-run the script to fire more.\n")