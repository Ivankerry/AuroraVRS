# 📱 Flutter Integration Guide: Video Upload & Feed

This guide outlines how to integrate the Flutter frontend with the AuroraVRS backend for video uploads and content discovery.

---

## 🔐 1. Authentication
All protected endpoints require a JWT Bearer token.
- **Endpoint**: `POST /api/v1/auth/login`
- **Body**: `{"email": "...", "password": "..."}`
- **Response**: `{"access_token": "...", "refresh_token": "..."}`
- **Header**: `Authorization: Bearer <access_token>`

---

## 🔍 2. Content Discovery (For Pickers)
Before uploading, the app should fetch available categories and tags to show in the UI.

### Fetch Categories
- **Endpoint**: `GET /api/v1/content/categories`
- **Response**: `[{"id": "...", "name": "Gaming"}, ...]`

### Fetch Tags
- **Endpoint**: `GET /api/v1/content/tags`
- **Response**: `[{"id": "...", "name": "fortnite"}, ...]`

---

## 📤 3. Video Upload (Multipart)
The upload endpoint uses `multipart/form-data`.

- **Endpoint**: `POST /api/v1/videos/upload`
- **Headers**: 
    - `Authorization: Bearer <token>`
    - `Content-Type: multipart/form-data`

### Form Fields:
| Field | Type | Description |
| :--- | :--- | :--- |
| `file` | File | **(Required)** The video file (binary) |
| `title` | String | **(Required)** Title of the video |
| `description`| String | (Optional) Description |
| `type` | String | (Optional) e.g., `QUICK` or `LONG`. Defaults to `QUICK`. |
| `privacy` | String | (Optional) `PUBLIC` or `PRIVATE`. Defaults to `PUBLIC`. |
| `category_ids`| String (JSON) | (Optional) List of UUIDs: `["guid1"]`. Defaults to `[]`. |
| `tag_ids` | String (JSON) | (Optional) List of UUIDs: `["guid2"]`. Defaults to `[]`. |

### Flutter (Dio) Example:
```dart
FormData formData = FormData.fromMap({
  "file": await MultipartFile.fromFile(filePath, filename: "video.mp4"),
  "title": "My Awesome Video",
  "description": "Integrated from Flutter!",
  "type": "QUICK",
  "category_ids": jsonEncode(["cat-uuid-here"]),
  "tag_ids": jsonEncode(["tag-uuid-here"]),
});

var response = await dio.post("/api/v1/videos/upload", data: formData);
```

---

## 📺 4. Feed & Playback
After upload, the video will appear in the feed.

### Fetch Feed
- **Endpoint**: `GET /api/v1/feed?video_type=QUICK`
- **Response**: 
    ```json
    {
      "videos": [
        {
          "id": "video-uuid",
          "title": "...",
          "manifest_url": "/api/v1/videos/content/<filename>.mp4",
          "creator_id": "...",
          "tags": ["gaming", "action"],
          "categories": ["Gaming"],
          "view_count": 10,
          "like_count": 2
        }
      ],
      "has_more": false,
      "next_cursor": null
    }
    ```

### Playback URL
To play the video, prefix the `manifest_url` with the server base URL:
`http://62.84.176.140:8080/api/v1/videos/content/<id>.mp4`

---

## 🔄 5. Infinite Scroll & Pagination
To ensure a smooth user experience, the app should fetch videos in batches of 20 and automatically load more as the user scrolls.

Detailed implementation logic using `ScrollController`, `isFetching` states, and `has_more` handling can be found in the:
👉 **[Flutter Infinite Scroll & Pagination Guide](file:///c:/Users/dev/Desktop/AuroraVRS/flutter_pagination_guide.md)**

---

## 📈 6. Event Tracking
To power the recommendation engine, the app must report user interactions.

- **Endpoint**: `POST /api/v1/events`
- **Headers**: 
    - `Authorization: Bearer <token>`
    - `Content-Type: application/json`

### Request Body:
```json
{
  "video_id": "uuid-here",
  "event_type": "LIKE",
  "watch_ratio": 0.85,
  "metadata": {}
}
```

### Supported Event Types:
| Event Type | Description | Effect |
| :--- | :--- | :--- |
| `VIEW` | Normal playback start/continue | Baseline interest |
| `LIKE` | User liked the video | High positive signal |
| `SHARE` | User shared the video | Very high positive signal |
| `SKIP` | User swiped away quickly | Negative signal |
| `DISLIKE` | User explicitly disliked | High negative signal |
| `COMMENT` | User commented | Positive signal |

### Flutter (Dio) Example:
```dart
void reportEvent(String videoId, String type, {double? ratio}) async {
  await dio.post("/api/v1/events", data: {
    "video_id": videoId,
    "event_type": type,
    "watch_ratio": ratio ?? 1.0,
    "metadata": {},
  });
}
```

---

## 🛠️ 7. Troubleshooting
- **405 Method Not Allowed**: Ensure you are using `POST` and the URL is exactly `/api/v1/events` or `/api/v1/videos/upload`.
- **422 Unprocessable Entity**: Check that `video_id` is a valid UUID and `event_type` is one of the supported strings.
- **413 Payload Too Large**: If the video is huge, ensure the server (Nginx/API) allows it. Current limit is generally 100MB+ depending on VPS config.
- **CORS**: The API now allows only configured origins from `ALLOWED_ORIGINS`. If Flutter Web calls fail, add your frontend origin (for example, `https://app.example.com`) to `.env` and restart the API.
