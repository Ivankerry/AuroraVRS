# AuroraVRS Backend Model Specification (Detailed, Project-Specific)

## 1. Scope and Intent
This document describes the recommendation model system implemented in this backend project, not a generic AI model description.

It covers:
- The serving model used by the API
- Candidate generation and scoring logic
- Training pipeline in the worker service
- Indexing/caching/runtime behavior
- Data contracts (tables, fields, thresholds)
- Explicit non-ambiguous constants and decision rules
- Known implementation caveats found in the current code

Evidence base used:
- api/main.py
- api/core/two_tower.py
- api/core/ranking.py
- api/core/faiss_index.py
- api/routers/feed.py
- api/routers/events.py
- worker/two_tower_trainer.py
- api/migrations/init.sql
- docker-compose.yml
- api/Dockerfile and worker/Dockerfile
- tests/test_ranking_hmm.py

Date captured: 2026-04-22 (updated after HMM interest-vector migration)

---

## 2. High-Level Model Architecture

### 2.1 System type
AuroraVRS uses a hybrid recommendation stack:
1. Retrieval model: Two-Tower neural model (PyTorch)
2. ANN retrieval index: FAISS IndexFlatIP (inner product)
3. Rule-based + statistical ranking layer: SQL candidate blending + normalized engagement + interest similarity + viral multiplier + creator affinity boost
4. Fallback mode: non-ML SQL candidate generation and cold-start random feed
5. Creator affinity layer: follow/like/save/comment events update per-creator preference scores

### 2.2 Core concept
The model predicts user-video affinity by embedding users and videos into a shared 128-dimensional normalized vector space.
- User embedding and video embedding are produced by separate towers.
- Similarity is dot product (cosine-like because embeddings are L2-normalized).
- Retrieval uses FAISS over video embeddings.
- Final ordering is not pure model score; it is a weighted blend with engagement metrics and viral multipliers.

---

## 3. Runtime Components and Responsibilities

### 3.1 API service
Runs FastAPI and performs:
- Loading the latest Two-Tower model from /app/storage/models/two_tower.pt at startup
- Building/rebuilding a FAISS index from stored video vectors or on-the-fly model encoding fallback
- Serving /api/v1/feed with either ML path or fallback path
- Admin ML controls:
  - POST /api/v1/ml/reload-model
  - POST /api/v1/ml/rebuild-index
  - GET /api/v1/ml/status

### 3.2 Worker service
Runs training continuously via two_tower_trainer.py and performs:
- Periodic retraining loop (default every 6 hours from env)
- Event milestone-triggered retraining at counts 5000, 10000, 50000
- Candidate model evaluation and replacement only if improved
- Regeneration and upsert of per-video vectors into Postgres pgvector table

### 3.3 Data stores
- Postgres (pgvector enabled): canonical persistence for events, user vectors, video vectors, metadata
- Redis: low-latency cache/state for interest vectors, feed pages, trending leaderboards, rollout state, viral tiers

---

## 4. Exact Two-Tower Model Definition

### 4.1 Neural model class
Implemented in api/core/two_tower.py as TwoTowerModel.

### 4.2 Embedding dimensions and learned latent tables
- user_latent: Embedding(20000, 64)
- video_latent: Embedding(20000, 64)
- Hash trick maps raw IDs into [0, 19999] using md5(id) mod 20000

### 4.3 User tower input layout
User content features before latent concat:
- 384 dims: weighted semantic tag/category embedding aggregate
- 2 dims: user metadata
  - normalized event_count
  - normalized account_age_days

After latent concat:
- 384 + 2 + 64 = 450 input dims to user tower MLP

User tower MLP:
- Linear(450, 256) + ReLU + Dropout(0.2)
- Linear(256, 256) + ReLU
- Linear(256, 128)
- L2 normalization

### 4.4 Video tower input layout
Video content features before latent concat:
- 384 dims: mean semantic tag/category embedding aggregate
- 5 dims: video metadata
  - log-scaled view count
  - like rate
  - avg watch ratio
  - age normalization
  - duration normalization

After latent concat:
- 384 + 5 + 64 = 453 input dims to video tower MLP

Video tower MLP:
- Linear(453, 256) + ReLU + Dropout(0.2)
- Linear(256, 256) + ReLU
- Linear(256, 128)
- L2 normalization

### 4.5 Inference outputs
- encode_user returns 128-d numpy vector
- encode_video returns 128-d numpy vector
- score returns dot product

