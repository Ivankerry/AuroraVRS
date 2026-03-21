import asyncio
import json
from sqlalchemy import text
from core.db import AsyncSessionLocal
import uuid

async def fix_and_reseed():
    user_email = "music@gmail.com"
    async with AsyncSessionLocal() as db:
        # 1. Ensure 'Comedy' tag exists
        res = await db.execute(text("SELECT id FROM tags WHERE name = 'Comedy'"))
        comedy_tag = res.mappings().first()
        if not comedy_tag:
            comedy_tag_id = str(uuid.uuid4())
            await db.execute(text("INSERT INTO tags (id, name) VALUES (:id, 'Comedy')"), {"id": comedy_tag_id})
            print(f"Created 'Comedy' tag: {comedy_tag_id}")
        else:
            comedy_tag_id = comedy_tag['id']
            print(f"Found existing 'Comedy' tag: {comedy_tag_id}")

        # 2. Find videos with 'comedy' or 'hilarious' in title and tag them
        res = await db.execute(text("SELECT id FROM videos WHERE title ILIKE '%comedy%' OR title ILIKE '%hilarious%'"))
        videos = res.mappings().all()
        for v in videos:
            # Check if already tagged
            check = await db.execute(text("SELECT 1 FROM video_tags WHERE video_id = :vid AND tag_id = :tid"), {"vid": v['id'], "tid": comedy_tag_id})
            if not check.scalar():
                await db.execute(text("INSERT INTO video_tags (video_id, tag_id) VALUES (:vid, :tid)"), {"vid": v['id'], "tid": comedy_tag_id})
        print(f"Tagged {len(videos)} videos with 'Comedy'")

        # 3. Reset interest vector for music@gmail.com
        user_res = await db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": user_email})
        user = user_res.mappings().first()
        if not user:
            print("User not found!")
            return
        user_id = user['id']
        
        # Reset weights: 1 Put high weights on Music and Comedy, and wipe everything else
        # Find 'Music' tag/category IDs
        mus_res = await db.execute(text("SELECT id FROM tags WHERE name ILIKE 'Music' UNION SELECT id FROM categories WHERE name ILIKE 'Music'"))
        music_ids = [r['id'] for r in mus_res.mappings().all()]
        
        new_weights = {str(mid): 1.0 for mid in music_ids}
        new_weights[str(comedy_tag_id)] = 1.0
        
        await db.execute(text("UPDATE user_interest_vectors SET tag_weights = :w, updated_at = NOW() WHERE user_id = :uid"), 
                         {"w": json.dumps(new_weights), "uid": user_id})
        await db.commit()
        print(f"Reset and boosted interests for {user_email}: Music and Comedy are now 1.0!")

if __name__ == "__main__":
    asyncio.run(fix_and_reseed())
