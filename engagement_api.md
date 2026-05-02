# AuroraVRS: Video Engagement & Events API

This document outlines all supported endpoints for recording user interactions. For the **TikTok 2026 "Interest-First" Upgrade**, the separation between **Action Endpoints** (State) and the **General Events API** (Signals) is critical.

---

## 🚀 General Events API (ML & Ranking Signals)
**Endpoint**: `POST /api/v1/events`  
**Description**: Primary input for the recommendation engine. These signals update the User Interest Vector (UIV) and the Global Trending Pool.

### Signal Payload
```json
{
  "video_id": "uuid-string",
  "event_type": "WATCH | VIEW | LIKE | SAVE | SHARE | COMMENT | DISLIKE | SKIP",
  "watch_ratio": 0.85, 
  "metadata": { "source": "feed" }
}
```

### 2026 Signal Weights & logic
Every event type has a specific weight applied to the user's interest categories:

| Event Type | Weight | Recommendation Impact | Frontend Trigger Logic |
| :--- | :--- | :--- | :--- |
| **WATCH / VIEW** | 0.0 - 1.0 | Based on `watch_ratio`. | Fire every 5 seconds or at completion. |
| **LIKE** | +0.6 | Increases category affinity. | Fire on "Double Tap" or Like button press. |
| **SAVE** | +1.2 | **Highest positive signal.** | Fire when added to "Favorites". |
| **SHARE** | +1.0 | Strong positive signal. | Fire when share sheet is opened. |
| **COMMENT** | +0.4 | Medium positive signal. | Fire when a comment is successfully posted. |
| **DISLIKE** | -1.0 | Blocks similar content. | Fire on "Long Press -> Not Interested". |
| **SKIP** | **-0.5** | **10% Penalty Rule (see below).** | Fire if swiped away < 20% watched. |

> [!IMPORTANT]
> **The 10% Skip Penalty**: If a `SKIP` event is fired with a `watch_ratio < 0.1`, a massive negative ranker (-1.0 points) is applied to that video's tags for the next 24 hours.

---

## 📊 Action Endpoints (Database Updates)
These endpoints update public counters and relational tables. They should be called alongside the Events API.

### 1. Unified Reactions
*   **POST** `/api/v1/videos/{id}/like`  
    Adds a like record. Automatically removes a dislike if it exists.
*   **POST** `/api/v1/videos/{id}/dislike`  
    Adds a dislike record. Automatically removes a like if it exists.

### 2. Social & Collections
*   **POST** `/api/v1/videos/{id}/save`  
    Adds video to user's "Saves" table for later retrieval.
*   **POST** `/api/v1/videos/{id}/comments`  
    Payload: `{ "content": "..." }`. Creates a comment record.

### 3. Public View Counter
*   **POST** `/api/v1/videos/{id}/view`  
    Increments the global `view_count`. Should be fired *once* per session per video.

---

## 💎 Metadata Enrichment (UI Badges)
API responses from `/feed` include `viral_tier`. Use this for visual decoration:
- `WATCH`: Low-level breakout (1.5x boost)
- `HOT`: Trending (2x boost)
- `VIRAL`: Regional Hit (3x boost)
- `MEGA_VIRAL`: Global Sensation (5x boost)

---

## 💡 Frontend Implementation Flow
To ensure data consistency and AI accuracy, your app must trigger **two calls** for most actions:

1.  **State Call**: e.g., `POST /videos/123/like` (Increments the UI counter).
2.  **Signal Call**: e.g., `POST /events` with type `LIKE` (Updates personalization vector).

Current backend behavior also bridges common action endpoints into creator-affinity tracking, so likes, saves, comments, follows, and unfollows are reflected in recommendation state even if the frontend misses the signal call.
Follow and unfollow also invalidate the user's feed cache immediately, so the next feed request reflects the new social graph.

---

## ⏭️ Detailed Skip Event (The "How-To")
The `SKIP` event is the only negative behavioral signal that doesn't require a manual "Dislike" from the user. It is inferred by the frontend based on navigation.

## 👤 Follow and Creator Affinity
Following a creator is now treated as a direct recommendation signal.

### What it does
* Follows and unfollows update a per-user creator-affinity store.
* Followed creators are re-injected into feed candidates even when ML retrieval is active.
* Follow and unfollow clear the user feed cache immediately so the next feed request reflects the change.

### Recommended frontend behavior
* Call the follow endpoint when the user taps follow.
* You do not need a separate follow event call; the backend now bridges it.

### When to Fire
*   **Trigger**: As soon as the user swiping *away* from a video (Next/Back).
*   **Threshold**: Only fire if the video has been active for **less than 15 seconds** or **less than 20%** of its total duration.
*   **Wait**: Do NOT fire a skip if the user simply paused and then resumed.

### Implementation Example (Typescript/React)
```typescript
const onVideoSwipeAway = (videoId: string, currentTime: number, duration: number) => {
  const watchRatio = currentTime / duration;

  // The 10% Penalty Zone
  if (watchRatio < 0.1) {
    console.log("⚠️ Extreme Skip Detected: Triggering Penalty");
  }

  // Only report as SKIP if < 20% watched
  if (watchRatio < 0.2) {
    fetch('/api/v1/events', {
      method: 'POST',
      body: JSON.stringify({
        video_id: videoId,
        event_type: 'SKIP',
        watch_ratio: watchRatio,
        metadata: { trigger: 'user_swipe' }
      })
    });
  }
};
```

### Implementation Example (Flutter/Dart)
In Flutter, this usually happens inside your `PageView` or `ListView` when the `pageIndex` changes. Use your `VideoPlayerController` to get the current position.

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:video_player/video_player.dart';

Future<void> reportSkip(VideoPlayerController controller, String videoId) async {
  final position = await controller.position;
  final duration = controller.value.duration;
  
  if (position == null || duration == Duration.zero) return;

  final double watchRatio = position.inMilliseconds / duration.inMilliseconds;

  // The 10% Penalty Zone (Logged for debugging)
  if (watchRatio < 0.1) {
    print("AI Alert: Critical skip penalty triggered for $videoId");
  }

  // Mandatory: Only fire SKIP if watch ratio is under 20%
  if (watchRatio < 0.2) {
    await http.post(
      Uri.parse('https://api.aurora-vrs.com/api/v1/events'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $jwtToken',
      },
      body: jsonEncode({
        'video_id': videoId,
        'event_type': 'SKIP',
        'watch_ratio': watchRatio,
        'metadata': {'platform': 'flutter', 'threshold': '20%'},
      }),
    );
  }
}
```

#### Detailed Trigger Flow in Flutter:
1.  **Listen to Scroll**: In your `PageView.onPageChanged(int index)`, get the controller for the *previously active* video (the one the user just left).
2.  **Capture Position**: Immediately call `controller.position` (it's asynchronous).
3.  **Fire and Forget**: Don't await the network call if it blocks your UI; fire the `reportSkip` function in the background as you transition to the new video.
4.  **Dispose Safety**: Ensure you capture the position and fire the event *before* you call `controller.dispose()` on the old video.
