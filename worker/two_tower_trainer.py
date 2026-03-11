import asyncio
import os
import logging
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import math
from datetime import datetime
import json

import asyncpg
from core.two_tower import TwoTowerModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global lock to prevent overlapping training cycles
training_lock = asyncio.Lock()


BATCH_SIZE = 256
EPOCHS = 20
LR = 0.001
VAL_SPLIT = 0.2
PATIENCE = 3
MODEL_PATH = os.getenv("MODEL_PATH", "/app/storage/models/two_tower.pt")
CANDIDATE_PATH = os.getenv("CANDIDATE_PATH", "/app/storage/models/two_tower_candidate.pt")

async def get_db_pool():
    url = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return await asyncpg.create_pool(url)

async def load_training_data(conn):
    query = """
    SELECT 
        e.user_id, e.video_id, e.watch_ratio, e.event_type,
        uiv.tag_weights AS user_tag_weights, uiv.event_count,
        u.created_at AS user_created_at, v.view_count, v.like_count,
        v.avg_watch_ratio AS video_avg_watch_ratio, v.created_at AS video_created_at, v.duration_sec
    FROM events e
    JOIN user_interest_vectors uiv ON uiv.user_id = e.user_id
    JOIN users u ON u.id = e.user_id
    JOIN videos v ON v.id = e.video_id
    WHERE e.event_type IN ('VIEW', 'LIKE', 'SHARE', 'DISLIKE', 'SKIP')
    ORDER BY e.created_at DESC
    LIMIT 100000
    """
    return await conn.fetch(query)

async def load_vocab(conn):
    rows = await conn.fetch("SELECT id FROM tags UNION SELECT id FROM categories ORDER BY id")
    return {str(row['id']): idx for idx, row in enumerate(rows)}

async def load_video_tags(conn, video_ids):
    if not video_ids:
        return {}
    query = """
    SELECT video_id, tag_id FROM video_tags WHERE video_id = ANY($1::uuid[])
    UNION ALL
    SELECT video_id, category_id as tag_id FROM video_categories WHERE video_id = ANY($1::uuid[])
    """
    rows = await conn.fetch(query, video_ids)
    video_tag_map = {vid: [] for vid in video_ids}
    for r in rows:
        video_tag_map[r['video_id']].append(str(r['tag_id']))
    return video_tag_map

def prepare_dataset(records, vocab, video_tag_map):
    logger.info(f"Preparing dataset with {len(records)} records...")
    positives = []
    video_features = {}
    now = datetime.utcnow()
    all_vids_list = list(set(r['video_id'] for r in records))
    all_vids_array = np.array(all_vids_list)
    
    for i, r in enumerate(records):
        if i % 10000 == 0:
            logger.info(f"Dataset preparation progress: {i}/{len(records)} records...")
            
        vid = r['video_id']
        if vid not in video_features:
            # strip timezone info if postgres returns aware datetimes
            vid_created = r['video_created_at']
            if vid_created.tzinfo:
                vid_created = vid_created.replace(tzinfo=None)
            
            age_hours = (now - vid_created).total_seconds() / 3600.0
            video_features[vid] = {
                'tag_ids': video_tag_map.get(vid, []),
                'view_count': math.log1p(r['view_count'] or 0),
                'like_rate': (r['like_count'] or 0) / max(r['view_count'] or 1, 1),
                'avg_watch_ratio': r['video_avg_watch_ratio'] or 0.0,
                'age_hours_normalized': min(age_hours, 7200) / 7200.0,
                'duration_normalized': min(r['duration_sec'] or 0.0, 600) / 600.0
            }
            
        event_type = r['event_type']
        watch_ratio = r['watch_ratio'] or 0.0
        is_pos = (event_type in ('LIKE', 'SHARE')) or (event_type == 'VIEW' and watch_ratio >= 0.5)
        
        tag_weights = r['user_tag_weights'] or {}
        if isinstance(tag_weights, str):
            tag_weights = json.loads(tag_weights)

        # Milestone 3: Multi-Interest Jittering
        # If a user has multiple interests, we occasionally "boost" the category of the
        # current positive video during training. This teaches the User Tower that 
        # a blended vector is still a strong match for its individual components.
        if len(tag_weights) > 1 and is_pos:
            # Find the tag of the current positive video
            v_tags = video_tag_map.get(vid, [])
            if v_tags:
                jittered_weights = tag_weights.copy()
                for v_tag in v_tags:
                    if str(v_tag) in jittered_weights:
                        jittered_weights[str(v_tag)] *= 1.5 # Boost current interest
                tag_weights = jittered_weights
            
        event_count = min(r['event_count'], 10000) / 10000.0
        
        user_created = r['user_created_at']
        if user_created.tzinfo:
            user_created = user_created.replace(tzinfo=None)
            
        acc_age = min((now - user_created).days, 3650) / 3650.0
        u_feat = {'tag_weights': tag_weights, 'event_count': event_count, 'account_age_days': acc_age}
        
        negatives = []
        for _ in range(4):
            neg_vid = np.random.choice(all_vids_array)
            while neg_vid == vid:
                neg_vid = np.random.choice(all_vids_array)
            negatives.append(neg_vid)
            
        positives.append({
            'u_feat': u_feat, 
            'pos_vid': vid, 
            'negatives': negatives,
            'is_positive': is_pos
        })
    return positives, video_features