### 4.6 Persistence format
Model checkpoint includes:
- model_state
- tag_vocab
- num_tags
- tag_embeddings (semantic vectors)

Stored at:
- Primary: /app/storage/models/two_tower.pt
- Candidate during training: /app/storage/models/two_tower_candidate.pt

---

## 5. Feature Engineering Details

### 5.1 Semantic tag embeddings
Training pipeline computes tag/category semantic embeddings using sentence-transformers model all-MiniLM-L6-v2.
- Tags and categories are encoded in batch.
- Resulting vectors are used as fixed 384-d semantic inputs.
- Text source: tag/category names from DB.

### 5.2 User content features
From user_interest_vectors.tag_weights JSONB plus metadata:
- Weighted average of semantic vectors for weighted tags/categories
- event_count normalized to [0,1] by min(event_count/10000, 1)
- account age normalized to [0,1] by min(days/365 or /3650 depending context)

Note on normalization inconsistency:
- In API inference encode_user uses account_age_days/365.
- In training dataset preparation account age uses /3650.
This mismatch may shift user feature scale between train and inference.

### 5.3 Video content features
From video metadata + tags/categories:
- view_count transformed with log1p then normalized
- like_rate = like_count / max(view_count,1)
- avg_watch_ratio direct
- age normalized with cap
- duration normalized with cap

---

## 6. Training Pipeline (Worker)

### 6.1 Data extraction
Training records query pulls up to 100000 recent events where event_type in:
- VIEW, LIKE, SHARE, DISLIKE, SKIP

Joined tables include:
- user_interest_vectors
- users
- videos

### 6.2 Positive/negative definition
A record is positive if:
- event_type in LIKE or SHARE
- OR event_type is VIEW and watch_ratio >= 0.5

DISLIKE and SKIP are not used as direct supervised negatives in the final dataset.
They pass through prepare_dataset but final dataset keeps only positive pairs.
Negative samples are random videos (4 per positive).

### 6.3 Sampling and objective
For each positive pair:
- 1 positive video
- 4 random negatives (not equal to positive)

Loss formulation:
- InfoNCE-like softmax over [positive_score, negative_scores]
- Temperature scaling by dividing logits by 0.07
- CrossEntropy loss with class 0 as positive

### 6.4 Hyperparameters
- batch size: 256
- epochs: 20
- learning rate: 0.001
- validation split: 0.2
- early stopping patience: 3
- scheduler: CosineAnnealingLR with T_max = EPOCHS

### 6.5 Minimum data gate
Training is skipped unless positive pairs >= 1000.

### 6.6 Model replacement rule
If existing model exists:
- Candidate replaces existing only if candidate_val_loss < existing_val_loss * 0.999
- This is strict >0.1% relative improvement requirement

If existing model cannot be loaded due to architecture mismatch:
- Candidate replaces existing.

### 6.7 Post-training embedding regeneration
When model is selected:
- Generates embeddings for all READY + PUBLIC videos
- Writes to video_tag_vectors.vector (pgvector(256))
- Current implementation pads 128-d model output into 256-d vector with trailing zeros

---

## 7. Retrieval and Candidate Generation in Serving

### 7.1 ML retrieval eligibility gate
ML retrieval path in feed endpoint runs only if all are true:
- model loaded
- authenticated user present
- user event_count >= MIN_EVENTS_FOR_MODEL
- FAISS index exists and is ready

MIN_EVENTS_FOR_MODEL default is 5000 via env and ranking.py constant.

### 7.2 FAISS index details
- Index type: faiss.IndexFlatIP
- Vector dimension used: 128
- Source vectors:
  - Preferred: video_tag_vectors.vector from DB (first 128 dims used)
  - Fallback at index build time: compute via model.encode_video if vector missing
- Rebuild cadence:
  - Immediate async build on API startup
  - Recurring loop every 1800 seconds (30 minutes)
  - Manual rebuild endpoint for admins

### 7.3 SQL fallback candidate pool
If ML retrieval not used or fails, candidates come from blended SQL sources:
1. Trending videos from Redis leaderboard
2. Followed creators
3. Top-interest tag similarity random pool
4. Regional pool by user location
5. Discovery pool with rollout-stage constraints

