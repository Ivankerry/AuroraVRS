import os
import asyncpg
import asyncio

# ── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

async def main():
    print("\n🧹 AURORA-VRS: DATABASE CLEANUP (REAL VIDEOS ONLY)")
    print("═" * 60)
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return

    # 1. Count before
    total_before = await conn.fetchval("SELECT count(*) FROM videos")
    real_count = await conn.fetchval("SELECT count(*) FROM videos WHERE description LIKE 'MicroLens Import%'")
    legacy_count = total_before - real_count

    print(f"📊 Current Catalog: {total_before} videos")
    print(f"   - Real Seeded: {real_count}")
    print(f"   - Legacy/Placeholder: {legacy_count}")

    if legacy_count == 0:
        print("\n✅ Database is already clean. No action needed.")
        await conn.close()
        return

    confirm = input(f"\n⚠️ WARNING: This will DELETE {legacy_count} legacy videos and ALL their associated events. \nAre you sure you want to proceed? (yes/no): ")
    
    if confirm.lower() == 'yes':
        print("\n🚀 Starting cleanup...")
        
        # We delete from videos; associated tags/categories/events should cascade if DB schema is correct.
        # If not, we handle them explicitly.
        
        # 1. Delete events associated with legacy videos
        deleted_events = await conn.execute("""
            DELETE FROM events 
            WHERE video_id IN (SELECT id FROM videos WHERE description NOT LIKE 'MicroLens Import%')
        """)
        print(f"  🗑️ Removed associated events.")

        # 2. Delete the videos themselves
        deleted_videos = await conn.execute("""
            DELETE FROM videos 
            WHERE description NOT LIKE 'MicroLens Import%'
        """)
        print(f"  🗑️ Removed {legacy_count} legacy videos from the database.")
        
        # 3. Trigger a FAISS rebuild (since the catalog just changed)
        # In a real sync we'd call the API, but for now we suggest it.
        print("\n✅ Cleanup Complete!")
        print("💡 TIP: You should now trigger an ML Rebuild to update your FAISS index.")
    else:
        print("\n❌ Cleanup cancelled.")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
