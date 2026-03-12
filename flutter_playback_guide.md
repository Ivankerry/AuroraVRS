# 📱 Flutter Frontend Integration: Fetching & Playing Videos

This document explains how your Flutter application should interact with the AuroraVRS backend (running on `62.84.176.140`) to fetch video lists and play them.

---

## 🌍 1. Base Configuration
Set your backend URL globally in your Flutter app:

```dart
const String baseUrl = "http://62.84.176.140:8080";
const String apiVersion = "/api/v1";
```

---

## 📂 2. Fetching the Video Feed
To get the list of videos for the home screen or discovery page:

- **Endpoint**: `GET http://62.84.176.140:8080/api/v1/feed`
- **Params**:
    - `video_type`: `QUICK` (shorts) or `LONGFORM` (standard)
    - `page`: `1` (for pagination)
- **Response**:
    ```json
    {
      "videos": [
        {
          "id": "uuid-here",
          "title": "Amazing Flutter App",
          "manifest_url": "/api/v1/videos/content/video_id.mp4",
          "creator_id": "...",
          ...
        }
      ]
    }
    ```

### Flutter Fetch Example (using Dio):
```dart
Future<void> fetchVideos() async {
  final response = await dio.get("$baseUrl$apiVersion/feed", queryParameters: {
    "video_type": "QUICK",
  });
  
  List videos = response.data['videos'];
  // Loop through videos and store them in your state
}
```

---

## 🎬 3. Playing the Videos
The backend returns a relative `manifest_url`. To play the video, you **must prepend the server IP**.

### Recommended Steps:
1.  Extract the `manifest_url` from the JSON response.
2.  Prepend `http://62.84.176.140:8080`.
3.  Pass the full URL to your video player (e.g., `video_player` or `chewie`).

### Constructing the Playback URL:
```dart
String relativeUrl = videoJson['manifest_url']; // e.g., "/api/v1/videos/content/abc.mp4"
String fullVideoUrl = "$baseUrl$relativeUrl"; 

// Result: http://62.84.176.140:8080/api/v1/videos/content/abc.mp4
```

### Flutter Video Player Example:
```dart
VideoPlayerController _controller = VideoPlayerController.networkUrl(
  Uri.parse("http://62.84.176.140:8080/api/v1/videos/content/your-video-id.mp4"),
);
```

---

## 📤 4. Uploading from App
When the user selects a video on their phone, send it as `multipart/form-data`.

- **Endpoint**: `POST http://62.84.176.140:8080/api/v1/videos/upload`
- **Required Fields**:
    - `file`: The video file
    - `title`: String
- **Optional Fields (Defaults handled by server)**:
    - `type`: `QUICK` (default) or `LONGFORM`
    - `privacy`: `PUBLIC` (default)
    - `category_ids`: JSON list `[]` (default)
    - `tag_ids`: JSON list `[]` (default)

---

## 🛠️ Summary Checklist
- [ ] Backend is at `http://62.84.176.140:8080`.
- [ ] Authentication required for Upload (Bearer Token in Headers).
- [ ] Playback URLs require the full server prefix.
- [ ] Video files serve from `/api/v1/videos/content/`.
