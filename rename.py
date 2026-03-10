import asyncio
import asyncpg

DATABASE_URL = "postgresql://user:pass@localhost:5432/db"

# Map each tag ID to a real descriptive name
TAG_RENAMES = {
    "9571e344-4465-4374-9b04-07441d3b8145": "tutorial",
    "51144afd-3618-4eb8-bd1e-71f7d8da253f": "gameplay",
    "101a953c-bb81-45aa-abc3-9834312dcfd0": "review",
    "fe471775-ee11-4fe7-8d1e-a56769c16704": "highlights",
    "bafb8a9d-335b-4006-b92d-60ab628a7782": "tips-and-tricks",
    "b2b43e59-b168-41a6-8d52-82b19969ad7e": "beginner-guide",
    "b3bbe1e2-1e39-4eb6-9ea9-3ec072a0230e": "live-stream",
    "84ce1cff-c191-45b0-bd87-788474a4d96c": "reaction",
    "cfa3106a-e20c-4268-8db8-9e59e45074f4": "coding",
    "777e786e-8b10-4c0f-915c-dc44f578779f": "unboxing",
    "13b992df-7bab-49fa-b5b4-ea4458fc3266": "short-film",
    "bb34d8f4-d4f4-4514-9162-33b8d05e5fb8": "explained",
    "b9312ebe-da57-43cb-a0b3-7b12eb092688": "vlog",
    "075c214b-d469-4842-b1af-8a295fd1a9d7": "music-video",
    "dc811c77-cb22-4e16-a964-e3512f5c6af1": "how-to",
    "9ba97873-3e11-4eda-a3c6-f7f9c6db0e4d": "challenge",
    "6f52e6f8-447d-40a7-bf38-681790f62e8f": "behind-the-scenes",
    "0b149c5d-d673-4dc6-9584-b90ec908f73b": "study-with-me",
    "4fcf1c76-b2eb-48ab-a37c-86ea592c3a25": "python",
    "cfac4bfb-aa5d-4368-bef9-1d5d3860f7c8": "comedy-skit",
    "31247bc0-119a-4d5f-b0fb-101e0c40ed38": "fps-game",
    "13cf6ef1-682b-42e1-a272-3403a3e7f27a": "productivity",
    "9ab9a099-fd03-479e-be06-17bb2d0ea13d": "trending",
    "7f90a773-6cc0-42d6-922a-213af4874585": "open-world",
    "10d9791c-ab82-431f-abec-d208c3df0e22": "science",
    "678a00d4-8758-42e6-9856-52bd9b953cf3": "cover-song",
    "383a0cc0-ae62-4fb3-9008-c07472c91408": "esports",
    "86e503c1-bd30-405a-bc81-4200dcfac28b": "javascript",
    "d0f7b4c4-1279-407b-9e74-521e51f08a6f": "news-update",
    "9ba97873-3e11-4eda-a3c6-f7f9c6db0e4d": "challenge",
}

async def main():
    print("\n" + "=" * 50)
    print("   🏷️  AURORA-VRS Tag Rename Migration")
    print("=" * 50)

    conn = await asyncpg.connect(DATABASE_URL)

    # First show current state
    rows = await conn.fetch("SELECT id, name FROM tags ORDER BY name")
    print(f"\n  Found {len(rows)} tags in database")

    # Apply renames
    success = 0
    skipped = 0
    for row in rows:
        tag_id   = str(row['id'])
        old_name = row['name']
        new_name = TAG_RENAMES.get(tag_id)

        if new_name and old_name != new_name:
            await conn.execute(
                "UPDATE tags SET name = $1 WHERE id = $2",
                new_name, row['id']
            )
            print(f"  ✅ {old_name:<8} → {new_name}")
            success += 1
        else:
            print(f"  ⏭️  {old_name:<8} → no mapping found, skipping")
            skipped += 1

    await conn.close()

    print(f"\n{'=' * 50}")
    print(f"  Done! {success} tags renamed, {skipped} skipped")
    print(f"  Restart API to clear any cached tag data:")
    print(f"  docker compose restart api")
    print(f"{'=' * 50}\n")

if __name__ == "__main__":
    asyncio.run(main())