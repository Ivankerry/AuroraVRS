import asyncio
import asyncpg
import time

DATABASE_URL = "postgresql://user:pass@localhost:5432/db"

async def recalculate_stats():
    print("🔌 Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)

    total = await conn.fetchval("SELECT count(*) FROM videos")
    print(f"📊 Found {total:,} videos to recalculate.\n")

    start_time = time.time()

    print("⚡ Step 1/3: Aggregating view counts...")
    print("  (this may take 1-2 minutes, please wait...)")
    await conn.execute("""
        UPDATE videos SET view_count = agg.cnt
        FROM (
            SELECT video_id, count(*) AS cnt
            FROM events WHERE event_type = 'VIEW'
            GROUP BY video_id
        ) AS agg
        WHERE videos.id = agg.video_id
    """)
    print("  ✅ View counts updated!")

    print("\n⚡ Step 2/3: Aggregating like counts...")
    await conn.execute("""
        UPDATE videos SET like_count = agg.cnt
        FROM (
            SELECT video_id, count(*) AS cnt
            FROM events WHERE event_type = 'LIKE'
            GROUP BY video_id
        ) AS agg
        WHERE videos.id = agg.video_id
    """)
    print("  ✅ Like counts updated!")

    print("\n⚡ Step 3/3: Zeroing out videos with no events...")
    await conn.execute("""
        UPDATE videos SET view_count = 0
        WHERE id NOT IN (
            SELECT DISTINCT video_id FROM events WHERE event_type = 'VIEW'
        )
    """)
    await conn.execute("""
        UPDATE videos SET like_count = 0
        WHERE id NOT IN (
            SELECT DISTINCT video_id FROM events WHERE event_type = 'LIKE'
        )
    """)
    print("  ✅ Done!")

    total_time = time.time() - start_time
    print(f"\n🎉 All {total:,} video stats are now accurate.")
    print(f"⏱️  Total time: {int(total_time // 60)}m {int(total_time % 60)}s")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(recalculate_stats())