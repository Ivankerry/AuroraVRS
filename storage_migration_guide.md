# 🚚 Video Storage Migration Guide (VPS)

Use this guide to migrate your video files from the Docker Named Volume to a Host Bind Mount. This ensures your videos are stored directly in `~/AuroraVRS/videos` for easier access.

## 🛠️ Step-by-Step Migration

### 1. Create the Host Directory
Run this on your VPS to create the target folder:
```bash
mkdir -p ~/AuroraVRS/videos
```

### 2. Migrate Existing Data
Run this one-liner to rescue your existing `.mp4` files from the old volume into the new folder:
```bash
docker run --rm -v auroravrs_video_storage:/from -v ~/AuroraVRS/videos:/to alpine ash -c "cp -av /from/. /to/"
```

### 3. Set Permissions
Ensure the Docker containers have permission to read/write to this folder:
```bash
sudo chown -R $USER:$USER ~/AuroraVRS/videos
chmod -R 755 ~/AuroraVRS/videos
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
