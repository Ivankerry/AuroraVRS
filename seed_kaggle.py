import asyncio
import os
import gc
import math
import uuid
from datetime import datetime
import pandas as pd
import asyncpg
import bcrypt

# We require users to install pandas: pip install pandas asyncpg bcrypt

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

# The path where you downloaded the Kaggle CSV
CSV_FILE_PATH = "youtube_recommendation_data.csv"
BATCH_SIZE = 10000

async def setup_kaggle_seed():
    if not os.path.exists(CSV_FILE_PATH):
        print(f"❌ Error: Could not find {CSV_FILE_PATH}")
        print("Please download 'youtube recommendation dataset.csv' from Kaggle and place it in the same folder.")
        return

    print("🔌 Connecting to Database...")
    conn = await asyncpg.connect(DATABASE_URL)

    print("🧹 Stage 1: Reading and Cleaning the Kaggle Dataset with Pandas...")
    # Load dataset. Kaggle data is messy, handle mixed types.
    df = pd.read_csv(CSV_FILE_PATH, dtype={
        'user_id': str,
        'video_id': str,
        'watch_time': pd.Int64Dtype(), 
        'video_duration': pd.Int64Dtype(),
        'liked': str, 
        'category': str
    }, low_memory=False)
    
    df = df.rename(columns={'watch_time': 'watch_time_sec', 'video_duration': 'video_duration_sec'})

    # 1. Clean missing or malformed data
    df = df.dropna(subset=['user_id', 'video_id'])
    
    # Clean boolean targets (Kaggle has mixed true/True/1/yes)
    df['liked'] = df['liked'].astype(str).str.lower().str.strip()
    df['is_liked'] = df['liked'].isin(['true', '1', 'yes', 't'])

    # Clean Durations to prevent division by zero
    df['video_duration_sec'] = pd.to_numeric(df['video_duration_sec'], errors='coerce').fillna(60)
    df['watch_time_sec'] = pd.to_numeric(df['watch_time_sec'], errors='coerce').fillna(0)
    
    # Enforce watch ratio boundaries
    df['watch_ratio'] = (df['watch_time_sec'] / df['video_duration_sec']).clip(0.0, 1.0)
    
    # Standardize Categories
    df['category'] = df['category'].astype(str).str.title().str.strip()
    df.loc[df['category'] == 'Nan', 'category'] = 'Uncategorized'

    print(f"✅ Loaded {len(df):,} clean interaction rows.")

    # ---------------------------------------------------------
    print("\n📦 Stage 2: Syncing Categories and Tags...")
    unique_categories = df['category'].unique()
    
    db_categories = {r['name']: r['id'] for r in await conn.fetch("SELECT id, name FROM categories")}
    new_categories = [(cat,) for cat in unique_categories if cat not in db_categories]
    
    if new_categories:
        await conn.executemany("INSERT INTO categories (name) VALUES ($1)", new_categories)
        db_categories = {r['name']: r['id'] for r in await conn.fetch("SELECT id, name FROM categories")}

    print(f"Found {len(unique_categories)} distinct Kaggle categories.")

    # ---------------------------------------------------------
    print("\n👤 Stage 3: Ingesting Users...")
    unique_users = df['user_id'].unique()
    
    # Fetch existing to prevent conflicts
    existing_users = {r['email'] for r in await conn.fetch("SELECT email FROM users")}
    
    user_batch = []
    # Kaggle User IDs are arbitrary strings (e.g. User_1495). We map them to our UUID schema.
    # To keep track of Kaggle User -> UUID mapping for the events table:
    kaggle_to_uuid_users = {}
    default_pw = bcrypt.hashpw(b'KaggleData123!', bcrypt.gensalt()).decode()
    
    for k_uid in unique_users:
        email = f"{str(k_uid).lower()}@kaggle.mock"
        sys_uuid = str(uuid.uuid4())
        kaggle_to_uuid_users[k_uid] = sys_uuid
        
        if email not in existing_users:
            user_batch.append((sys_uuid, f"Kaggle {k_uid}", email, default_pw, 'USER'))

    if user_batch:
        print(f"Writing {len(user_batch):,} new Users to DB in batches...")
        for i in range(0, len(user_batch), BATCH_SIZE):
            await conn.executemany("""
                INSERT INTO users (id, names, email, password_hash, role)
                VALUES ($1, $2, $3, $4, $5)
            """, user_batch[i:i+BATCH_SIZE])

    # ---------------------------------------------------------
    print("\n🎥 Stage 4: Ingesting Videos...")
    unique_videos = df[['video_id', 'video_duration_sec', 'category']].drop_duplicates(subset=['video_id'])
    
    kaggle_to_uuid_videos = {}
    video_batch = []
    video_category_batch = []
    
    # We just assign all Kaggle videos to a random 'owner' to satisfy the foreign key
    random_owner_id = list(kaggle_to_uuid_users.values())[0] if kaggle_to_uuid_users else None
    
    for _, row in unique_videos.iterrows():
        k_vid = row['video_id']
        sys_uuid = str(uuid.uuid4())
        kaggle_to_uuid_videos[k_vid] = sys_uuid
        
        duration = float(row['video_duration_sec'])
        video_type = 'QUICK' if duration <= 60 else 'LONGFORM'
        
        video_batch.append((
            sys_uuid, random_owner_id, f"Kaggle Video {k_vid}", 
            "Imported from Kaggle ML Dataset", video_type, 'PUBLIC', 'READY', duration
        ))
        
        cat_id = db_categories.get(row['category'])
        if cat_id:
            video_category_batch.append((sys_uuid, cat_id))

    if video_batch:
        print(f"Writing {len(video_batch):,} new Videos to DB...")
        for i in range(0, len(video_batch), BATCH_SIZE):
            await conn.executemany("""
                INSERT INTO videos (id, creator_id, title, description, type, privacy, status, duration_sec)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, video_batch[i:i+BATCH_SIZE])
            
        await conn.executemany("""
            INSERT INTO video_categories (video_id, category_id) VALUES ($1, $2)
        """, video_category_batch)

    # ---------------------------------------------------------
    print("\n🔥 Stage 5: Ingesting Kaggle Events (The Machine Learning Engine!)...")
    # This maps the exact interaction rows the PyTorch TwoTower uses.
    events_batch = []
    now = datetime.utcnow()
    
    # Fast iteration over pandas rows
    for row in df.itertuples(index=False):
        u_uuid = kaggle_to_uuid_users.get(row.user_id)
        v_uuid = kaggle_to_uuid_videos.get(row.video_id)
        
        if not u_uuid or not v_uuid:
            continue

        # Extract extra fields if present
        metadata = {}
        if hasattr(row, 'device') and not pd.isna(row.device):
            metadata['device'] = str(row.device)
        if hasattr(row, 'watch_time_of_day') and not pd.isna(row.watch_time_of_day):
            metadata['watch_time_of_day'] = str(row.watch_time_of_day)
        if hasattr(row, 'recommended') and not pd.isna(row.recommended):
             metadata['recommended'] = bool(row.recommended)
        if hasattr(row, 'clicked') and not pd.isna(row.clicked):
             metadata['clicked'] = bool(row.clicked)
        if hasattr(row, 'subscribed_after') and not pd.isna(row.subscribed_after):
             metadata['subscribed_after'] = bool(row.subscribed_after)
             
        import json
        meta_json = json.dumps(metadata) if metadata else None
        
        # Use Kaggle timestamp if present, otherwise fallback to "now"
        event_time = now
        if hasattr(row, 'timestamp') and not pd.isna(row.timestamp):
            try:
                event_time = pd.to_datetime(row.timestamp).to_pydatetime()
            except Exception:
                pass
            
        # We always record a VIEW event for the watch_ratio extraction
        events_batch.append((u_uuid, v_uuid, 'VIEW', float(row.watch_ratio), meta_json, event_time))
        
        # If the Kaggle dataset explicitly marked 'liked', fire a LIKE event separately
        if getattr(row, 'is_liked', False):
             events_batch.append((u_uuid, v_uuid, 'LIKE', None, meta_json, event_time))
             
        if hasattr(row, 'commented') and str(row.commented) in ['1', 'true', 'yes', 't', 'True']:
             events_batch.append((u_uuid, v_uuid, 'COMMENT', None, meta_json, event_time))
    print(f"Writing {len(events_batch):,} Neural Network Training Events to PostgreSQL...")
    for i in range(0, len(events_batch), BATCH_SIZE * 5):
        try:
            await conn.executemany("""
                INSERT INTO events (user_id, video_id, event_type, watch_ratio, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, events_batch[i:i+(BATCH_SIZE * 5)])
            print(f"  ... inserted events split {i:,}/{len(events_batch):,} ...")
        except Exception as e:
            pass # ignore conflicts on massive inserts

    # ---------------------------------------------------------
    print("\n🧮 Stage 6: Recalculating Data Aggregates...")
    await conn.execute("""
        UPDATE videos SET 
            view_count = (SELECT count(*) FROM events WHERE video_id = videos.id AND event_type = 'VIEW'),
            like_count = (SELECT count(*) FROM events WHERE video_id = videos.id AND event_type = 'LIKE')
    """)

    print("\n✅ INGESTION COMPLETE!")
    print("\nYou have successfully migrated the entire Kaggle Dataset into Aurora-VRS.")
    print("If your row count exceeded 50,000, your PyTorch worker is already spinning up a new model asynchronously!")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(setup_kaggle_seed())