Creator affinity is now also used as a candidate source:
- The API stores user_creator_affinity rows for follow, like, save, share, comment, dislike, skip, and unfollow events.
- The feed candidate generator pulls recent public videos from the user's highest-affinity creators even when the ML path is active.
- Followed creators are guaranteed to survive candidate generation through the explicit followed-creator branch and creator-affinity branch.

Candidates are deduplicated by video ID and filtered against seen IDs.

---

## 8. Final Ranking Formula (Serving)

### 8.1 Metric normalization
For the candidate pool, per-video metrics are computed:
- watch_ratio
- like_rate
- comment_rate
- share_rate
- save_rate

Each metric is min-max normalized within that candidate pool.
If max == min, normalized value is set to 0.5.

### 8.2 Similarity term
If user embedding and video embedding exist:
- similarity = dot(user_emb, video_emb[:128])

Else fallback similarity:
- Sum user interest weights over video tag_ids + category_ids
- Clamped to [0,1]

### 8.3 Engagement term
eng_score =
- 0.35 * normalized_watch
- 0.25 * normalized_save
- 0.20 * normalized_share
- 0.13 * normalized_comment
- 0.07 * normalized_like

### 8.4 Base score and penalties
base_score = 0.5 * similarity + 0.5 * eng_score

Low-retention penalty:
- If watch_ratio < 0.1 then base_score -= 1.0

Creator preference boost:
- Videos from creators with positive user_creator_affinity get an additive bonus before the viral multiplier is applied.
- Follow events carry the strongest positive creator-affinity weight.
- The old heuristic discovery-stage follower check has been removed in favor of explicit follow and affinity-driven candidate sources.

### 8.5 Viral multiplier
final_score = base_score * viral_multiplier

viral_multiplier from Redis viral tier key:
- WATCH: 1.5
- HOT: 2.0
- VIRAL: 3.0
- MEGA_VIRAL: 5.0
- Missing tier: 1.0

### 8.6 Output
Videos sorted descending by final_score.
Feed response returns top limit and has_more flag.

---

## 9. Event Ingestion and Online Learning Signals

### 9.1 Event ingestion endpoint
POST /api/v1/events writes event and updates online state.

### 9.2 Interest vector online update
update_interest_vector now delegates to update_interest_vector_hmm and stores tag weights as a probability distribution.

Event-to-signal mapping is unchanged:
- VIEW: watch_ratio
- WATCH: watch_ratio
- LIKE: 0.6
- SAVE: 1.2
- SHARE: 1.0
- SKIP: -0.5
- DISLIKE: -1.0
- COMMENT: 0.4

Legacy normalization behavior:
- If incoming weights are not a valid probability distribution, normalize_to_probability_distribution converts them to [0.0, 1.0] and enforces sum=1.0.
- Conversion path is stable softmax-based for arbitrary/legacy values, followed by floor-safe projection.

HMM step-size behavior:
- event_count < 50: alpha = 0.8
- event_count >= 50: alpha = 0.2
- Watch override: for VIEW/WATCH with signal >= 0.6, alpha is forced to 0.5.

HMM redistribution behavior (equal-exit mass transfer):
- Positive signal: target tags gain probability mass; non-target tags lose mass equally.
- Negative signal: target tags lose probability mass; non-target tags gain mass equally.
- The system enforces strict probability invariants after every update.

Safety valves implemented in ranking.py:
- Probability floor: each tag remains >= 0.02 (PROBABILITY_FLOOR).
- Sum invariant: probabilities are corrected to total exactly 1.0 (floating drift corrected).
- Division-by-zero resistant for empty/single-tag vectors.
- New tags introduced mid-session are seeded without violating floor or sum constraints.

Stored in:
- Redis iv:user_id (TTL 24h)
- Postgres user_interest_vectors.tag_weights

### 9.2.1 Creator affinity online update
Creator-following preference is tracked separately from tag affinity.
- Stored in Redis creator_affinity:user_id and Postgres user_creator_affinity.
- FOLLOW: +3.0
- LIKE: +1.0
- SAVE: +1.5
- SHARE: +1.25
- COMMENT: +0.5
- DISLIKE: -2.0
- SKIP: -0.5
- UNFOLLOW: -3.0

This allows the system to recommend posts from specific creators even when their content tags differ from the user's topic history.

### 9.3 Trending and viral detection
Each event maps to engagement velocity value and updates Redis sorted set trending:region.
Then z-score tiering is computed from current leaderboard scores:
- z > 2: WATCH
- z > 5: HOT
- z > 10: VIRAL
- z > 15: MEGA_VIRAL