class TwoTowerDataset(torch.utils.data.Dataset):
    def __init__(self, pairs, video_features, vocab, num_tags, tag_embeddings):
        # pairs have already been filtered for is_positive in outer loop now
        self.pairs = pairs
        self.video_features = video_features
        self.vocab = vocab
        self.num_tags = num_tags
        self.tag_embeddings = tag_embeddings

    def __len__(self): return len(self.pairs)

    def _get_v_tensor(self, vid):
        v_feat = self.video_features[vid]
        v_tensor = torch.zeros(384 + 5, dtype=torch.float32)
        
        tag_vectors = [self.tag_embeddings[str(t_id)] for t_id in v_feat['tag_ids'] if str(t_id) in self.tag_embeddings]
        if tag_vectors:
            v_tensor[:384] = torch.tensor(np.mean(tag_vectors, axis=0), dtype=torch.float32)
            
        v_tensor[384] = float(v_feat['view_count'])
        v_tensor[384+1] = float(v_feat['like_rate'])
        v_tensor[384+2] = float(v_feat['avg_watch_ratio'])
        v_tensor[384+3] = float(v_feat['age_hours_normalized'])
        v_tensor[384+4] = float(v_feat['duration_normalized'])
        return v_tensor

    def __getitem__(self, idx):
        pair = self.pairs[idx]
        u_feat = pair['u_feat']
        pos_vid = pair['pos_vid']
        neg_vids = pair['negatives']
        
        vectors = []
        weights = []
        for t_id, w in u_feat['tag_weights'].items():
            if str(t_id) in self.tag_embeddings:
                vectors.append(self.tag_embeddings[str(t_id)])
                weights.append(float(w))
                
        u_tensor = torch.zeros(384 + 2, dtype=torch.float32)
        if vectors:
            u_tensor[:384] = torch.tensor(np.average(vectors, axis=0, weights=weights), dtype=torch.float32)
            
        u_tensor[384] = float(u_feat['event_count'])
        u_tensor[384+1] = float(u_feat['account_age_days'])
        
        pos_v_tensor = self._get_v_tensor(pos_vid)
        neg_v_tensors = torch.stack([self._get_v_tensor(nv) for nv in neg_vids])
        
        return u_tensor, pos_v_tensor, neg_v_tensors

def evaluate_model(model, val_loader, device):
    model.eval()
    val_loss = 0
    with torch.no_grad():
        for u_batch, pos_v_batch, neg_v_batch in val_loader:
            u_batch = u_batch.to(device)
            pos_v_batch = pos_v_batch.to(device)
            neg_v_batch = neg_v_batch.to(device)
            
            u_emb, p_emb = model(u_batch, pos_v_batch)
            b, n, _ = neg_v_batch.size()
            _, n_emb = model(u_batch, neg_v_batch.view(-1, neg_v_batch.size(-1)))
            n_emb = n_emb.view(b, n, 128)
            
            p_scores = (u_emb * p_emb).sum(dim=1).unsqueeze(1) / 0.07
            n_scores = (u_emb.unsqueeze(1) * n_emb).sum(dim=2) / 0.07
            
            logits = torch.cat([p_scores, n_scores], dim=1)
            labels = torch.zeros(logits.size(0), dtype=torch.long, device=device)
            
            loss = nn.CrossEntropyLoss()(logits, labels)
            val_loss += loss.item()
    return val_loss / len(val_loader)

