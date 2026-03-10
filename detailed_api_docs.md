# AURORA-VRS API Documentation

This document officially outlines every available API endpoint natively built into the AURORA-VRS backend system serving on `localhost:8080`.

---

## 🔐 Authentication (`api/routers/auth.py`)

All protected endpoints require an `Authorization: Bearer <token>` HTTP header.

### **POST** `/api/v1/auth/register`
Creates a new user account securely hashed with `bcrypt`.
* **Payload:** 
  ```json
  {
    "email": "user@example.com", 
    "password": "strongPassword123!", 
    "names": "Full Name"
  }
  ```
* **Returns (200 OK):** 
  ```json
  {
    "access_token": "eyJhbGciOi...", 
    "refresh_token": "a1b2c3d4e5..."
  }
  ```

### **POST** `/api/v1/auth/login`
Authenticates an existing user and returns JWT credentials.
* **Payload:** 
  ```json
  {
    "email": "user@example.com", 
    "password": "strongPassword123!"
  }
  ```
* **Returns (200 OK):** 
  ```json
  {
    "access_token": "eyJhbGciOi...", 
    "refresh_token": "a1b2c3d4e5..."
  }
  ```

### **POST** `/api/v1/auth/refresh`
Generates a new short-lived access token for a valid session using the long-lived refresh token.
* **Payload:** 
  ```json
  {"refresh_token": "a1b2c3d4e5..."}
  ```
* **Returns (200 OK):** 
  ```json
  {"access_token": "eyJhbGciOi..."}
  ```

### **POST** `/api/v1/auth/logout`
Invalidates the current session's refresh token on the database ledger.
* **Payload:** 
  ```json
  {"refresh_token": "a1b2c3d4e5..."}
  ```
* **Returns:** `200 OK` `{"message": "Logged out"}`

### **POST** `/api/v1/auth/change-password`
Updates the user's explicit password hash string. **Requires Bearer Token.**
* **Payload:** 
  ```json
  {
    "old_password": "strongPassword123!", 
    "new_password": "evenStronger!Password456"
  }
  ```
* **Returns:** `200 OK` `{"message": "Password updated"}`

---

## 👤 Users (`api/routers/users.py`)

### **GET** `/api/v1/users/me`
Retrieves the active, authenticated session's user identity details. **Requires Bearer Token.**
* **Returns (200 OK):** 
  ```json
  {
    "id": "uuid-string", 
    "names": "Full Name", 
    "email": "user@example.com", 
    "bio": "Hello World!", 
    "avatar_url": "https://img.com/avatar.png", 
    "role": "USER"
  }
  ```

### **PUT** `/api/v1/users/me`
Updates the user's mutable profile fields. Every key is technically optional. **Requires Bearer Token.**
* **Payload:** 
  ```json
  {
    "names": "New Label", 
    "bio": "Updated biography string", 
    "avatar_url": "https://img.com/avatar2.png"
  }
  ```
* **Returns:** `200 OK` `{"message": "Profile updated"}`

### **GET** `/api/v1/users/{id}`
Retrieves the safe, public profile facing parameters of a target user. 
* **Returns (200 OK):** 
  ```json
  {
    "id": "uuid", "names": "Name", "bio": "...", "avatar_url": "..."
  }
  ```

### **POST** `/api/v1/users/{id}/follow`
Submits a follow edge from the requesting identity towards the target identity. **Requires Bearer Token.**

### **DELETE** `/api/v1/users/{id}/follow`
Removes a follow edge. **Requires Bearer Token.**

### **GET** `/api/v1/users/{id}/followers`
Lists user objects that are actively following the specified user UUID.

### **GET** `/api/v1/users/{id}/following`
Lists user objects that the target user actively follows.

---

## 📱 Feed Engine (`api/routers/feed.py`)

### **GET** `/api/v1/feed`
The primary machine learning endpoint. Recursively retrieves and ranks candidate videos globally based off the requested user UUID. 

If the user is unregistered or has an insufficient `event_count` (< 100 interaction records), they are served a randomized SQL 'Cold-Start' logic stream instead of the PyTorch Deep Learning `candidate_generation` path. 
* **Optional Authorization:** `Bearer <token>` (If no token is present, the server natively defaults to the cold-start fallback payload).
* **Query Params:** 
  * `page`: integer representing the scroll state slice (default `1`).
  * `limit`: integer ceiling per batch payload (default `20`).
  * `video_type`: query parameter toggling between `QUICK` (shorts formatting) or `LONGFORM` videos.
* **Returns (200 OK):** 
  ```json
  {
    "videos": [
      {
         "id": "uuid", "creator_id": "uuid", "title": "...", "description": "...", 
         "type": "QUICK", "privacy": "PUBLIC", "status": "READY", "duration_sec": 45.0,
         "view_count": 0, "like_count": 0, "avg_watch_ratio": 0.0, "created_at": "...",
         "tags": ["tag_uuid", "tag_uuid"]
      }
    ],
    "has_more": true,
    "next_cursor": null
  }
  ```

