# 🚚 Video Storage Migration Guide (VPS)

Use this guide to migrate your video files from the Docker Named Volume to a Host Bind Mount. This ensures your videos are stored directly in `~/AuroraVRS/videos` for easier access.

## 🛠️ Step-by-Step Migration

### 1. Create Host Directories
Run this on your VPS to create the target folders:
```bash
mkdir -p ~/AuroraVRS/videos
mkdir -p ~/AuroraVRS/models
```

### 2. Migrate Existing Data
Run these commands to rescue your existing files from the old volumes:
```bash
# Migrate Videos
docker run --rm -v auroravrs_video_storage:/from -v ~/AuroraVRS/videos:/to alpine ash -c "cp -av /from/. /to/"

# Migrate Models
docker run --rm -v auroravrs_model_storage:/from -v ~/AuroraVRS/models:/to alpine ash -c "cp -av /from/. /to/"
```

### 3. Set Permissions
Ensure the Docker containers have permission to read/write to these folders:
```bash
sudo chown -R $USER:$USER ~/AuroraVRS/videos ~/AuroraVRS/models
chmod -R 755 ~/AuroraVRS/videos ~/AuroraVRS/models
```

### 4. Restart with New Configuration
Since I have already updated your `docker-compose.yml`, you just need to restart the services:
```bash
docker compose down
docker compose up -d
```

---

## 🔍 How to Verify
Check the host folder to confirm the files are there:
```bash
ls -lh ~/AuroraVRS/videos
```

If you see your `.mp4` files, the migration was successful! New videos will now appear here automatically.