def train_model(train_loader, val_loader, model, device, candidate_path: str) -> float:
    optimizer = optim.Adam(model.parameters(), lr=LR)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    best_loss = float('inf')
    patience_counter = 0

    for epoch in range(EPOCHS):
        model.train()
        for u_batch, pos_v_batch, neg_v_batch in train_loader:
            u_batch = u_batch.to(device)
            pos_v_batch = pos_v_batch.to(device)
            neg_v_batch = neg_v_batch.to(device)
            
            optimizer.zero_grad()
            
            u_emb, p_emb = model(u_batch, pos_v_batch)
            b, n, _ = neg_v_batch.size()
            _, n_emb = model(u_batch, neg_v_batch.view(-1, neg_v_batch.size(-1)))
            n_emb = n_emb.view(b, n, 128)
            
            p_scores = (u_emb * p_emb).sum(dim=1).unsqueeze(1) / 0.07
            n_scores = (u_emb.unsqueeze(1) * n_emb).sum(dim=2) / 0.07
            
            logits = torch.cat([p_scores, n_scores], dim=1)
            labels = torch.zeros(logits.size(0), dtype=torch.long, device=device)
            
            loss = nn.CrossEntropyLoss()(logits, labels)
            
            loss.backward()
            optimizer.step()
            
        val_loss = evaluate_model(model, val_loader, device)
        scheduler.step()
        
        logger.info(f"Epoch {epoch+1}/{EPOCHS} completed | Val Loss: {val_loss:.4f} | Best Loss: {best_loss:.4f}")
        
        if val_loss < best_loss:
            best_loss = val_loss
            patience_counter = 0
            model.save(candidate_path)
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE: break
            
    return best_loss

async def generate_and_save_video_embeddings(conn, model):
    query = "SELECT id, view_count, like_count, avg_watch_ratio, created_at, duration_sec FROM videos WHERE status = 'READY' AND privacy = 'PUBLIC'"
    videos = await conn.fetch(query)
    now = datetime.utcnow()
    for i in range(0, len(videos), 500):
        batch = videos[i:i+500]
        vid_ids = [v['id'] for v in batch]
        tag_map = await load_video_tags(conn, vid_ids)
        embeddings = []
        for v in batch:
            vid = v['id']
            created_at = v['created_at']
            if created_at.tzinfo:
                created_at = created_at.replace(tzinfo=None)
                
            age_norm = min((now - created_at).total_seconds() / 3600.0, 7200) / 7200.0
            emb = model.encode_video(
                tag_map.get(vid, []), math.log1p(v['view_count'] or 0),
                (v['like_count'] or 0) / max(v['view_count'] or 1, 1),
                float(v['avg_watch_ratio'] or 0.0), age_norm, min(v['duration_sec'] or 0.0, 600) / 600.0
            )
            padded = np.zeros(256, dtype=np.float32)
            padded[:128] = emb
            vec_str = '[' + ','.join(map(str, padded)) + ']'
            embeddings.append((vid, vec_str, now))
        upsert_query = "INSERT INTO video_tag_vectors (video_id, vector, updated_at) VALUES ($1, $2::vector, $3) ON CONFLICT (video_id) DO UPDATE SET vector = EXCLUDED.vector, updated_at = EXCLUDED.updated_at"
        await conn.executemany(upsert_query, embeddings)

