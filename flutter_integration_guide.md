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
          ...
        }
      ]
    }
    ```

### Playback URL
To play the video, prefix the `manifest_url` with the server base URL:
`http://62.84.176.140:8080/api/v1/videos/content/<id>.mp4`

---

## 🛠️ 5. Troubleshooting
- **405 Method Not Allowed**: Ensure you are using `POST` and the URL is exactly `/api/v1/videos/upload`.
- **413 Payload Too Large**: If the video is huge, ensure the server (Nginx/API) allows it. Current limit is generally 100MB+ depending on VPS config.
- **CORS**: The API allows all origins (`*`), so Flutter Web/Mobile should connect without issues.