Tiers are cached for short TTL and can trigger proactive feed cache invalidation for viral surges.

---

## 10. Rollout/Exploration Controls

### 10.1 Stage tracking
Redis keys manage rollout stage and serve counts per video.
- rollout_stage:video_id
- rollout_count:video_id
- rollout_failed set

### 10.2 Advancement thresholds
Stage thresholds in evaluate_rollout_advancement:
- Stage 1 requires watch > 0.4 and like_rate >= 0.0, max audience 500
- Stage 2 requires watch > 0.5 and like_rate >= 0.05, max audience 5000
- Stage 3 requires watch > 0.6 and like_rate >= 0.08, max audience 50000

Pass condition advances stage by 1.
If audience cap hit without pass, video added to rollout_failed for 24h.

### 10.3 Discovery insertion logic
Discovery query includes low-view or recent videos and applies rollout filters.
Popular videos (view_count >= 100) are grandfathered to stage 4.

---

## 11. Feed Caching and Session Behavior

### 11.1 Seen-session dedupe
For authenticated users:
- session:user_id stores seen video IDs in Redis
- Keeps last 1000 IDs
- TTL 600s

### 11.2 Feed cache
Per page cache key:
- feed_cache:user_id:page

TTL policy by viral tier in returned page:
- VIRAL or MEGA_VIRAL present: 20s
- HOT or WATCH present: 60s
- otherwise: 300s

### 11.3 Cache invalidation
Triggered by:
- Certain user events (LIKE/SHARE/SAVE) via clear_user_feed_cache
- Follow and unfollow actions via clear_user_feed_cache
- Viral promotion logic for high z-score videos

---

## 12. Data Schema Required by the Model

### 12.1 Key tables
- events
- user_interest_vectors (vector(256), tag_weights JSONB, event_count)
- video_tag_vectors (vector(256))
- videos
- video_tags
- video_categories
- tags
- categories

### 12.2 Vector shape contract
- TwoTower runtime embedding size: 128
- Database vector columns: 256
- Current convention: store 128 in first half, zero pad remaining 128
- FAISS retrieval/search uses first 128 dimensions

---

## 13. Deployment and Runtime Topology

### 13.1 Containers
From docker-compose:
- db: pgvector-enabled Postgres image
- redis
- api
- worker
- nginx

### 13.2 Shared model path contract
Both API and worker mount ./models to /app/storage/models.
This is how worker-produced model files become visible to API reload/startup logic.

### 13.3 CPU-only stack
Both API and worker Dockerfiles install torch CPU wheels.
FAISS CPU installed in API image.

---

## 14. Admin and Operability Endpoints

### 14.1 ML status
GET /api/v1/ml/status returns:
- model_loaded boolean
- model_path
- faiss_size
- faiss_ready
- min_events_threshold
- two_tower_active

### 14.2 Model control
- POST /api/v1/ml/reload-model: reloads model from disk
- POST /api/v1/ml/rebuild-index: reloads model and triggers async FAISS rebuild

Both require admin auth dependency.

---

## 15. Explicit Constants and Thresholds Summary

- MIN_EVENTS_FOR_MODEL default: 5000
- Retrain interval default: 6 hours
- Event milestone triggers: 5000, 10000, 50000
- FAISS rebuild interval: 30 minutes
- Two-tower output dim: 128
- DB vector dim: 256 (padded storage)
- Negative samples per positive: 4
- Positive event logic: LIKE/SHARE/VIEW>=0.5
- Skip training if positives < 1000
- Candidate replace condition: >0.1% val loss improvement
- Interest-vector probability floor: 0.02
- HMM alpha values: 0.8 (cold), 0.2 (stable), 0.5 (high-watch override)

---

## 16. Known Caveats and Ambiguity Elimination Notes

This section lists concrete implementation caveats to prevent misunderstanding.

1. API docs drift
The repository detailed_api_docs.md mentions a lower ML threshold in prose, but current runtime gate in code is 5000 events. Use code as source of truth.

2. Train/inference feature scaling mismatch
Account age normalization differs between trainer dataset and API encode_user path.

3. Negative feedback underuse in supervised target
DISLIKE and SKIP are ingested but not directly used as labeled negatives in final training dataset (training keeps positives only + sampled negatives).

