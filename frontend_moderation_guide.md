# Frontend Integration: Content Moderation (SHIELD)

Aurora now uses the **SHIELD** moderation system to screen videos. This change affects how the frontend handles video uploads and feed visibility.

## 1. Video Visibility & "Streaming Ready"

Every new video uploaded to Aurora is sent to SHIELD for moderation. While being moderated, the video is **hidden from the public feed**.

- **Field:** `streaming_ready` (boolean)
- **Logic:** Only display videos where `streaming_ready == true`.
- **Default:** New uploads always start with `streaming_ready: false`.

## 2. Video Statuses

The `videos` table now includes a `status` field to help the UI provide feedback to the user about their upload.

| Status | Meaning | UI Recommendation |
| :--- | :--- | :--- |
| `READY` | Moderation passed / Processing done. | Show in feed. |
| `UPLOADING` | File is currently being sent to server. | Show upload progress bar. |
| `PROCESSING` | Transcoding or internal prep. | Show "Processing..." spinner. |
| `REMOVED` | Moderation failed (Safe search violation). | Show "Content Removed" or remove from list. |
| `CSAM_REMOVED` | Illegal content detected. | Action: Account will be suspended. |

## 3. UI Implementation Tips

### Handling "Pending Moderation"
When a user finishes an upload, the video will not appear in the "Global Feed" immediately. We recommend:
- Showing a **"My Uploads"** section for the user.
- Labeling videos with `streaming_ready: false` as **"Pending Moderation"**.
- Polishing the experience by automatically refreshing the status every 30 seconds until it becomes `READY`.

### Monitoring Uploads
You can poll the status of an ongoing upload using:
`GET /api/v1/videos/upload/{id}/status`

## 4. Root Health Check
Legitimate clients can now verify the API is online by hitting the root URL:
`GET /`

**Response Example:**
```json
{
  "message": "Welcome to AuroraVRS API",
  "status": "online",
  "version": "1.0.0"
}
```

---
**Note:** The backend automatically handles the communication with SHIELD. The frontend only needs to respect the `streaming_ready` and `status` fields.