---

## 🎥 Videos (`api/routers/videos.py`)

### **GET** `/api/v1/videos`
Retrieves a paginated list of all publicly mapped videos sorted by descending creation timelines.
* **Query Params:** `page`, `limit`

### **GET** `/api/v1/videos/search`
Retrieves a paginated list of videos explicitly text-matching the query parameter.
* **Query Params:** `q="Search query"`

### **GET** `/api/v1/videos/{id}`
Retrieves a single Video object node metadata model.

### **POST** `/api/v1/videos/upload/start`
Pre-signs the ingestion transaction block for a fresh video record upload to state `UPLOADING`. **Requires Bearer Token.**
* **Payload:** 
  ```json
  {
    "title": "My New Video", 
    "description": "...", 
    "type": "QUICK", 
    "privacy": "PUBLIC"
  }
  ```
* **Returns (200 OK):** 
  ```json
  {"video_id": "uuid", "upload_url": "stub_s3_signed_url"}
  ```

### **POST** `/api/v1/videos/upload/complete`
Transitions an active ingestion URL to pipeline state `PROCESSING`. **Requires Bearer Token.**
* **Query Params:** `?video_id={id}`

### **GET** `/api/v1/videos/upload/{id}/status`
Queries the database explicitly for the `status` enum (`UPLOADING`, `PROCESSING`, `READY`, `FAILED`).
* **Returns (200 OK):** `{"status": "READY"}`

### **DELETE** `/api/v1/videos/{id}`
Hard deletes a specific video identity. **Requires Bearer Token (must equal `creator_id`).**

### **PATCH** `/api/v1/videos/{id}/privacy`
Updates a video's target visibility layer. **Requires Bearer Token.**
* **Payload:** `{"privacy": "PRIVATE"}`

---

## ❤️ Interactions & Analytics (`api/routers/videos.py` / `events.py`)

### **POST** `/api/v1/events`
The silent ingestor route. Used by the player frontend to fire `watch_ratio` completion timers, `PROFILE_VISIT` analytics, or implicit events that feed the Two-Tower interaction dataset model.
* **Payload:** 
  ```json
  {
    "video_id": "uuid", 
    "event_type": "VIEW", 
    "watch_ratio": 0.85, 
    "metadata": {}
  }
  ```

### **POST** `/api/v1/videos/{id}/view`
Public API hook explicitly iterating the static `view_count` on the video's node row.

### **POST** `/api/v1/videos/{id}/like`
Iterates the `like_count`, registers the LIKE `event`, and explicitly destroys any DISLIKE objects from the same user context. **Requires Bearer Token.**

### **POST** `/api/v1/videos/{id}/dislike`
Does the inverse operation to likes. **Requires Bearer Token.**

### **GET** `/api/v1/videos/{id}/comments`
Recursively yields the previous 50 comments on a given Video ID context.

### **POST** `/api/v1/videos/{id}/comments`
Mutates a text string attachment string onto the given Video. **Requires Bearer Token.**
* **Payload:** `{"content": "A thoughtful message."}`

---

## ⚙️ Administration & ML Health (`api/main.py` & `api/routers/misc.py`)

**ALL endpoints in this section strictly require an `Authorization: Bearer <token>` where the JWT explicitly issues `"role": "ADMIN"`.**

### **GET** `/api/v1/ml/status`
Exposes the live FastAPI `App State` verifying both Two-Tower index memory, Redis fallback flags, and FAISS dimensional sizing.
* **Returns (200 OK):** 
  ```json
  {
    "model_loaded": true,
    "model_path": "/app/storage/models/two_tower.pt",
    "faiss_size": 200,
    "faiss_ready": true,
    "min_events_threshold": 100,
    "two_tower_active": true
  }
  ```

### **POST** `/api/v1/ml/rebuild-index`
Manually queues a Python coroutine loop `asyncio.create_task(_rebuild_faiss_index(app))` overriding the standard 30-minute Redis trigger. This natively spins PyTorch weights and embeds all mapped UUID video features into the dense Index parameters array instantly.
* **Returns:** `200 OK` `{"status": "rebuild triggered"}`

### **POST** `/api/v1/content/categories`
Bootstraps a core static content genre pool type.
* **Payload:** `{"name": "Action"}`

---

## 🏷️ System Metadata (`api/routers/misc.py`)

### **GET** `/api/v1/content/categories`
Provides the native app mapping strings to categorize global discovery elements.

### **GET** `/api/v1/content/tags`
Retrieves all explicitly defined dynamic meta tag labels created universally across videos.

### **POST** `/api/v1/content/tags`
Submits a brand new arbitrary label explicitly mapping the tag array. **Requires Bearer Token.**
* **Payload:** `{"name": "VFX"}`

### **GET** `/api/v1/analytics/videos/{id}`
Returns granular telemetry stats mapped towards an asset's lifetime.
* **Returns (200 OK):**
  ```json
  {
    "views": 412,
    "likes": 56,
    "shares": 10,
    "avg_watch_ratio": 0.82
  }
  ```