4. Discovery and follow behavior are explicit
Followed creators and creator-affinity creators are now injected directly into candidate generation, so the feed does not rely on the old heuristic follower check.

5. Vector dimensional duality
Storage vectors are 256-d while model and FAISS logic use 128 effective dims.

6. CORS is open
API CORS currently allows all origins, methods, headers. This is operationally permissive and should be reviewed for production hardening.

7. Training feature expectation vs serving vector semantics
The two-tower user encoder consumes tag_weights as weighted inputs. After HMM migration, these weights are now normalized probabilities with a floor, not the prior signed EMA range. This is intentional but changes input distribution characteristics.

---

## 17. End-to-End Request-Time Flow (Authenticated User)

1. Client calls GET /api/v1/feed.
2. API attempts feed_cache:user:page hit.
3. If miss, loads user interest vector and metadata.
4. Checks ML gate (model loaded + event count >= threshold + FAISS ready).
5. If gate passes:
   - Encodes user embedding.
   - Retrieves candidate IDs from FAISS.
   - Loads candidate rows from SQL.
6. If gate fails:
   - Uses SQL blended candidate generation.
7. Merges creator-affinity candidates so followed or heavily liked creators still contribute directly.
8. Computes final score with similarity + normalized engagement + creator boost + penalties + viral multiplier.
9. Sorts, truncates to limit, enriches viral tier, strips internal fields.
10. Updates seen session and feed cache with tier-aware TTL.
11. Returns videos + has_more + next_cursor.

---

## 18. End-to-End Training Flow

1. Worker starts and immediately triggers run_training_cycle.
2. Loads vocab from tags + categories.
3. Encodes semantic embeddings for all vocab IDs via sentence-transformers.
4. Loads recent events and joined features.
5. Builds positive pairs and random negatives.
6. Trains candidate model with validation and early stopping.
7. Compares candidate to existing model via validation loss threshold.
8. Replaces model if improved enough.
9. Regenerates video vectors and upserts into video_tag_vectors.
10. Continues periodic loop and milestone-triggered retraining.

---

## 19. Practical Definition of “The Model” in This Backend

In this repository, the phrase the model should be interpreted as:
- The TwoTowerModel neural architecture + learned checkpoint
- The semantic tag embedding generation process used to build features
- The FAISS retrieval index built from video vectors
- The ranking policy that combines model similarity with engagement and viral heuristics

It is not only a single .pt file; it is a full retrieval-plus-ranking system.

---

## 20. Recommended Verification Commands (Optional)

If you want runtime confirmation rather than static code reading, verify with:
- Run one-command end-to-end smoke test (no pre-existing videos required):
  - pwsh -ExecutionPolicy Bypass -File scripts/smoke_hmm_e2e.ps1
- If you do not have Docker Compose, run API-only mode (requires backend already running):
  - pwsh -ExecutionPolicy Bypass -File scripts/smoke_hmm_e2e.ps1 -NoDocker -BaseUrl http://localhost:8080
- GET /health
- GET /api/v1/ml/status (admin token)
- POST /api/v1/ml/reload-model (admin token)
- POST /api/v1/ml/rebuild-index (admin token)
- Compare feed behavior for users below and above event threshold
- Run deterministic math tests:
  - c:/Users/dev/Desktop/AuroraVRS/.venv/Scripts/python.exe -m pytest tests/test_ranking_hmm.py

---

## 21. Deterministic Test Coverage for HMM Updater

Implemented in tests/test_ranking_hmm.py.

Covered scenarios:
- Sum invariant using math.isclose after positive and negative updates.
- Hard floor behavior under repeated negative events.
- Legacy normalization from non-probability vectors.
- Watch override behavior for high watch_ratio events.
- Empty vector initialization.
- Single-tag no-crash behavior.
- New tag introduction preserving floor and total mass.

---

## 22. Final Non-Ambiguous Summary

- Primary ML model: PyTorch two-tower recommender with 128-d normalized embeddings.
- Serving retrieval: FAISS IndexFlatIP over first 128 dims of stored video vectors.
- Final rank: 50% similarity + 50% normalized engagement, then penalties and viral multiplier.
- Online adaptation: event-driven alpha-beta HMM probability updates in Redis + Postgres.
- Offline updates: worker retraining loop with candidate-vs-current validation gate.
- Gate to use ML retrieval: authenticated user with event_count >= 5000 and ready model/index.
- Fallback behavior exists at every critical stage for resilience.

End of specification.