async def run_training_cycle(pool):
    if training_lock.locked():
        logger.info("Training cycle already in progress, skipping...")
        return

    async with training_lock:
        logger.info("Starting training cycle.")
        try:
            async with pool.acquire() as conn:
                vocab = await load_vocab(conn)

                # --- NLP Hybrid Addition ---
                logger.info("Loading semantic tags for NLP embeddings...")
                from sentence_transformers import SentenceTransformer
                nlp_model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
                tag_names = await conn.fetch("SELECT id, name FROM tags")
                cat_names = await conn.fetch("SELECT id, name FROM categories")

                text_mapping = {}
                for r in tag_names: text_mapping[str(r['id'])] = r['name']
                for r in cat_names: text_mapping[str(r['id'])] = r['name']

                # Batch encode all tags in one forward pass instead of one-by-one
                tag_ids_list = list(vocab.keys())
                texts = [text_mapping.get(tid, "unknown").replace("-", " ").strip() for tid in tag_ids_list]
                logger.info(f"Encoding {len(texts)} tags/categories in a single batch...")
                all_embs = nlp_model.encode(texts, batch_size=64, show_progress_bar=True)
                tag_embeddings = {tid: np.array(emb, dtype=np.float32) for tid, emb in zip(tag_ids_list, all_embs)}
                logger.info(f"Tag embeddings ready: {len(tag_embeddings)} vectors.")
                # --------------------------

                records = await load_training_data(conn)
                logger.info(f"Fetched {len(records)} events from DB.")

                vid_ids = list(set(r['video_id'] for r in records))
                logger.info(f"Loading metadata for {len(vid_ids)} unique videos...")
                video_tag_map = await load_video_tags(conn, vid_ids)
                
                logger.info("Building training dataset and negative sampling...")
                pairs, video_features = prepare_dataset(records, vocab, video_tag_map)

                pos_pairs = [p for p in pairs if p['is_positive']]
                positive_count = len(pos_pairs)
                logger.info(f"Generated {len(pairs)} pairs total, {positive_count} are positive.")

                if positive_count < 1000:
                    logger.warning(f"Only {positive_count} positive pairs, skipping training (need 1000)")
                    return

                ds = TwoTowerDataset(pos_pairs, video_features, vocab, len(vocab), tag_embeddings)
                v_sz = int(len(ds) * VAL_SPLIT)
                t_ds, v_ds = torch.utils.data.random_split(ds, [len(ds)-v_sz, v_sz])
                t_loader = torch.utils.data.DataLoader(t_ds, batch_size=BATCH_SIZE, shuffle=True)
                v_loader = torch.utils.data.DataLoader(v_ds, batch_size=BATCH_SIZE)

                model = TwoTowerModel(vocab, tag_embeddings=tag_embeddings)
                cand_loss = train_model(t_loader, v_loader, model, torch.device('cpu'), CANDIDATE_PATH)

                os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

                replaced = False
                if os.path.exists(MODEL_PATH):
                    try:
                        existing_model = TwoTowerModel.load(MODEL_PATH)
                        existing_val_loss = evaluate_model(existing_model, v_loader, torch.device('cpu'))
                        if cand_loss < existing_val_loss * 0.999:
                            os.replace(CANDIDATE_PATH, MODEL_PATH)
                            replaced = True
                    except RuntimeError as e:
                        logger.warning(f"Could not load existing model, likely architecture change: {e}. Replacing with new model.")
                        os.replace(CANDIDATE_PATH, MODEL_PATH)
                        replaced = True
                else:
                    if os.path.exists(CANDIDATE_PATH):
                        os.replace(CANDIDATE_PATH, MODEL_PATH)
                        replaced = True

                if replaced:
                    logger.info("New model selected and replaced the previous one.")
                    best = TwoTowerModel.load(MODEL_PATH)
                    await generate_and_save_video_embeddings(conn, best)
                else:
                    logger.info("New model did not improve >0.1% over existing model. Kept old model.")
        except Exception as e:
            logger.error(f"Error during training cycle: {e}")

async def event_monitor_loop(pool):
    import redis.asyncio as redis
    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    while True:
        try:
            async with pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM events")
            
            milestones = [5000, 10000, 50000]
            for m in milestones:
                if count >= m:
                    key = f"aurora:milestone:{m}"
                    already_triggered = await redis_client.get(key)
                    if not already_triggered:
                        await redis_client.set(key, "1")
                        logger.info(f"Event milestone {m} crossed, triggering immediate training")
                        asyncio.create_task(run_training_cycle(pool))
                        break
        except Exception as e:
            logger.error(f"Event monitor error: {e}")
        await asyncio.sleep(60)

async def training_loop(pool):
    # Trigger an immediate training cycle on container startup
    await run_training_cycle(pool)
    
    while True:
        interval_hours = float(os.getenv("TWO_TOWER_RETRAIN_INTERVAL_HOURS", "6"))
        await asyncio.sleep(interval_hours * 3600)
        await run_training_cycle(pool)

async def main():
    pool = await get_db_pool()
    await asyncio.gather(
        training_loop(pool),
        event_monitor_loop(pool),
    )

if __name__ == "__main__":
    asyncio.run(main())
