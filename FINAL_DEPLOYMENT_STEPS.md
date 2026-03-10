# 🚀 Final Deployment Steps: AuroraVRS on Contabo VPS

Follow these steps exactly to move your local code to your new Contabo VPS.

---

## 1. Prepare Your Local Code
Before connecting to the VPS, ensure all fixes are committed and pushed to your repository (GitHub/GitLab):
- [ ] Indentation fix for `worker/two_tower_trainer.py`.
- [ ] Added `deploy.sh` script.

---

## 2. Connect and Setup VPS
1. **SSH into your VPS**:
   ```bash
   ssh root@<YOUR_VPS_IP>
   ```
2. **Clone your repository**:
   ```bash
   git clone <YOUR_GIT_REPO_URL>
   cd AuroraVRS
   ```

---

## 3. Pre-Deployment Configuration (CRITICAL)

### A. Environment Variables
1. **Create the .env file**:
   ```bash
   nano .env
   ```
2. **Paste your configuration**. Ensure the URLs point to the Docker service names, NOT localhost:
   ```env
   # Example
   DATABASE_URL=postgresql://user:password@db:5432/aurora
   REDIS_URL=redis://redis:6379/0
   MODEL_PATH=/app/storage/models/two_tower.pt
   # ... other variables ...
   ```
   *Press `Ctrl+O`, `Enter`, then `Ctrl+X` to save and exit.*

### B. Add Swap Space (Recommended for Training)
Prevent memory crashes during model training:
```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### C. Initialize the Database (MANDATORY)
Run the migration script to create tables and extensions inside the Docker container:
```bash
# Run this from the root of the AuroraVRS folder on your VPS
docker compose exec -T db psql -U user -d db < api/migrations/init.sql
```
*Note: If you changed the DB user or name in `.env`, replace `user` and `db` accordingly.*

---

## 4. Launch Deployment
Run the automated deployment script:
```bash
chmod +x deploy.sh
./deploy.sh
```
*This will install Docker, Docker Compose, and build/restart your containers.*

---

## 5. Verify and Monitor
1. **Check Container Status**:
   ```bash
   docker compose ps
   ```
2. **Access the API**:
   The API is mapped to port **8080** on your VPS.
   - **Internal test**: `curl http://localhost:8080/health`
   - **External test**: `http://<YOUR_VPS_IP>:8080/health`
   
3. **Watch the Training Logs**:
   ```bash
   docker compose logs -f worker
   ```
   *Look for: "Starting training cycle" and "Epoch 1/20 completed".*

---

## 6. Seed Large Dataset (Optional)
If you want to train on the 1 million YouTube interactions:
1. **Apply Configuration Changes** (if not already done):
   ```bash
   git pull
   docker compose up -d --build
   ```
2. **Run the Seed Script**:
   ```bash
   docker compose exec worker python /app/seed_kaggle.py
   ```
   *This will take about 5–10 minutes to process all 1M rows.*
3. **Run User Interest Backfill**:
   ```bash
   docker compose exec worker python /app/backfill_iv.py
   ```
   *This summarizes the 1M events into user profiles that the model needs for training.*

---

## 7. Maintenance Commands
- **Stop everything**: `docker compose down`
- **Restart one service**: `docker compose restart worker`
- **Update with latest code**:
  ```bash
  git pull
  docker compose up -d --build
  ```
