import requests
import json
import time
import random
import sys

API_BASE_URL = "http://localhost:8080/api/v1"

# User Credentials
EMAIL = "music@gmail.com"
PASSWORD = "test123"
NAMES = "Music Comedy Fan"

def register_user():
    print(f"Registering user {EMAIL}...")
    try:
        r = requests.post(f"{API_BASE_URL}/auth/register", json={
            "email": EMAIL,
            "password": PASSWORD,
            "names": NAMES
        })
        if r.status_code in (200, 201):
            print("✅ User registered successfully.")
            return r.json().get("access_token")
        elif r.status_code == 400 and "already registered" in r.text:
            print("ℹ️ User already registered, logging in...")
            return login_user()
        else:
            print(f"❌ Registration failed: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Error during registration: {e}")
    return None

def login_user():
    try:
        r = requests.post(f"{API_BASE_URL}/auth/login", json={
            "email": EMAIL,
            "password": PASSWORD
        })
        if r.status_code == 200:
            print("✅ Login successful.")
            return r.json().get("access_token")
        else:
            print(f"❌ Login failed: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Error during login: {e}")
    return None

def find_videos(query, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{API_BASE_URL}/videos/search", params={"q": query}, headers=headers)
        if r.status_code == 200:
            vids = r.json()
            print(f"🔍 Found {len(vids)} videos for '{query}'")
            return [v["id"] for v in vids]
        else:
            print(f"❌ Search failed: {r.status_code}")
    except Exception as e:
        print(f"❌ Error during search: {e}")
    return []

def fire_events(video_ids, token, count=100):
    headers = {"Authorization": f"Bearer {token}"}
    events_fired = 0
    print(f"🔥 Injecting {count} events...")
    
    for i in range(count):
        v_id = random.choice(video_ids)
        event_type = random.choices(["VIEW", "LIKE", "SHARE"], weights=[0.8, 0.15, 0.05])[0]
        watch_ratio = random.uniform(0.6, 1.0) if event_type == "VIEW" else None
        
        try:
            r = requests.post(f"{API_BASE_URL}/events", json={
                "video_id": v_id,
                "event_type": event_type,
                "watch_ratio": watch_ratio
            }, headers=headers)
            if r.status_code in (200, 201):
                events_fired += 1
                if events_fired % 50 == 0:
                    print(f"  Progress: {events_fired}/{count} events fired.")
            else:
                print(f"  ❌ Event failed: {r.status_code}")
        except Exception as e:
            print(f"  ❌ Error firing event: {e}")
        
        time.sleep(0.01) # Small delay
    
    print(f"✅ Finished firing {events_fired} events.")

def main():
    token = register_user()
    if not token:
        sys.exit(1)
    
    # 1. Seed Music
    music_vids = find_videos("music", token)
    if music_vids:
        fire_events(music_vids, token, count=250)
    else:
        print("⚠️ No music videos found to seed.")
        
    # 2. Seed Comedy
    comedy_vids = find_videos("comedy", token)
    if comedy_vids:
        fire_events(comedy_vids, token, count=250)
    else:
        print("⚠️ No comedy videos found to seed.")

    print("\n✨ Seeding Complete for music@gmail.com!")
    print("The model interest vector will now strongly favor Music and Comedy.")

if __name__ == "__main__":
    main()
