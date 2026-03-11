import asyncio
import os
import json
import random
import uuid
import asyncpg
import requests
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

# Sample Data (Fallback so script works immediately)
SAMPLE_MOVIES = [
    {"title": "The Matrix Revolutions", "cats": ["Tech", "Sci-Fi"], "desc": "Neo and the rebel leaders estimate that they have very little time before 250,000 Sentinels destroy Zion."},
    {"title": "Interstellar", "cats": ["Tech", "Sci-Fi", "Drama"], "desc": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival."},
    {"title": "Whiplash", "cats": ["Music", "Drama"], "desc": "A promising young drummer enrolls at a cut-throat music conservatory where his dreams of greatness are mentored by an instructor who will stop at nothing."},
    {"title": "The Social Network", "cats": ["Tech", "Comedy"], "desc": "As Harvard student Mark Zuckerberg creates the social networking site that would become Facebook, he is sued by the twins who claimed he stole their idea."},
    {"title": "Cyberpunk: Edgerunners", "cats": ["Gaming", "Sci-Fi", "Tech"], "desc": "In a dystopia riddled with corruption and cybernetic implants, a talented but reckless street kid strives to become a mercenary outlaw."},
    {"title": "The Witcher", "cats": ["Gaming", "Fantasy"], "desc": "Geralt of Rivia, a solitary monster hunter, struggles to find his place in a world where people often prove more wicked than beasts."},
    {"name": "Elda Gaming Rig", "cats": ["Gaming", "Tech"], "desc": "High performance PC build and benchmark test for the latest AAA titles."},
]

async def enrich_from_amazon(jsonl_path=None):
    print("\n" + "═" * 80)
    print("       🚀 AURORA-VRS AMAZON METADATA ENRICHER")
    print("═" * 80)
    
    conn = await asyncpg.connect(DATABASE_URL)

    # 1. Ensure categories exist (Especially 'Gaming')
    categories = list(set([c for m in SAMPLE_MOVIES for c in m.get("cats", [])]))
    print(f"📦 Syncing categories: {', '.join(categories)}")
    
    for cat in categories:
        await conn.execute("""
            INSERT INTO categories (id, name, description)
            VALUES ($1, $2, $3)
            ON CONFLICT (name) DO NOTHING
        """, uuid.uuid4(), cat, f"Amazon-sourced {cat} content")

    # 2. Add Anchor Videos
    print(f"\n🎥 Injecting Semantic Anchor Videos...")
    
    # If user provided a file, we could parse it here. For now, use SAMPLE_MOVIES.
    # We create a mix of real titles to give the model a vocabulary.
    
    count = 0
    now = datetime.utcnow()
    
    for movie in SAMPLE_MOVIES:
        v_id = uuid.uuid4()
        title = movie.get("title") or movie.get("name")
        desc = movie.get("desc")
        cats = movie.get("cats", [])
        
        # Insert video
        await conn.execute("""
            INSERT INTO videos (id, title, description, privacy, status, created_at, view_count, like_count, duration_sec)
            VALUES ($1, $2, $3, 'PUBLIC', 'READY', $4, $5, $6, $7)
        """, v_id, title, desc, now, random.randint(100, 1000), random.randint(10, 50), random.randint(30, 180))
        
        # Link to categories
        for cat_name in cats:
            cat_id = await conn.fetchval("SELECT id FROM categories WHERE name = $1", cat_name)
            if cat_id:
                await conn.execute("""
                    INSERT INTO video_categories (video_id, category_id)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                """, v_id, cat_id)
        
        print(f"  ✅ Added: {title[:30]}...")
        count += 1

    await conn.close()
    print(f"\n🚀 Injected {count} anchor videos.")
    print("═" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(enrich_from_amazon())
