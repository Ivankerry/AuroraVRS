# AuroraVRS: Video Engagement & Events API

This document outlines all supported endpoints for recording user interactions with videos. These events are divided into **Action Endpoints** (which update database counts like likes and comments) and the **General Events API** (which feeds the recommendation engine).

---

## 🚀 General Events API (ML Signals)
This is the primary endpoint for the recommendation engine. Every interaction logged here directly influences the user's future feed.

### `POST /api/v1/events`
**Description**: Records a raw engagement signal.
**Authentication**: Optional (Anonymous events are allowed but don't influence personalization).

**Request Body**:
```json
{
  "video_id": "uuid-string",
  "event_type": "VIEW | LIKE | SHARE | DISLIKE | SKIP",
  "watch_ratio": 0.85, 
  "metadata": { "device": "ios", "source": "feed" }
}
```

| Event Type | Recommendation Impact |
| :--- | :--- |
| **VIEW** | Positive signal (especially if `watch_ratio` > 0.5). |
| **LIKE** | Strong positive signal. |
| **SHARE** | Strong positive signal. |
| **DISLIKE** | Strong negative signal (hides similar content). |
| **SKIP** | Subtle negative signal (indicates lack of interest). |

---

## 📊 Action Endpoints (Database Updates)
These endpoints explicitly update public-facing metrics like like counts and comment threads.

### 1. Like / Dislike
These endpoints manage the binary "Up/Down" state and update the `like_count` on the video.

*   **POST** `/api/v1/videos/{video_id}/like`
    *   *Effect*: Adds a like, removes a dislike if present.
*   **POST** `/api/v1/videos/{video_id}/dislike`
    *   *Effect*: Adds a dislike, removes a like if present.

### 2. Views
*   **POST** `/api/v1/videos/{video_id}/view`
    *   *Effect*: Increments the public `view_count` by 1. Should be called when a video starts playing.

### 3. Comments
*   **GET** `/api/v1/videos/{video_id}/comments`
    *   *Effect*: Retrieves the latest 50 comments for a video.
*   **POST** `/api/v1/videos/{video_id}/comments`
    *   *Request Body*: `{ "content": "Great video!" }`
    *   *Effect*: Adds a comment and increments the `comment_count`.

---

## 💎 Metadata & Viral Info (Visual Badges)
These fields are returned in both the `GET /feed` and `GET /videos/{id}` responses. Use them to display visual badges or filters in the frontend.

### Response Fields
- **`categories`**: Array of human-readable category names (e.g., `["Gaming", "Tech"]`).
- **`tags`**: Array of human-readable tags (e.g., `["Esports", "Review"]`).
- **`viral_tier`**: The current virality level (Null | "WATCH" | "HOT" | "VIRAL" | "MEGA_VIRAL").

### Implementation Example:
If `viral_tier` is **"MEGA_VIRAL"**, you should display a "🔥 Trending" or "Viral" badge on the video card.

---

## 💡 Frontend Integration Tip
For the best recommendation accuracy, your app should call **both** the Action endpoint and the General Event API.

**Example: When a user likes a video:**
1.  Call `POST /api/v1/videos/{id}/like` (Updates the UI count).
2.  Call `POST /api/v1/events` with type `LIKE` (Tells the AI to show more like this).
