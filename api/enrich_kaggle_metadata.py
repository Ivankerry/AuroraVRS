import asyncio
import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

async def enrich_kaggle_metadata():
    print("🔌 Connecting to Database...")
    conn = await asyncpg.connect(DATABASE_URL)

    print("🔍 Fetching Kaggle categories and video mappings...")
    # Get all categories assigned to Kaggle videos
    rows = await conn.fetch("""
        SELECT DISTINCT c.id, c.name
        FROM categories c
        JOIN video_categories vc ON c.id = vc.category_id
        JOIN videos v ON vc.video_id = v.id
        WHERE v.title LIKE 'Kaggle Video%'
    """)
    
    if not rows:
        print("❌ No Kaggle videos found with categories.")
        await conn.close()
        return

    print(f"Found {len(rows)} categories to mirror as tags.")

    # 1. Create tags mirroring the categories
    tag_mapping = {} # category_id -> tag_id
    for r in rows:
        cat_id, cat_name = r['id'], r['name']
        
        # Insert tag if not exists
        tag_id = await conn.fetchval("""
            INSERT INTO tags (name)
            VALUES ($1)
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """, cat_name)
        
        tag_mapping[cat_id] = tag_id
        print(f"  Mapped Category '{cat_name}' to Tag ID {tag_id}")

    # 2. Link videos to these tags
    print("\n🔗 Linking Kaggle videos to new tags...")
    
    # We do a batch insert of video_tags based on existing video_categories
    res = await conn.execute("""
        INSERT INTO video_tags (video_id, tag_id)
        SELECT vc.video_id, t.id
        FROM video_categories vc
        JOIN categories c ON vc.category_id = c.id
        JOIN tags t ON t.name = c.name
        JOIN videos v ON vc.video_id = v.id
        WHERE v.title LIKE 'Kaggle Video%'
        ON CONFLICT DO NOTHING
    """)
    
    print(f"✅ {res} video-tag links created.")

    # 3. Final verification
    new_tag_count = await conn.fetchval("""
        SELECT COUNT(*) 
        FROM video_tags vt
        JOIN videos v ON vt.video_id = v.id
        WHERE v.title LIKE 'Kaggle Video%'
    """)
    print(f"\n📊 Verification: Kaggle videos now have {new_tag_count} total tag assignments.")
    
    await conn.close()
    print("\n✨ Enrichment Complete!")

if __name__ == "__main__":
    asyncio.run(enrich_kaggle_metadata())
