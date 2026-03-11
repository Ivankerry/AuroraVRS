import requests
import random
import time
import os
import argparse
import asyncio
import asyncpg
from concurrent.futures import ThreadPoolExecutor

# ── Config ────────────────────────────────────────────────────────────────────
API_URL = os.getenv("API_URL", "http://62.84.176.140:8080/api/v1")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

# Personas define the interest distribution for "Bot" users
PERSONAS = {
    "Tech Elite":     ["Tech"],
    "Gamer Pro":      ["Gaming"],
    "Cinephile":      ["Drama", "Sci-Fi"],
    "Educationist":   ["Education"],
    "Music Lover":    ["Music"],
    "Joker":          ["Comedy"],
    "Fantasy Nerd":   ["Fantasy"],
    "Tech/Gamer":     ["Tech", "Gaming"],
    "Music/Comedy":   ["Music", "Comedy"],
    "Sci-Fi/Tech":    ["Sci-Fi", "Tech"],
    "Drama/Comedy":   ["Drama", "Comedy"],
    "Gaming/Edu":     ["Gaming", "Education"],
    "Omnivore":       ["Tech", "Gaming", "Music", "Comedy", "Education", "Sci-Fi", "Drama"]
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def register_or_login(email):
    try:
        # Try to register
        r = requests.post(f"{API_URL}/auth/register", json={
            "email": email,
            "password": "bot_password_123!",
            "full_name": "Bot User"
        }, timeout=10)
        
        # If already exists, login
        if r.status_code != 201:
            r = requests.post(f"{API_URL}/auth/login", data={
                "username": email,
                "password": "bot_password_123!"
            }, timeout=10)
        
        if r.status_code in (200, 201):
            return r.json().get("access_token")
        else:
            print(f"  ❌ Failed to auth {email}: {r.status_code} - {r.text[:50]}")
    except Exception as e:
        print(f"  ❌ Connection error for {email}: {e}")
    
    return None

def fire_interaction(token, video_id, event_type, watch_ratio=1.0):
    try:
        requests.post(
            f"{API_URL}/events",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "video_id": video_id,
                "event_type": event_type,
                "watch_ratio": watch_ratio
            },
            timeout=5
        )
    except: pass

async def load_video_pools(conn):
    print("📋 Fetching video pools from database...")
    pools = {}
    all_cats = set()
    for p in PERSONAS.values():
        for c in p: all_cats.add(c)
    
    for cat in all_cats:
        rows = await conn.fetch("""
            SELECT v.id FROM videos v
            JOIN video_categories vc ON v.id = vc.video_id
            JOIN categories c ON vc.category_id = c.id
            WHERE c.name = $1 AND v.privacy = 'PUBLIC' AND v.status = 'READY'
        """, cat)
        pools[cat] = [str(r['id']) for r in rows]
        print(f"  📦 Pool [{cat:<10}]: {len(pools[cat])} videos")
    
    return pools

# ── Main Loop ─────────────────────────────────────────────────────────────────
async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=1000, help="Number of events to generate")
    parser.add_argument("--bots", type=int, default=50, help="Number of bot users")
    args = parser.parse_args()

    print(f"\n🚀 AURORA-VRS INTERACTION SIMULATOR (DIVERSE PERSONAS)")
    print(f"📡 Target API: {API_URL}")
    print(f"📦 Goal: {args.events} events across {args.bots} bots\n")

    conn = await asyncpg.connect(DATABASE_URL)
    cat_pools = await load_video_pools(conn)
    await conn.close()

    if not any(cat_pools.values()):
        print("❌ Error: Video pools are empty. Run amazon_enricher.py first!")
        return

    # 1. Setup Bots
    bots = []
    print(f"🤖 Initializing {args.bots} user personas...")
    for i in range(args.bots):
        persona_name = random.choice(list(PERSONAS.keys()))
        # Use a stable bot index so we don't create 1000s of users every time
        bot_idx = i % args.bots 
        email = f"stable_bot_{bot_idx}@aurora-vrs.internal"
        token = register_or_login(email)
        if token:
            bots.append({
                "token": token, 
                "email": email, 
                "persona": persona_name,
                "interests": PERSONAS[persona_name]
            })

    if not bots:
        print("\n❌ CRITICAL: No bots were successfully initialized.")
        print("   If running inside Docker, ensure API_URL is http://api:8000/api/v1")
        return

    print(f"  ✅ {len(bots)} bots ready for action.")

    # 2. Fire Events
    print(f"🔥 Generating {args.events} signals...")
    events_fired = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=10) as executor:
        while events_fired < args.events:
            bot = random.choice(bots)
            
            # Pick a video from one of the bot's interest pools
            target_cat = random.choice(bot["interests"])
            pool = cat_pools.get(target_cat, [])
            if not pool:
                continue
                
            video_id = random.choice(pool)
            
            # Realistic event weighting
            event_type = random.choices(
                ["VIEW", "LIKE", "SHARE", "SKIP", "DISLIKE"],
                weights=[60, 20, 5, 10, 5],
                k=1
            )[0]
            
            watch_ratio = random.uniform(0.6, 1.0) if event_type in ["VIEW", "LIKE", "SHARE"] else random.uniform(0.0, 0.3)
            
            executor.submit(fire_interaction, bot["token"], video_id, event_type, watch_ratio)
            events_fired += 1
            
            if events_fired % 100 == 0:
                elapsed = time.time() - start_time
                rate = events_fired / (elapsed + 0.1)
                print(f"  ✅ {events_fired}/{args.events} events fired ({rate:.1f} ev/s)")

    print(f"\n✨ FINISHED: Generated {events_fired} interactions in {time.time()-start_time:.1f}s.")
    print(f"💡 Run 'docker compose logs -f worker' to see the model retraining.")

if __name__ == "__main__":
    asyncio.run(main())
