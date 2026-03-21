import requests
import json
import sys

API_BASE_URL = "http://localhost:8080/api/v1"
EMAIL = "music@gmail.com"
PASSWORD = "test123"

def login_user():
    try:
        r = requests.post(f"{API_BASE_URL}/auth/login", json={
            "email": EMAIL,
            "password": PASSWORD
        })
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception as e:
        print(f"❌ Login error: {e}")
    return None

def check_profile(token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        # Check users/me or a personalized feed
        r = requests.get(f"{API_BASE_URL}/users/me", headers=headers)
        if r.status_code == 200:
            user_data = r.json()
            print("\n--- User Profile ---")
            print(f"Email: {user_data.get('email')}")
            
            # Check interest vector if available in the response
            # Note: Sometimes it's in a separate endpoint or user settings
            print(f"Interests (Raw): {user_data.get('interest_weights') or 'Not in basic profile'}")
        
        # Check the feed to see what's being recommended
        r = requests.get(f"{API_BASE_URL}/feed", headers=headers)
        if r.status_code == 200:
            feed_data = r.json()
            videos = feed_data.get('videos', [])
            print("\n--- Current Feed Top 5 ---")
            for i, vid in enumerate(videos[:5]):
                print(f"{i+1}. {vid.get('title')} (Cat: {vid.get('categories')})")
        else:
            print(f"❌ Feed error: {r.status_code}")
            
    except Exception as e:
        print(f"❌ Profile check error: {e}")

def main():
    token = login_user()
    if not token:
        print("❌ Could not login to verify.")
        sys.exit(1)
    
    check_profile(token)

if __name__ == "__main__":
    main()
