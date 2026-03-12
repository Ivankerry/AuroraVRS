import os
import time
import json
import requests
import pandas as pd
from tqdm import tqdm
import uuid
from typing import List, Optional

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = "http://localhost:8000/api/v1"
# When running on host, default to local 'videos' folder. 
# When running in Docker, it will use the env var /app/video_storage
VIDEO_STORAGE_PATH = os.getenv("VIDEO_STORAGE_PATH", "./videos")
os.makedirs(VIDEO_STORAGE_PATH, exist_ok=True)
DOWNLOAD_BASE_URL = "https://recsys.westlake.edu.cn/MicroLens-100k-Dataset/MicroLens-100k_videos/"

CSV_TITLE_FILE = "MicroLens-100k_title_en.csv"
CSV_TAG_FILE = "tags_to_summary.csv"
TXT_ENGAGEMENT_FILE = "MicroLens-100k_likes_and_views.txt"

VIDEO_LIMIT = 8000
EVENT_LIMIT = 50000

# ── Helpers ───────────────────────────────────────────────────────────────────
session = requests.Session()

def download_video(item_id: str, v_uuid: str):
    file_path = os.path.join(VIDEO_STORAGE_PATH, f"{v_uuid}.mp4")
    if os.path.exists(file_path):
        return True
    
    url = f"{DOWNLOAD_BASE_URL}{item_id}.mp4"
    try:
        response = session.get(url, stream=True, timeout=30)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        else:
            print(f"  ❌ Failed to download {item_id}: HTTP {response.status_code}")
    except Exception as e:
        print(f"  ❌ Error downloading {item_id} (UUID: {v_uuid}): {e}")
    return False

def register_video(video_data: dict):
    try:
        # High-performance high-volume metadata ingestion
        r = session.post(f"{API_BASE_URL}/videos/register", json=video_data, timeout=15)
        if r.status_code in (200, 201):
            return True
        print(f"  ❌ Registry error: {r.status_code} - {r.text[:100]}")
    except Exception as e:
        print(f"  ❌ Registry exception: {e}")
    return False

def fire_event(video_id: str):
    try:
        r = session.post(f"{API_BASE_URL}/events", json={
            "video_id": video_id,
            "event_type": "VIEW",
            "watch_ratio": 1.0
        }, timeout=5)
        return r.status_code in (200, 201)
    except:
        return False

# ── Main Pipeline ─────────────────────────────────────────────────────────────
def main():
    print(f"\n🚀 AURORA-VRS MASTER SEEDER (FULL 3-FILE PIPELINE)")
    print(f"📂 Storage: {VIDEO_STORAGE_PATH}")
    print(f"📡 API:     {API_BASE_URL}\n")

    # 1. Load and Merge Data from 3 Sources
    print("📊 Loading data from 2 CSVs and 1 TXT file...")
    try:
        # File 1: Titles (item_id, title)
        df_title = pd.read_csv(CSV_TITLE_FILE, names=['item_id', 'title'], dtype={'item_id': str})
        
        # File 2: Tags/Categories (item_id, category)
        df_tags = pd.read_csv(CSV_TAG_FILE, names=['item_id', 'category'], dtype={'item_id': str})
        
        # File 3: Engagement (item_id, likes, views) - Whitespace separated
        df_eng = pd.read_csv(TXT_ENGAGEMENT_FILE, sep=r'\s+', names=['item_id', 'likes', 'views'], dtype={'item_id': str})
        
        # Merging Logic: Title + Tags first, then add Engagement
        df_merged = pd.merge(df_title, df_tags, on='item_id')
        df = pd.merge(df_merged, df_eng, on='item_id')
        
        print(f"  ✅ {len(df):,} total records merged successfully.")
    except Exception as e:
        print(f"❌ Critical Error merging files: {e}")
        return

    # 2. Phase 1: Ingesting 8,000 Videos
    print(f"\n🎥 PHASE 1: Seeding {VIDEO_LIMIT} videos with rich metadata...")
    seeded_ids = []
    success_count = 0
    
    for _, row in df.iterrows():
        if success_count >= VIDEO_LIMIT:
            break
            
        item_id = row['item_id']
        # Deterministic UUID for DB compatibility
        v_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"microlens-{item_id}"))
        
        title = row['title']
        category = str(row['category']) if not pd.isna(row['category']) else "General"
        
        # Prepare Tags
        tags = [category]
        if "#" in str(title):
            title_parts = str(title).split("#")
            for part in title_parts[1:]:
                tag = part.strip().split()[0]
                if tag:
                    tags.append(tag)

        # Download Check (Saves as {v_uuid}.mp4)
        if download_video(item_id, v_uuid):
            video_payload = {
                "id": v_uuid,
                "title": title,
                "description": f"MicroLens Import | Category: {category} | MicroLensID: {item_id}",
                "categories": [category], 
                "tags": list(set(tags)),
                "view_count": int(row.get('views', 0)),
                "like_count": int(row.get('likes', 0)),
                "manifest_url": f"/api/v1/videos/content/{v_uuid}.mp4",
                "status": "READY"
            }
            
            if register_video(video_payload):
                success_count += 1
                seeded_ids.append(v_uuid)
                print(f"[SEEDING {success_count}/{VIDEO_LIMIT}] UUID: {v_uuid} | Cat: {category} | Title: {title[:40]}...")
        
    print(f"✅ Phase 1 Complete. {success_count} videos registered.")

    if not seeded_ids:
        print("❌ No videos were seeded. Pipeline aborted.")
        return

    # 3. Phase 2: Injecting 50,000 Events
    print(f"\n🔥 PHASE 2: Injecting {EVENT_LIMIT} engagement events...")
    events_fired = 0
    
    with tqdm(total=EVENT_LIMIT, desc="Injecting Events") as pbar:
        while events_fired < EVENT_LIMIT:
            # Round-robin injection over seeded videos
            v_id = seeded_ids[events_fired % len(seeded_ids)]
            if fire_event(v_id):
                events_fired += 1
                pbar.update(1)
                
                if events_fired % 1000 == 0:
                    print(f"\n[EVENT LOG] Seeding progress: {events_fired}/{EVENT_LIMIT} events fired.")
            
            # CPU Safety: Small sleep to prevent API bottleneck
            time.sleep(0.005)

    print(f"\n✨ MASTER SEEDER FINISHED!")
    print(f"📊 Summary:")
    print(f"   - CSV Title File:     {CSV_TITLE_FILE}")
    print(f"   - CSV Tag/Cat File:    {CSV_TAG_FILE}")
    print(f"   - TXT Engagement File: {TXT_ENGAGEMENT_FILE}")
    print(f"   - Total Successful Seeds: {success_count}")
    print(f"   - Total Events Fired:     {events_fired}")
    print(f"\n🚀 Project is fully populated. Check your Video Feed now!")

if __name__ == "__main__":
    main()
