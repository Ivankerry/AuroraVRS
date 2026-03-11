import requests
import os
import json

API_URL = "http://62.84.176.140:8080/api/v1"

def get_token():
    r = requests.post(f"{API_URL}/auth/login", json={
        "email": "testone@gmail.com",
        "password": "test123"
    })
    return r.json().get("access_token")

def test_upload():
    token = get_token()
    if not token:
        print("❌ Auth failed")
        return

    # Create dummy video file
    with open("test_video.mp4", "wb") as f:
        f.write(os.urandom(1024))
    
    # Mock tags and categories
    # Assuming tags like 'Tech' and categories like 'Gaming' exist
    # I'll just use dummy UUIDs for now and check if it fails or use a script to find real ones
    
    # Find real tag/cat IDs first
    print("🔍 Fetching tags/categories...")
    cats_resp = requests.get(f"{API_URL}/content/categories")
    tags_resp = requests.get(f"{API_URL}/content/tags")
    
    if cats_resp.status_code != 200:
        print(f"❌ Failed to fetch categories: {cats_resp.status_code} - {cats_resp.text}")
        cats = []
    else:
        cats = cats_resp.json()

    if tags_resp.status_code != 200:
        print(f"❌ Failed to fetch tags: {tags_resp.status_code} - {tags_resp.text}")
        tags = []
    else:
        tags = tags_resp.json()

    # Extract IDs (handling list of dicts)
    cat_ids = [str(c['id']) for c in cats[:1]] if isinstance(cats, list) and cats else []
    tag_ids = [str(t['id']) for t in tags[:2]] if isinstance(tags, list) and tags else []
    
    print(f"📦 Uploading with Categories: {cat_ids}, Tags: {tag_ids}")
    
    data = {
        "title": "Verifying Upload Flow",
        "description": "This is a test video for Milestone 7",
        "type": "QUICK",
        "privacy": "PUBLIC",
        "category_ids": json.dumps(cat_ids),
        "tag_ids": json.dumps(tag_ids)
    }
    
    files = {
        "file": ("test_video.mp4", open("test_video.mp4", "rb"), "video/mp4")
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    
    r = requests.post(f"{API_URL}/videos/upload", data=data, files=files, headers=headers)
    
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
    
    if r.status_code == 200:
        print("✅ Upload successful!")
        v_id = r.json().get("video_id")
        m_url = r.json().get("manifest_url")
        print(f"🔗 Video ID: {v_id}")
        print(f"🔗 Manifest URL: {m_url}")
        
        # Verify it exists in feed
        print("📺 Checking feed...")
        feed = requests.get(f"{API_URL}/feed", headers=headers).json()
        found = any(v['id'] == v_id for v in feed.get('videos', []))
        if found:
            print("✨ Video found in feed!")
        else:
            print("❓ Video not found in feed yet (might be due to threshold/ranking)")

if __name__ == "__main__":
    test_upload()
