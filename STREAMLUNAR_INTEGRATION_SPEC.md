# AURORA VRS → StreamLunar Microservice Integration Specification

**Document Purpose**: This specification requests critical information from StreamLunar platform team required to transform AURORA VRS into a microservice-ready component.

**Target Audience**: StreamLunar Platform Engineering, DevOps, Data, and Product teams.

**Status**: Implementation Reference

---

## AURORA VRS: Internal Recommendation Service Overview

### What AURORA VRS Is

AURORA (Adaptive User Recommendation and Ranking Online Algorithm) is a production-ready video recommendation microservice. In the StreamLunar architecture, it is an internal ranking engine, not a user-facing product and not a standalone backend.

### What AURORA Owns

- Real-time recommendation ranking
- HMM interest vector updates
- Two-Tower model inference and retraining
- FAISS candidate retrieval
- Trending and viral tier scoring
- Feed session state and recommendation caching
- AURORA-owned PostgreSQL tables and Redis state

### What StreamLunar Owns

- User identity and authentication
- Video hydration and client-facing GraphQL responses
- Engagement writes and background task execution
- Authoritative video metadata in StreamLunar PostgreSQL
- Public API exposure to Flutter clients

### Integration Contract at a Glance

| Area | Contract |
|---|---|
| Caller authentication | StreamLunar sends `X-Service-Token` on every AURORA request |
| User identity | StreamLunar passes `user_id` explicitly; AURORA never receives user JWTs |
| Feed response | AURORA returns ordered video IDs only, not full video objects |
| Event ingestion | StreamLunar forwards engagement events asynchronously to AURORA |
| Video data source | AURORA reads StreamLunar video data from a read-only DB connection |
| AURORA state | AURORA writes to its own DB and Redis only |
| Network exposure | AURORA stays internal to the Docker network; no public port |

### Key Capabilities (Ready Today)

| Capability | What It Does | Impact |
|---|---|---|
| **HMM Interest Vectors** | Tracks user interests as a probability distribution over tags | Real-time personalization |
| **Two-Tower Embeddings** | Generates semantic user/video representations | Better matching beyond simple popularity |
| **FAISS Indexing** | Fast nearest-neighbor retrieval | Low-latency candidate generation |
| **Viral Tier Multipliers** | Applies 1.5x-5.0x boosts to hot content | Surfaces trending content quickly |
| **Rollout Gates** | Staged exposure for new content | Prevents flooding the feed with unvetted content |
| **Redis Caching** | TTL-bound cache with LRU eviction | Predictable memory usage and latency |
| **Event Ingestion** | Accepts VIEW/WATCH/LIKE/SAVE/SHARE/COMMENT/SKIP/DISLIKE | Keeps interest models current |

### What Must Be Confirmed by StreamLunar

- Service token value and environment distribution
- Exact scope of standalone AURORA decommissioning (which endpoints and auth paths are retired, which remain internal)
- Read-only PostgreSQL access for `LUNA_DATABASE_URL`
- Redis DB index reservation for AURORA
- Docker network and service names
- SLA targets, monitoring stack, and compliance rules
- Exact video schema and soft-delete behavior

### Standalone Decommission Questions

**Q0.1**: Which standalone AURORA responsibilities are being removed entirely?
- User registration and login
- Password reset / refresh tokens / logout
- Video upload, registration, delete, and privacy management
- Follow / unfollow / like / dislike / save / comment write endpoints
- Public browser-facing API access
- Any AURORA-owned client UI or admin UI

**Q0.2**: Which AURORA endpoints must remain after decommissioning?
- `GET /health`
- `POST /api/v1/events`
- `GET /api/v1/feed`
- `GET /api/v1/ml/status`
- `POST /api/v1/ml/reload-model`
- `POST /api/v1/ml/rebuild-index`
- `GET /api/v1/misc/tags`
- `GET /api/v1/misc/categories`

**Q0.3**: What is the target feed contract after decommissioning?
- Should AURORA return video IDs only, or video IDs plus debug score metadata?
- Should StreamLunar hydrate all video metadata from its own database?
- Should AURORA ever return thumbnails, titles, creator names, or URLs directly?

**Q0.4**: What is the target event contract after decommissioning?
- Should StreamLunar forward all engagement events asynchronously?
- Should AURORA ever receive user JWTs, or only the explicit `user_id` field?
- Should anonymous users be excluded from forwarding entirely?

**Q0.5**: What is the target identity contract after decommissioning?
- Should AURORA trust only `X-Service-Token` for service authentication?
- Should AURORA ever validate user passwords or user access tokens?
- Should AURORA ever issue tokens to clients?

**Q0.6**: What are the deployment and network rules after decommissioning?
- Must AURORA stay internal-only on the Docker network?
- Must AURORA avoid public port exposure entirely?
- Which Redis DB index belongs to AURORA?
- Which PostgreSQL database is AURORA's source of truth for its own state?

**Q0.7**: What data ownership boundaries are required after decommissioning?
- Which data remains in StreamLunar PostgreSQL and is read-only to AURORA?
- Which AURORA tables remain owned by AURORA only?
- Should AURORA keep any standalone user/video tables at all, or should they be retired?

**Q0.8**: What is the rollback and migration expectation?
- Is there a cutover window where the standalone endpoints continue to work temporarily?
- When should old standalone clients stop working?
- Is a compatibility shim required during migration?

### Architecture Overview

```
Flutter Client
  ↓
StreamLunar GraphQL API
  ↓
Asynq task / resolver call
  ↓
AURORA internal HTTP API
  ↓
AURORA ranking + event processing + retraining
  ↓
StreamLunar hydrates video IDs from its own DB
```

---

## Implementation Status Summary

| Component | Status | Notes |
|---|---|---|
| Event Ingestion & HMM | ✅ IMPLEMENTED | Ready for StreamLunar events |
| Two-Tower Model & Training | ✅ IMPLEMENTED | Worker can retrain on StreamLunar data |
| FAISS Indexing | ✅ IMPLEMENTED | Needs integration with StreamLunar data pipeline |
| Feed Ranking & Scoring | ✅ IMPLEMENTED | Core algorithm complete |
| Trending Detection | ✅ IMPLEMENTED | Z-score viral tier detection working |
| Rollout/Discovery Gates | ✅ IMPLEMENTED | Staged release system ready |
| Redis Caching | ✅ IMPLEMENTED | Memory-safe with TTLs and LRU eviction (recently fixed) |
| **Authentication/AuthZ** | ❌ NOT IMPLEMENTED YET | Needs StreamLunar auth integration |
| **Service-to-Service Auth** | ❌ NOT IMPLEMENTED YET | Adapter needed for StreamLunar auth mechanism |
| **External Service Calls** | ❌ NOT IMPLEMENTED YET | Adapters for user service, video service, etc. |
| **Prometheus Metrics** | ❌ NOT IMPLEMENTED YET | Basic logging exists; needs metric export |
| **Rate Limiting** | ❌ NOT IMPLEMENTED YET | No per-user/per-IP rate limits yet |
| **Multi-Tenant Support** | ❌ NOT IMPLEMENTED YET | Currently single-tenant; needs tenant ID propagation |
| **GDPR/Compliance Hooks** | ❌ NOT IMPLEMENTED YET | Data deletion, audit logging not yet built |
| **Kubernetes Manifests** | ❌ NOT IMPLEMENTED YET | Docker ready, K8s deployment not yet created |

---

## 1. Authentication & Authorization

### Status: ❌ NOT IMPLEMENTED YET

**Current State**: AURORA still contains standalone-era auth assumptions. These must be removed or disabled in microservice mode.

### 1.1 Service-to-Service Authentication

**Current State**: AURORA has no service-to-service auth mechanism. Currently assumes all traffic is trusted.

**Q1.1.1**: What authentication mechanism does StreamLunar use for inter-service communication?
- [ ] OAuth 2.0 (client credentials flow)
- [ ] JWT (signed tokens)
- [ ] API Keys (static or rotated)
- [ ] mTLS (mutual TLS certificates)
- [ ] Other: __________________

**Q1.1.2**: If using JWT, provide:
- Signing algorithm (RS256, HS256, etc.)
- Token issuer URL or endpoint
- Expected token lifetime (TTL)
- Claims structure expected in token
- Sample JWT for reference

**Q1.1.3**: If using API Keys:
- Key format (prefix, length)
- Rotation policy (frequency, grace period)
- Key management system (Vault, Secrets Manager, etc.)
- How are keys provisioned to AURORA container?

**Q1.1.4**: How should AURORA authenticate requests from user-facing clients (mobile apps, web)?
- Should AURORA validate StreamLunar user tokens?
- What claim/field identifies the user?
- Is token validation stateless (JWT) or stateful (session lookup)?
- Provide sample user token structure

**Action Item for AURORA**: Create auth adapter layer in `api/core/auth.py` to validate StreamLunar tokens before processing requests.

---

## 2. User Identity & Context

### Status: ⚠️ PARTIAL (Core logic ready, adapter needed)

### 2.1 User Model Alignment

**Current State**: AURORA has basic user model (user_id, created_at, region in DB). Does NOT validate schema against StreamLunar's user service.

**Q2.1.1**: Provide StreamLunar's user schema:
```json
{
  "user_id": "type and format?",
  "username": "required?",
  "email": "format validation?",
  "created_at": "ISO 8601?",
  "region": "how is it stored? (ISO country code, city, timezone?)",
  "age_group": "optional? (18-25, 26-35, etc?)",
  "language_preference": "ISO 639-1 code?",
  "premium_status": "boolean or tier system?",
  "other_fields": "any additional fields AURORA should know?"
}
```

**Q2.1.2**: User ID uniqueness:
- Is user_id UUID, integer, or string?
- Is it globally unique across all StreamLunar services?
- Can a user have multiple accounts?

**Q2.1.3**: How is user region determined?
- GeoIP from request IP?
- User-selected setting?
- Derived from payment/profile?
- Updated in real-time or cached?

**Q2.1.4**: Does StreamLunar have user segments or cohorts?
- Should AURORA be aware of A/B test groups?
- Are there user tiers (free, premium, enterprise)?
- Should AURORA apply different ranking logic per tier?

### 2.2 Session & Context Passing

**Current State**: AURORA derives user context from database queries. Does NOT accept pre-computed headers or claims from StreamLunar.

**Q2.2.1**: How should AURORA receive user context on each request?
- In HTTP headers? (e.g., `X-User-ID`, `X-Region`)
- In JWT claims?
- Via a context service lookup?
- All of the above?

**Q2.2.2**: Provide the expected header format/claim structure:
```
X-User-ID: <user_id>
X-User-Region: <region_code>
X-Request-ID: <trace_id>  # for correlation
X-User-Premium: <boolean>
Other required headers: _______________
```

**Q2.2.3**: What is the session timeout policy?
- How long is a user considered "active" after last interaction?
- Should AURORA clear session data explicitly or auto-expire?

---

## 3. Video Model & Metadata

### Status: ⚠️ PARTIAL (Ranking ready, schema adapter needed)

### 3.1 Video Schema Alignment

**Current State**: AURORA has flexible video model (id, status, privacy, view_count, like_count, tags, categories). Does NOT validate against StreamLunar schema.

**Action Item**: Create video schema adapter to map StreamLunar videos ↔ AURORA model.
**Q3.1.1**: Provide StreamLunar's video schema:
```json
{
  "video_id": "UUID/string? Must match AURORA's format?",
  "title": "required? max length?",
  "description": "required? plaintext or HTML?",
  "creator_id": "user_id of uploader?",
  "duration_seconds": "required? max value?",
  "created_at": "ISO 8601?",
  "published_at": "different from created_at?",
  "thumbnail_url": "required? CDN format?",
  "video_url": "HLS stream, MP4, other?",
  "privacy": "PUBLIC, UNLISTED, PRIVATE, etc?",
  "content_rating": "G, PG, PG-13, R, etc? or custom?",
  "category_id": "required? single or array?",
  "tags": "array of strings? max length? auto-generated or user-provided?",
  "language": "ISO 639-1? required?",
  "transcription": "available? for ranking?",
  "view_count": "denormalized in video record? or separate stats service?",
  "like_count": "same as above?",
  "comment_count": "same as above?",
  "other_fields": "format, resolution, captions, etc?"
}
```

**Q3.1.2**: How does video metadata evolve?
- Are video_id, creator_id, created_at immutable?
- Can title, description, tags be edited? How often?
- Does AURORA need real-time sync or batch updates?

**Q3.1.3**: Video status & visibility:
- How are "draft", "processing", "ready", "deleted" states represented?
- Should AURORA include private videos in personalized feeds?
- How long after deletion should AURORA ignore a video?

### 3.2 Video Statistics & Engagement

**Current State**: AURORA stores denormalized stats (view_count, like_count, avg_watch_ratio) in videos table. Can query real-time or accept batch updates from external source.

**Q3.2.1**: Where is engagement data (views, likes, comments) stored?
- In the video record (denormalized)?
- In a separate analytics/stats service?
- In a time-series database?

**Q3.2.2**: How real-time do these stats need to be in AURORA?
- Updated on every action (real-time)?
- Batched updates (hourly/daily)?
- Eventual consistency acceptable?

**Q3.2.3**: What is the source of truth for video metrics?
- AURORA stores its own copy? Or queries an external service?
- If external, provide endpoint/API contract

### 3.3 Categories & Tags

**Current State**: AURORA has categories and tags tables with M:N relationships to videos. Can ingest StreamLunar taxonomy without code changes.

**Q3.3.1**: How are categories/tags structured?
```json
{
  "category_id": "UUID or integer?",
  "category_name": "string?",
  "description": "optional?",
  "parent_category_id": "hierarchical? (music > rock > metal)"
}
```

**Q3.3.2**: Are categories fixed or dynamic?
- Can creators invent new tags?
- Is there a curated taxonomy?
- How often are categories updated?

**Q3.3.3**: For ranking purposes:
- Should AURORA favor videos with popular tags?
- Are tags weighted equally or hierarchically?
- Do tags have seasonal/temporal relevance?

---

## 4. Event Streaming & Engagement Tracking

### Status: ✅ IMPLEMENTED (Ready for StreamLunar event format)

**Key Capabilities**:
- ✅ Full event ingestion pipeline (HTTP endpoint accepts events)
- ✅ HMM interest vector calculation on every event
- ✅ Support for VIEW, WATCH, LIKE, SKIP, DISLIKE, COMMENT, SAVE, SHARE, REPORT
- ✅ Event storage in PostgreSQL
- ✅ Real-time ranking updates

### 4.1 Event Model & Ingestion

**Current State**: AURORA fully implements event ingestion with complete event type support. HMM interest vector calculation is production-ready.
**Q4.1.1**: What events should AURORA track?
- [ ] VIEW (user watched video)
- [ ] WATCH (user watched entire/most of video)
- [ ] LIKE
- [ ] DISLIKE
- [ ] SHARE
- [ ] COMMENT
- [ ] SAVE/BOOKMARK
- [ ] SKIP
- [ ] REPORT
- [ ] Other: __________________

**Q4.1.2**: Provide the event schema:
```json
{
  "event_id": "UUID?",
  "event_type": "string",
  "user_id": "who triggered event?",
  "video_id": "what was engaged with?",
  "timestamp": "ISO 8601 UTC?",
  "client_info": {
    "platform": "WEB, iOS, Android?",
    "version": "app version?",
    "user_agent": "browser string?"
  },
  "context": {
    "watch_ratio": "0-1 float? required for WATCH events?",
    "duration_watched_sec": "optional?",
    "ip_address": "for geo tracking?",
    "session_id": "optional?"
  },
  "other_fields": "_______________"
}
```

**Q4.1.3**: How are events delivered to AURORA?
- [x] Direct HTTP POST from client to AURORA ← **AURORA fully supports this**
- [ ] Message queue (Kafka, RabbitMQ, SQS) ← **NOT IMPLEMENTED** (needs adapter)
- [ ] Event bus (CDC, pub/sub) ← **NOT IMPLEMENTED** (needs adapter)
- [ ] Batch import (daily/hourly) ← **AURORA can do this via script**

**Q4.1.4**: If using a message queue:
- Queue name/topic format
- Partition key strategy (by user_id, video_id, region?)
- Retention policy (how long are events kept?)
- Expected throughput (events/sec)

### 4.2 Real-Time vs. Batch

**Current State**: AURORA supports both modes:
- **Real-time**: HTTP events processed immediately, interest vectors update within seconds
- **Batch**: Two-tower model retrains on schedule (default 6h), triggered by event milestones (5k, 10k, 50k events)

**Q4.2.1**: What is StreamLunar's requirement for event freshness in AURORA?
- Real-time ranking (events affect feed within seconds)?
- Near real-time (minutes)?
- Batch (hourly/daily)?

**Q4.2.2**: Should AURORA update ranking immediately on event or batch?
- Per-event updates: higher latency, more computation
- Batch updates: lower latency, but feed may be slightly stale

**Q4.2.3**: How should AURORA handle backpressure if event rate spikes?
- Queue and process async?
- Drop events with error response?
- Reject with rate-limit response?

### 4.3 User Interests & Tags

**Current State**: AURORA fully implements HMM interest vector tracking. Updates on every event in real-time. Stores in Redis cache (30d TTL) + Postgres durable copy.

**Q4.3.1**: For HMM interest vector calculation, which tags should AURORA track?
- StreamLunar's category tags?
- Creator-provided tags?
- ML-extracted tags (NLP on transcript)?
- All of the above?

**Q4.3.2**: Are tags subject to change?
- Can new tags be added to a video after creation?
- If so, how should AURORA update interest vectors retroactively?

---

## 5. Feed Generation & Response Contract

### Status: ✅ IMPLEMENTED (Endpoint ready, response format adapter needed)

**Key Capabilities**:
- ✅ Fully functional `/api/v1/feed` endpoint (paginated, personalized)
- ✅ Multiple candidate pools (trending, FAISS semantic search, interest-based, cold-start)
- ✅ Tiered TTL caching (20s-300s based on viral tier)
- ✅ Regional content pooling
- ✅ Viral tier multipliers (1.5x-5x boost)
- ✅ Rollout stage gating (staged video discovery)

**To Integrate with StreamLunar**: Create response adapter to transform AURORA format to StreamLunar expectations.

### 5.1 Feed Endpoint Specification

**Current State**: AURORA has fully functional `/api/v1/feed` endpoint with personalization, cold-start fallback, and regional content pooling.
**Q5.1.1**: Specify the feed endpoint contract AURORA should expose:
```
Method: GET or POST?
Path: /api/v1/feed or /recommend/feed?
Query Params:
  - page: int (page number or cursor?)
  - limit: int (default 20, max?)
  - video_type: string (VIDEO, SHORT, LIVE?) - required or optional?
  - region: string (override user region?)
  - preferences: JSON (personalization override?)
  
Request Headers:
  - Authorization: Bearer <token>?
  - X-User-ID: <user_id>?
  - X-Request-ID: <trace_id>?
  - Accept-Language: <language>?

Request Body (if POST):
  - {json schema}
  
Response Format:
  {
    "videos": [
      {
        "video_id": "...",
        "title": "...",
        ... (full video schema or minimal?)
      }
    ],
    "next_cursor": "...?" (pagination token or page number?)
    "has_more": true/false?
    "expires_at": "cache TTL in epoch seconds?"
  }
```

**Q5.1.2**: What video fields should AURORA return?
- Full video object or subset?
- Minimal set for mobile app (fewer fields):
  ```
  video_id, title, thumbnail_url, duration_seconds, creator_id, 
  view_count, like_count, created_at
  ```
- Extended set for web (more context):
  ```
  above + description, tags, category, language, rating
  ```

**Q5.1.3**: Pagination strategy:
- Offset-based (page 1, 2, 3)?
- Cursor-based (opaque token)?
- Keyset pagination (video_id + score)?
- What is the maximum result limit?

**Q5.1.4**: Should AURORA include metadata about ranking decision?
- Expose which candidate pool each video came from (trending, FAISS, interest-based)?
- Include ranking score?
- Include interest vector match percentage?
- Or is this internal-only (for debugging)?

### 5.2 Ranking Multipliers & Weights

**Current State**: AURORA has all multipliers hardcoded in code. Can be tuned via environment variables. Does NOT have runtime tuning dashboard.

**Hardcoded Values**:
- Viral tier WATCH: 1.5x
- Viral tier HOT: 2.0x
- Viral tier VIRAL: 3.0x
- Viral tier MEGA_VIRAL: 5.0x
- Trending boost: included in scoring function

**Action Item**: If tuning is needed post-launch, implement parameter API or admin dashboard.

**Q5.2.1**: Should AURORA expose tuning parameters to StreamLunar?
- Can engagement velocity weights be adjusted per region?
- Can rollout thresholds be changed per content type?
- Should viral tier multipliers be configurable?

**Q5.2.2**: Are there business rules AURORA must enforce?
- Preference for first-party content (StreamLunar staff)?
- Revenue-sharing tiers (premium creators boosted)?
- Sponsored/promoted video slots?
- Age-gating (R-rated content filtered for minors)?

**Q5.2.3**: Feed diversity requirements:
- Should AURORA avoid showing multiple videos from same creator consecutively?
- Minimum time between videos from same category?
- Preference for video language matching user preference?

### 5.3 Personalization Preferences

**Current State**: AURORA does NOT expose user preferences UI. No blocking, following, or watchlist persistence.

**To Implement if StreamLunar requires**: Add user preference storage (blocks, follows) and filtering logic in ranking.

**Q5.3.1**: Can users control AURORA's ranking behavior?
- Allow users to follow/unfollow creators?
- Block creators or categories?
- Save videos to watchlist (and should AURORA rank saved videos higher)?
- Export watch history?

**Q5.3.2**: Should AURORA respect content preferences?
- Parental controls (strict filtering)?
- Content warnings (show anyway or hide)?

---

## 6. Data Storage & Persistence

### Status: ⚠️ PARTIAL (Infrastructure ready, schema coordination needed)

**Key Capabilities**:
- ✅ PostgreSQL with pgvector extension (for embeddings)
- ✅ Complete schema (users, videos, tags, categories, events, interest vectors)
- ✅ Can run standalone or against shared database
- ✅ Migration scripts included (api/migrations/init.sql)

### 6.1 Database Requirements

**Current State**: AURORA uses PostgreSQL 14+ with pgvector. Schema includes all necessary tables. Can share database with StreamLunar or run isolated.
**Q6.1.1**: Can AURORA use its own PostgreSQL instance, or must it share StreamLunar's database?
- Separate DB: simpler data model isolation
- Shared DB: need coordination on schema, migrations, backups

**Q6.1.2**: If shared DB:
- What schema naming convention? (aurora_*, vrs_*, etc.)
- Who manages schema migrations?
- Backup/recovery SLA same as rest of platform?

**Q6.1.3**: Data retention & compliance:
- How long should AURORA retain events?
- GDPR/CCPA: user data deletion policy?
- Audit log retention?

### 6.2 Model Storage & Versioning

**Current State**: AURORA trains and stores models locally in `/app/storage/models`. Worker container retrains on schedule (6h default) or on event milestone. No A/B testing, rollback, or version control mechanism yet.

**Current Models**:
- two_tower_model.pt (PyTorch, ~50MB)
- faiss_index (binary, scales with catalog size)

**To Integrate**: Define shared model storage location (S3, NFS) if multiple AURORA instances needed.

**Q6.2.1**: Where should trained models (two-tower embeddings, FAISS index) live?
- Shared S3/object storage (CloudFront, etc.)?
- NFS mount on all AURORA instances?
- Baked into container image?

**Q6.2.2**: Model update strategy:
- How often should two-tower retraining happen? (6 hours, daily, weekly?)
- Rollback mechanism if new model performs poorly?
- A/B testing new models?

**Q6.2.3**: FAISS index size & scaling:
- Expected video catalog size? (10k, 100k, 1M?)
- Will model/index size exceed container storage?
- Need GPU for training or CPU-only acceptable?

### 6.3 Caching Strategy

**Current State**: AURORA uses Redis 7 with:
- **Memory**: 512MB cap (configurable)
- **Eviction**: allkeys-lru (least recently used keys evicted first when full)
- **TTLs**: Recently fixed to prevent unbounded growth
  - Interest vectors: 30d TTL
  - Feed pages: 5-300s tiered TTL (depends on viral tier)
  - Viral tiers: 24h TTL
  - Sessions: 4h TTL with 200-entry cap
  - Trending ZSET: 24h TTL, capped at 1000 entries

**Q6.3.1**: Redis configuration:
- Can AURORA use StreamLunar's shared Redis or separate instance?
- Expected concurrency/QPS? (to size Redis memory)
- What is the SLA for cache availability? (Is Redis failure tolerable or must it be highly available?)

**Q6.3.2**: Cache invalidation:
- When a video's metadata changes, who invalidates AURORA's cache?
- When viral status changes, auto-invalidate user feed caches?
- When user interest vector updates, clear their feed cache?

---

## 7. Configuration & Environment

### Status: ⚠️ PARTIAL (Env vars exist, standardization needed)

### 7.1 Environment Variables

**Current State**: AURORA reads standard env vars (DATABASE_URL, REDIS_URL, etc.). Tuning parameters are environment-based but not yet dynamic.

**Current Env Vars**:
```
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://redis:6379/0
VIDEO_STORAGE_PATH=/app/storage/videos
MODEL_STORAGE_PATH=/app/storage/models
TWO_TOWER_RETRAIN_INTERVAL_HOURS=6 (default)
```
**Q7.1.1**: Provide StreamLunar's standardized environment variable naming:
- Database: `DATABASE_URL` or `POSTGRES_HOST`, `POSTGRES_PORT`, etc?
- Redis: `REDIS_URL` or structured?
- Other services: service discovery via env vars or service mesh?

**Q7.1.2**: Feature flags:
- How are feature flags managed? (LaunchDarkly, Unleash, custom?)
- Can AURORA enable/disable ranking components (e.g., disable FAISS fallback to SQL)?

**Q7.1.3**: Tuning parameters to expose:
```
AURORA_INTEREST_VECTOR_TTL_HOURS=24
AURORA_SESSION_TIMEOUT_HOURS=4
AURORA_VIRAL_TIER_TTL_HOURS=24
AURORA_HMM_PROBABILITY_FLOOR=0.02
AURORA_TRENDING_ZSET_CAP=500
AURORA_FAISS_CANDIDATE_LIMIT=100
AURORA_ROLLOUT_STAGE_1_THRESHOLD_WATCH_RATIO=0.4
AURORA_ROLLOUT_STAGE_1_THRESHOLD_LIKE_RATE=0.0
... (others as needed)
```

### 7.2 Service Discovery & Communication

**Status**: ❌ StreamLunar Must Provide

**Current State**: AURORA is stateless with no built-in service discovery. Depends on environment variables for external service URLs.

**To Integrate**: Add client adapters for StreamLunar services if AURORA needs to call them (user service, video service, analytics service).

**Q7.2.1**: How does AURORA discover other StreamLunar services?
- DNS (service.namespace)?
- Environment variables?
- Service mesh (Istio, Linkerd)?
- API gateway with service registry?

**Q7.2.2**: If AURORA needs to call external services (user service, video service, analytics):
- Provide list of services and their endpoints
- Expected response latency SLA?
- Retry/timeout strategy?

### 7.3 Secrets Management

**Status**: ❌ StreamLunar Must Provide

**Current State**: AURORA currently reads secrets from environment variables (insecure for production). No Vault/Secrets Manager integration.

**To Integrate**: Add adapter layer to support StreamLunar's secrets management system (Vault, AWS Secrets Manager, K8s Secrets, etc.).

**Q7.3.1**: How are database passwords, API keys stored?
- Kubernetes Secrets?
- HashiCorp Vault?
- AWS Secrets Manager?
- How are they rotated?

---

## 8. Deployment & Orchestration

### Status: ⚠️ PARTIAL (Docker ready, K8s infrastructure provided by StreamLunar NOT YET SPECIFIED)

**Key Capabilities**:
- ✅ Docker images for API and Worker services
- ✅ Docker Compose for local development (working)
- ✅ Stateless API design (scales horizontally)
- ❌ No Kubernetes manifests
- ❌ No HPA/autoscaling config
- ❌ No health check probes optimized for K8s

### 8.1 Container & Kubernetes

**Status**: ❌ StreamLunar Must Provide K8s Cluster Details

**Current State**: AURORA has functional Dockerfile (API + Worker). Proven with Docker Compose locally.

**To Integrate with StreamLunar K8s**: Create K8s manifests (Deployment, Service, ConfigMap, PDB, HPA).
**Q8.1.1**: What container orchestration does StreamLunar use?
- [ ] Docker Compose (dev only)
- [ ] Kubernetes (which distribution? EKS, GKE, On-prem?)
- [ ] Other: __________________

**Q8.1.2**: If Kubernetes, provide:
- Namespace convention (aurora, vrs, default?)
- Resource quotas/limits (CPU, memory per pod?)
- Node affinity rules (GPU required? specific node pool?)

**Q8.1.3**: Container registry:
- Docker Hub, ECR, GCR, or private registry?
- Image naming convention?
- Tag strategy (latest, v1.0.0, git-sha)?

### 8.2 Scaling & Load Balancing

**Current State**: AURORA is horizontally scalable (stateless API). No autoscaling configuration yet.

**To Integrate**: Define K8s HPA based on CPU/memory metrics or custom QPS metric.

**Q8.2.1**: Expected throughput:
- Peak QPS to feed endpoint?
- Event ingestion rate (events/sec)?
- Concurrent users?

**Q8.2.2**: Scaling strategy:
- Horizontal pod autoscaling (HPA) based on CPU, memory, or custom metric?
- Min/max replicas?
- Scale-down cooldown period?

**Q8.2.3**: Load balancing:
- Round-robin, least-connections, or custom?
- Session affinity needed? (sticky sessions for model cache?)

### 8.3 Startup & Health

**Current State**: AURORA boots in ~5-10 seconds (model loading is async). Has basic `/health` endpoint.

**To Implement for K8s**: Add proper `/live` (liveness) and `/ready` (readiness) probes that report model status.

**Q8.3.1**: Startup requirements:
- How long does AURORA take to boot? (model loading?)
- Should startup block model availability until loaded?
- Graceful degradation if model load fails?

**Q8.3.2**: Health check endpoints:
```
GET /health → { "status": "ok" }
GET /ready → { "ready": true/false } (include model status?)
GET /live → { "alive": true } (used by K8s liveness probe)
```

**Q8.3.3**: Shutdown:
- Graceful shutdown timeout? (30s, 60s?)
- In-flight requests: wait for completion or terminate?

### 8.4 Rolling Updates

**Current State**: AURORA containers are stateless, so rolling updates are safe. Model updates don't need zero-downtime reload.

**Q8.4.1**: Update strategy:
- Blue-green, canary, or rolling?
- How are model updates coordinated? (zero-downtime reload or service restart?)

**Q8.4.2**: Backwards compatibility:
- Can old AURORA instances talk to new backend services?
- Do API contracts need to stay stable for N versions?

---

## 9. Monitoring, Observability & Debugging

### Status: ⚠️ PARTIAL (Basic logging exists, advanced observability NOT IMPLEMENTED YET / Infrastructure provided by StreamLunar)

**Current State**:
- ✅ Logs to stdout (JSON-compatible format)
- ✅ Basic request logging
- ✅ Error tracking and stack traces
- ❌ No Prometheus metrics export
- ❌ No distributed tracing
- ❌ No structured logging aggregation

### 9.1 Logging

**Status**: ❌ StreamLunar Must Provide Logging Infrastructure

**Current State**: AURORA logs to stdout. No centralized log aggregation yet.
**Q9.1.1**: Log format & aggregation:
- JSON structured logs or plain text?
- Log aggregation system (ELK, CloudWatch, Datadog)?
- Log level convention (DEBUG, INFO, WARN, ERROR)?

**Q9.1.2**: Log fields to include:
```json
{
  "timestamp": "ISO 8601 UTC",
  "level": "INFO",
  "service": "aurora-vrs",
  "trace_id": "for request correlation",
  "user_id": "if applicable",
  "message": "...",
  "error": "stack trace if ERROR level"
}
```

**Q9.1.3**: Should AURORA log:
- All feed requests? (very verbose, high volume)
- Only errors and slow queries?
- Sampling strategy for high-volume events?

### 9.2 Metrics & Observability

**Status**: ⚠️ PARTIAL (AURORA needs prometheus-client; StreamLunar must provide metrics infrastructure)

**Current State**: AURORA does NOT expose Prometheus metrics. No metric collection beyond basic logging.

**To Implement**: Add prometheus-client library, expose key metrics (request latency, cache hit rate, ranking scores, event processing rate).

**Q9.2.1**: Metrics framework:
- Prometheus, StatsD, or other?
- Scrape interval?
- Retention period?

**Q9.2.2**: Key metrics to expose:
```
feed_endpoint_requests_total{status, region, user_type}
feed_endpoint_duration_seconds{quantile, region}
feed_cache_hit_ratio{region}
ranking_candidate_source{source: faiss, trending, interest_based, cold_start}
viral_tier_distribution{tier: watch, hot, viral, mega_viral}
rollout_advancement_count{stage}
two_tower_training_duration_seconds
event_ingestion_rate
event_processing_lag_seconds
interest_vector_update_duration_seconds
redis_operations_count{operation, status}
```

**Q9.2.3**: Dashboards:
- Should StreamLunar provide Grafana dashboard template?
- Key visualizations for AURORA health?

### 9.3 Tracing & Debugging

**Status**: ⚠️ PARTIAL (AURORA needs OpenTelemetry integration; StreamLunar must provide tracing backend)

**Current State**: AURORA does NOT emit distributed trace spans. Request correlation exists via X-Request-ID header but no full OpenTelemetry integration.

**To Implement if needed**: Add OpenTelemetry instrumentation for distributed tracing.

**Q9.3.1**: Distributed tracing:
- System in use? (Jaeger, Zipkin, X-Ray?)
- Should AURORA emit trace spans for:
  - Feed request → candidate generation → ranking → response?
  - Interest vector update → HMM calculation → Redis write?
  - Model training → metrics evaluation → deployment?

**Q9.3.2**: Debug endpoints:
- Should AURORA expose `/debug/user/{user_id}` showing:
  - Current interest vector
  - Session state
  - Last 10 recommended videos + scores
- Security: who can access debug endpoints? (admins only?)

---

## 10. Rate Limiting & SLAs

### Status: ❌ NOT IMPLEMENTED YET (AURORA needs implementation; StreamLunar must specify SLA/rate limit policy)

**Current State**: AURORA has NO rate limiting. Nginx has basic burst limits (10 req/sec per IP globally). No per-user rate limiting.

### 10.1 Rate Limiting

**Current State**: No per-user or per-IP rate limiting implemented.
**Q10.1.1**: Rate limit strategy:
- Per-user limits? (e.g., 100 req/min per user)
- Per-IP limits? (for mobile apps behind proxy)
- Global limit?

**Q10.1.2**: Rate limit response:
```
HTTP 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1704067200
Retry-After: 60
```

**Q10.1.3**: Should event ingestion have separate limits?
- Burst allowance for spiky traffic?

### 10.2 Service Level Agreements

**Current State**: No SLA defined or measured. Feed endpoint typically responds in <200ms (p95) on local tests, but NOT tested at production scale.

**Before Production**: Must perform load testing and define SLA with StreamLunar.

**Q10.2.1**: Feed endpoint SLA:
- Availability target? (99%, 99.9%, 99.99%?)
- Latency target? (p50, p95, p99: e.g., p95 < 200ms)
- Error budget?

**Q10.2.2**: Graceful degradation:
- If FAISS index unavailable, fallback to SQL?
- If user interest vector expired, show cold-start feed?
- If two-tower model fails to load, use heuristic ranking?

**Q10.2.3**: Incident response:
- Who is on-call for AURORA?
- Escalation path?
- RTO/RPO (recovery time/point objective)?

---

## 11. Data Isolation & Multi-Tenancy

### Status: ❌ StreamLunar Must Specify (NOT IMPLEMENTED YET)

### 11.1 Single vs. Multi-Tenant

**Current State**: AURORA is single-tenant (no tenant_id filtering). All data is assumed to belong to one platform.

**To Implement if needed**: Add tenant_id column to all tables, filter queries by tenant_id, namespace Redis keys by tenant.
**Q11.1.1**: Is AURORA serving one tenant (StreamLunar) or multiple?
- If multi-tenant: separate databases per tenant or shared with filtering?
- Shared Redis or separate Redis per tenant?

**Q11.1.2**: If multi-tenant:
- Tenant ID in all queries?
- Row-level security (RLS) in database?
- How are models shared or separated?

---

## 12. API Versioning & Backwards Compatibility

### Status: ⚠️ PARTIAL (v1 exists, versioning strategy NOT IMPLEMENTED YET / StreamLunar must define policy)

### 12.1 API Evolution

**Current State**: AURORA has `/api/v1/feed` endpoint. No versioning strategy, deprecation policy, or v2 planned.
**Q12.1.1**: API versioning strategy:
- URL-based (/api/v1, /api/v2)?
- Header-based (Accept: application/vnd.aurora+json;version=1)?
- Sunset policy for old versions?

**Q12.1.2**: Contract stability:
- Is the video schema stable or will new fields be added?
- Will response format change?
- How are deprecations communicated?

---

## 13. Testing & Staging

### Status: ⚠️ PARTIAL (Local tests exist, staging environment NOT SET UP)

### 13.1 Test Environment

**Current State**: AURORA has local unit tests (test_ranking_hmm.py). No dedicated staging environment or integration tests.
**Q13.1.1**: Staging setup:
- Is there a staging environment separate from production?
- Staging data: sample videos, synthetic events, or prod data replica?
- Who can deploy to staging?

**Q13.1.2**: Integration tests:
- Should AURORA include tests for StreamLunar API contracts?
- Mock StreamLunar services or call real staging services?

### 13.2 Load Testing

**Current State**: AURORA has NOT been load tested. No baseline latency/throughput metrics.

**Before Production**: Must perform load testing against StreamLunar staging. Estimate peak QPS, measure p50/p95/p99 latencies, validate model inference performance.

**Q13.2.1**: Before production deployment:
- Load test requirements? (peak QPS simulation)
- Duration? (5 min, 1 hour, sustained?)
- Acceptable latency percentiles?

**Q13.2.2**: Canary deployment:
- Roll out to 5% of traffic first, monitor, then 25%, then 100%?
- Automated rollback on error rate spike?

---

## 14. Compliance & Data Privacy

### Status: ❌ NOT IMPLEMENTED YET (StreamLunar must specify requirements)

**Missing**:
- No GDPR user deletion hooks
- No CCPA opt-out mechanism
- No audit logging
- No data retention policies

### 14.1 Data Governance

**Current State**: AURORA has NO data governance or compliance mechanisms. User deletion, GDPR/CCPA not implemented.
**Q14.1.1**: User data retention:
- GDPR: user deletion means what? (anonymize events, delete interest vectors?)
- CCPA: user opt-out of tracking? (delete events, reset interest vectors?)
- Other regulations?

**Q14.1.2**: Data residency:
- Must data be stored in specific geographic region?
- Cross-border data transfer restrictions?

### 14.2 Audit & Compliance
**Q14.2.1**: Audit logging:
- What actions must be logged for compliance? (model updates, config changes?)
- Immutable audit log required?

**Q14.2.2**: Security scanning:
- Container image scanning for vulnerabilities?
- Dependency audit?
- Code review/approval process?

---

## 15. Reporting & Insights

### Status: ❌ NOT IMPLEMENTED YET (StreamLunar must specify dashboard/reporting needs)

### 15.1 Analytics & Reporting

**Current State**: AURORA does NOT expose analytics or performance metrics to product/marketing teams.
**Q15.1.1**: Should AURORA expose usage analytics?
- How many users are engaged per day?
- Which videos are recommended most often?
- What is the click-through rate (CTR) on recommendations?
- Regional performance differences?

**Q15.1.2**: Content performance:
- Which content sources (trending, FAISS, interest-based) perform best?
- Does viral tier actually boost watch time?
- How do rollout-stage videos perform vs. graduated?

### 15.2 Dashboard & Reports
**Q15.2.1**: Should AURORA provide a dashboard for StreamLunar product/marketing?
- Real-time feed performance?
- Model training status?
- Event ingestion health?

---

## 16. Dependency Management & Third-Party Services

### Status: ⚠️ PARTIAL (Internal deps defined, external service adapters NOT IMPLEMENTED YET / StreamLunar must specify external dependencies)

### 16.1 External Dependencies

**Current State**: AURORA is self-contained. Does NOT currently call external StreamLunar services. All data (users, videos, events) is stored in AURORA database.

**To Integrate**: Create client adapters if AURORA needs to call StreamLunar services (user profile, video metadata, analytics).
**Q16.1.1**: If AURORA needs to call external services:
- Video metadata service (fetch video details)?
- User service (fetch user profile)?
- Analytics service (query engagement stats)?
- Content moderation service (flag inappropriate content)?

**Q16.1.2**: For each external dependency:
- Expected SLA (availability, latency)?
- Timeout & retry strategy?
- Circuit breaker pattern for resilience?
- Fallback behavior if service down?

### 16.2 Third-Party Libraries

**Current State**: AURORA uses PyTorch (torch), FAISS (CPU), sentence-transformers for NLP. All dependencies pinned in requirements.txt.

**Key Dependencies**:
- PyTorch (model training)
- FAISS (similarity search)
- sentence-transformers (NLP embeddings)
- FastAPI (HTTP server)
- SQLAlchemy (ORM)
- Redis (caching)
- Asyncpg (async PostgreSQL driver)

**Q16.2.1**: Model dependencies:
- sentence-transformers (for NLP embeddings)?
- torch/PyTorch (for model training)?
- faiss-cpu or faiss-gpu?
- License compatibility?

**Q16.2.2**: Dependency scanning:
- Are there security policies on dependencies?
- Approved vs. blacklisted libraries?

---

## 17. Cost & Resource Planning

### Status: ⚠️ PARTIAL (Tested on dev hardware, production sizing needed)

### 17.1 Infrastructure Costs

**Current State**: AURORA tested on modest hardware (4 CPU, 8GB RAM). Production requirements not yet determined.

**Development Environment**:
- API: ~500MB RAM, 1 CPU core
- Worker: ~2GB RAM, 2 CPU cores (during training)
- PostgreSQL: ~1GB RAM
- Redis: 512MB RAM

**To Size for Production**: Estimate based on expected video catalog size and concurrent users.
**Q17.1.1**: What infrastructure does AURORA consume?
- Compute: how many CPU cores, how much RAM per instance?
- Storage: PostgreSQL data volume, Redis memory, model size?
- Network: data transfer costs?

**Q17.1.2**: Cost optimization:
- Can AURORA use spot instances or reserved capacity?
- Is there a cost budget?

### 17.2 Staffing
**Q17.2.1**: Operational requirements:
- How many engineers to maintain AURORA in production?
- On-call rotation?

---

## 18. Go-Live Checklist

### 18.1 Pre-Production Sign-Off
- [ ] Data schema aligned with StreamLunar
- [ ] Authentication & authorization implemented
- [ ] API contract agreed upon
- [ ] Load testing completed
- [ ] Monitoring & alerting configured
- [ ] Runbook created (incident response)
- [ ] On-call team trained
- [ ] GDPR/compliance review passed
- [ ] Security scan passed
- [ ] Staging environment validated
- [ ] Rollback plan documented
- [ ] SLA agreed upon with business stakeholders

### 18.2 Launch Plan
- [ ] Scheduled deployment window
- [ ] Canary rollout percentage & duration
- [ ] Rollback trigger conditions
- [ ] Communication plan (Slack notification, status page)
- [ ] Post-launch monitoring (24/7 for first week?)

---

## 19. Glossary & Definitions

| Term | Definition |
|---|---|
| **AURORA** | Recommendation engine (this microservice) |
| **VRS** | Video Ranking System (original component) |
| **StreamLunar** | Parent streaming platform |
| **Two-Tower Model** | Dual embedding model (user tower + video tower) for ranking |
| **FAISS** | Facebook AI Similarity Search (nearest neighbor search) |
| **HMM** | Hidden Markov Model for user interest tracking |
| **Interest Vector** | Probability distribution over video tags (user preferences) |
| **Viral Tier** | Classification (WATCH, HOT, VIRAL, MEGA_VIRAL) for trending videos |
| **Rollout** | Staged release of video content to increasing user cohorts |
| **TTL** | Time-to-live (cache expiration policy) |
| **LRU** | Least recently used (eviction policy) |
| **QPS** | Queries per second (throughput metric) |
| **SLA** | Service level agreement (availability, latency guarantees) |
| **RTO/RPO** | Recovery time/point objectives (disaster recovery metrics) |

---

## 20. Feedback & Next Steps

**This specification is a living document.**

### Questions for StreamLunar:
1. Which sections require clarification?
2. Are there StreamLunar-specific constraints not mentioned above?
3. What is the timeline for integration?
4. Who is the primary technical contact for AURORA integration?

### AURORA Team Immediate Action Items (Parallel, while waiting):
- [ ] Code audit & cleanup (add type hints, increase test coverage)
- [ ] Generate OpenAPI/Swagger documentation
- [ ] Create database schema documentation
- [ ] Document model training process
- [ ] Security dependency scan
- [ ] Prepare demo environment

### StreamLunar Must Provide (Critical Path Blocker):
- [ ] Auth mechanism & token format (Q1.1.1-1.1.4)
- [ ] User schema & context passing (Q2.1.1-2.2.3)
- [ ] Video schema & engagement data location (Q3.1.1-3.3.3)
- [ ] Event delivery mechanism (Q4.1.1-4.1.4)
- [ ] Feed response contract (Q5.1.1-5.3.2)
- [ ] Expected QPS, latency SLA, availability target (Q10.2.1)
- [ ] Kubernetes cluster details (Q8.1.1-8.1.3)
- [ ] Monitoring stack (logging, metrics, tracing) (Q9.1.1-9.3.2)
- [ ] Compliance requirements (Q14.1.1-14.2.2)

---

## Implementation Roadmap

### Current Status
- **Phase**: Requirements Gathering (IN PROGRESS)
- **Readiness**: ~40% (core AURORA ready, integration pending)
- **Blocker**: Awaiting StreamLunar answers to sections 1-20

### Phase 0: Requirements Gathering (2 weeks)
**Status**: IN PROGRESS
- [ ] StreamLunar provides complete answers to specification
- [ ] Teams align on auth, user model, video schema
- [ ] Event ingestion mechanism decided (HTTP/Kafka/etc.)
- [ ] SLA targets confirmed (QPS, latency, availability)
- [ ] Compliance requirements clarified

### Phase 1: Integration Adapters (2-3 weeks)
**Status**: NOT STARTED
- [ ] Auth adapter (validate StreamLunar tokens)
- [ ] User context mapper (StreamLunar schema → AURORA model)
- [ ] Video schema adapter (map video fields)
- [ ] External service clients (if needed: user service, video service)
- [ ] Event ingestion adapter (HTTP/Kafka/pub-sub)
- [ ] Response format transformer (AURORA → StreamLunar)

### Phase 2: Deployment & Operations (2-3 weeks)
**Status**: NOT STARTED
- [ ] Kubernetes manifests (Deployment, Service, HPA, PDB)
- [ ] Prometheus metrics implementation
- [ ] OpenTelemetry distributed tracing integration
- [ ] Staging environment provisioning
- [ ] Load testing & performance baseline
- [ ] Runbook & incident response procedures

### Phase 3: Compliance & Hardening (1-2 weeks)
**Status**: NOT STARTED
- [ ] GDPR/CCPA data deletion hooks
- [ ] Rate limiting (per-user, per-IP, per-region)
- [ ] Container security scanning
- [ ] Dependency vulnerability audit
- [ ] Audit logging implementation
- [ ] Security review by StreamLunar team

### Phase 4: Go-Live (1 week)
**Status**: NOT STARTED
- [ ] Final staging validation
- [ ] Canary rollout plan (5% → 25% → 100%)
- [ ] Rollback & incident response runbook
- [ ] On-call team training
- [ ] Production deployment
- [ ] 24/7 monitoring (first week)

**Total Timeline**: 8-12 weeks from requirements confirmation

---

**Document Version**: 1.0  
**Last Updated**: April 30, 2026  
**Maintained By**: AURORA Engineering Team  
**For Questions**: Contact: aurora-team@streamlunar.com

---

## 21. StreamLunar Blocking Questions

**From:** AURORA-VRS Team  
**To:** StreamLunar Engine Team  
**Date:** 2026-04-26  
**Purpose:** Everything AURORA needs to know from StreamLunar before any integration work can begin. Every question in this document is blocking. Nothing can be built until these are answered.

Do not assume any answer. Do not give a vague answer. Where a question asks for a schema, provide the actual column names, types, and constraints. Where a question asks for a UUID format, provide an actual example. Where a question asks about behavior, describe exactly what happens, not what is intended.

---

## Section 21.1 — StreamLunar API Structure

AURORA needs the full StreamLunar API shape so it can integrate cleanly as an internal recommendation service. The feed contract is only one piece of the integration. StreamLunar must describe the surrounding API structure so AURORA knows what it is integrating with, what it should never call, and what data lives only in StreamLunar.

---

### 21.1.1 Public API Surfaces

What are the full public API surfaces exposed by StreamLunar today?

Provide all of the following if they exist:
- GraphQL schema root types (`Query`, `Mutation`, `Subscription`)
- REST endpoints used by the Flutter app
- Internal service endpoints used only by backend services
- Webhook endpoints
- Admin or moderation endpoints

For each surface, specify:
- Path or GraphQL root operation name
- Request method if REST
- Authentication mechanism
- Whether AURORA should ever call it directly

---

### 21.1.2 GraphQL Schema Shape

If StreamLunar uses GraphQL, provide the actual API structure:
- Root `Query` fields
- Root `Mutation` fields
- Any `Subscription` fields
- Input object types used by the feed, upload, and engagement flows
- Custom scalars in use (`DateTime`, `UUID`, `Cursor`, etc.)
- Pagination style (`cursor`, `offset`, `relay`, etc.)

For the feed integration, AURORA specifically needs to know:
- What the exact `recommendedFeed` query looks like
- What arguments it accepts
- What type it returns
- Whether the final response is hydrated in GraphQL resolvers or by a separate service layer

---

### 21.1.3 Authentication and Session Model

Describe the StreamLunar auth structure that sits in front of the API:
- Does the client send a JWT, session cookie, or opaque token?
- Is the API gateway or backend responsible for validating it?
- Which claim or session field maps to `user_id`?
- Are there separate auth rules for public, creator, moderator, and admin users?
- Are service-to-service calls authenticated differently from client calls?

This must be explicit because AURORA must never depend on user JWTs once it becomes an internal ranking service.

---

### 21.1.4 Video Upload and Engagement Endpoints

List the StreamLunar endpoints or mutations that create and mutate video state:
- Upload start
- Upload completion
- Metadata update
- Privacy change
- Delete / soft delete
- Like / dislike / save / comment / share / skip / watch writes

For each one, specify:
- Whether it is GraphQL or REST
- The exact input shape
- Which fields are required
- Which service owns the write
- Whether AURORA should receive a forwarded event afterward

---

### 21.1.5 Versioning and Deprecation

What is StreamLunar's API versioning strategy?
- URL versioning (`/api/v1`, `/api/v2`)?
- GraphQL schema evolution only?
- Header-based version selection?

How are breaking changes communicated?
- Deprecation window
- Sunset policy
- Backwards compatibility guarantees

If AURORA is integrated against an API contract that changes later, what is the expected migration path?

---

### 21.1.6 Error Format and Pagination

What is the standard error shape for StreamLunar API responses?
- GraphQL error envelope structure
- REST error JSON schema
- Error codes and human-readable messages

What pagination patterns are used throughout StreamLunar APIs?
- Cursor values
- Page numbers
- Opaque tokens
- Maximum page size

This matters because AURORA's feed integration, hydration order preservation, and fallback behavior depend on the API conventions StreamLunar already uses.

---

### 21.1.7 Internal Services AURORA Must Not Call

Which StreamLunar services are internal-only and should never be called directly by AURORA?
- Upload pipeline services
- Moderation services
- Billing or subscription services
- User profile mutation services
- Any service behind GraphQL-only access

If some services are reachable only through the Go backend and not directly from AURORA, say so explicitly.

---

### 21.1.8 Remaining StreamLunar Backend Surfaces

The current AURORA backend contains routes for categories, tags, notifications, analytics, and static video content. StreamLunar must describe whether these exist in the new architecture, whether AURORA should read them directly, or whether they will be retired in favor of StreamLunar-owned equivalents.

**Q21.1.8.1**: What is the source of truth for categories and tags?
- Are `/api/v1/content/categories` and `/api/v1/content/tags` StreamLunar-owned endpoints?
- Should AURORA call them directly, or should these be retired in favor of database access only?
- Do categories/tags have their own GraphQL fields instead of REST endpoints?

**Q21.1.8.2**: What is the notifications API shape?
- Does StreamLunar expose notifications to clients at all?
- Are `/api/v1/notifications` and `/api/v1/notifications/{id}` real StreamLunar endpoints, or are they being removed when AURORA stops being standalone?
- If notifications remain, what is their schema and who owns writes?

**Q21.1.8.3**: What is the analytics API shape?
- Does StreamLunar have a video analytics endpoint equivalent to `/api/v1/analytics/videos/{id}`?
- If yes, is it GraphQL or REST, and what fields does it return?
- Should AURORA read those metrics directly from the database instead of calling an API?

**Q21.1.8.4**: What is the static video content and upload asset path?
- Is ` /api/v1/videos/content/* ` still the correct public or internal path for video playback assets?
- Is video content served by StreamLunar, object storage, a CDN, or the AURORA filesystem?
- Should AURORA ever reference static content URLs directly, or only video IDs?

**Q21.1.8.5**: What root and documentation endpoints are part of StreamLunar's API surface?
- Is `GET /` intended to exist in production?
- Is `/docs` public, internal-only, or disabled in production?
- Are health and ML admin endpoints the only AURORA-exposed endpoints after the cutover?

**Q21.1.8.6**: What are the public video read endpoints?
- Does StreamLunar expose a video list endpoint equivalent to `GET /api/v1/videos`?
- Does StreamLunar expose a video search endpoint equivalent to `GET /api/v1/videos/search`?
- Does StreamLunar expose a video detail endpoint equivalent to `GET /api/v1/videos/{id}`?
- Does StreamLunar expose an upload-status endpoint equivalent to `GET /api/v1/videos/{id}/status`?
- If these remain, are they client-facing GraphQL fields, REST endpoints, or internal-only helpers?
- Should AURORA ever call them directly, or only StreamLunar should use them for hydration/debugging?

---

## Section 1 — PostgreSQL Database Access

AURORA's worker training loop and SQL fallback feed path both require direct read access to Stream Luna's PostgreSQL database. AURORA will never write to Stream Luna's database. The following questions determine exactly what that connection looks like and what data AURORA is allowed to read.

---

### 1.1 Database Host and Port

What is the hostname or IP address of Stream Luna's PostgreSQL instance as it is reachable from within the shared Docker network?

Is it running as a Docker Compose service (in which case the hostname is the service name, e.g. `db` or `postgres`), or is it a managed external database (e.g. Supabase, Neon, Railway, DigitalOcean Managed Postgres)?

If it is a managed external database, provide the full connection hostname and port number.

If it is a Docker Compose service, provide the exact service name as declared in `docker-compose.yml`.

---

### 1.2 Database Name

What is the name of Stream Luna's PostgreSQL database — the value that goes after the final `/` in a connection string?

Example format of what is needed: `streamluna` or `luna_production` or `engine_db`. Provide the exact value.

---

### 1.3 Read-Only User Credentials

Stream Luna must create a dedicated PostgreSQL user for AURORA with read-only permissions. This user must be created by the Stream Luna team. AURORA will not use the application's primary database user.

Confirm the following will be done by the Stream Luna team:

1. A PostgreSQL user named `aurora_reader` (or any name Stream Luna prefers) will be created.
2. The password for that user will be generated and shared with AURORA securely (not over Slack, not in a Git commit).
3. The user will be granted `CONNECT` on the Stream Luna database.
4. The user will be granted `USAGE` on the `public` schema.
5. The user will be granted `SELECT` on the specific tables listed in Section 2 of this document.

If Stream Luna uses a different schema name than `public`, provide the exact schema name.

Once created, provide the full connection string in this format:

```
postgresql+asyncpg://aurora_reader:<password>@<host>:<port>/<database_name>
```

---

### 1.4 PostgreSQL Version

What version of PostgreSQL is Stream Luna running?

AURORA uses SQLAlchemy with `asyncpg`. Certain query features (e.g. `ANY($1)` array parameters, `UNNEST`, JSON operators) behave differently across PostgreSQL versions. Provide the exact version number, e.g. `15.3` or `16.1`.

---

### 1.5 Network Reachability

If both Stream Luna and AURORA run on the same VPS via Docker Compose, the database is reachable over the internal Docker network with no firewall rules needed.

Confirm: Are both services on the same VPS and the same Docker Compose network, or is the database on a separate host that requires firewall rules or VPN access?

If separate, describe exactly how AURORA should reach it.

---

## Section 2 — Table Schemas

AURORA reads from Stream Luna's database to build training data and generate fallback feed candidates. For each table below, provide the exact schema: every column name, its PostgreSQL data type, whether it is nullable, and any relevant constraints or enum values.

Do not paraphrase column names. If the column is called `hls_master_url`, write `hls_master_url`. If it is called `manifest_url`, write `manifest_url`. AURORA's SQL queries will use the exact names provided here.

---

### 2.1 The `videos` Table

AURORA needs to read video metadata for two purposes: building training pairs in the worker, and building fallback feed candidates in the SQL path.

Provide the full schema for the videos table. AURORA specifically needs to know the exact column names for:

| Information Needed | Why AURORA Needs It |
|---|---|
| Primary key / video ID column name and type | Every AURORA reference to a video uses this key |
| Creator / uploader ID column name and type | Used to build the followed-creators candidate pool |
| Video status column name and all possible enum values | AURORA must only train on and serve `READY` videos — what is the exact string value for ready? |
| Video privacy column name and all possible enum values | AURORA must only train on and serve `PUBLIC` videos — what is the exact string value? |
| Video type column name and possible values | AURORA supports `QUICK` and `LONGFORM` — what are Stream Luna's exact values? |
| Duration column name and unit | Seconds? Milliseconds? Integer or float? |
| View count column name and type | Engagement feature for ranking |
| Like count column name and type | Engagement feature |
| Dislike count column name and type | Used to compute dislike rate |
| Comment count column name and type | Engagement feature |
| Share count column name and type | Engagement feature |
| Average watch ratio column name and type | Critical ranking feature — is this stored or computed? If computed, from what? |
| Created at column name and type | Used for recency scoring and cold-start logic |
| Soft delete column name (if any) | If videos are soft-deleted rather than physically removed, what is the column and what value indicates deletion? |
| HLS master playlist URL column name | Used if AURORA ever needs to reference the video stream URL |
| Thumbnail URL column name | Not used by AURORA directly but needed to confirm what Stream Luna returns during video hydration |

Provide the complete `CREATE TABLE` statement for the videos table if possible. That is the least ambiguous format.

---

### 2.2 The `tags` Table

AURORA uses tags as the semantic vocabulary for the entire recommendation system. The HMM interest vector is a probability distribution over tag names. The Two-Tower model uses tag embeddings. The SQL fallback queries candidates by tag affinity.

Provide the full schema. AURORA specifically needs:

| Information Needed | Why |
|---|---|
| Primary key column name and type | Used in JOIN conditions |
| Tag name column name | This is what AURORA stores in the interest vector — the actual string value |
| Any other columns that affect which tags are active or visible | If tags can be disabled or archived, AURORA needs to filter those out |

Are tag names guaranteed to be unique? If two tags can have the same name (e.g. different capitalizations), how should AURORA deduplicate?

Are tag names normalized to lowercase? Or can the same concept appear as both `Comedy` and `comedy`? AURORA's interest vector uses tag name strings as keys. If casing is inconsistent, the HMM will treat `Comedy` and `comedy` as different tags and split probability mass incorrectly.

---

### 2.3 The `video_tags` Join Table

This table maps videos to their tags. AURORA reads it to know which tags belong to which video.

Provide the full schema. AURORA needs:

| Information Needed | Why |
|---|---|
| Video ID column name and type | Must match the primary key in the `videos` table exactly |
| Tag ID column name and type | Must match the primary key in the `tags` table exactly |
| Any additional columns | e.g. is there a `primary` or `weight` column that indicates which tag is most representative? |

Is there any constraint on how many tags a video can have? Is there a minimum? Can a video have zero tags? If a video has no tags, AURORA cannot include it in tag-based candidate generation. AURORA needs to know whether to treat zero-tag videos as an edge case or as common.

---

### 2.4 The `categories` Table

Categories are a secondary semantic signal used by the video tower in the Two-Tower model and as a fallback grouping in candidate generation.

Provide the full schema. AURORA needs:

| Information Needed | Why |
|---|---|
| Primary key column name and type | JOIN condition |
| Category name column name | Used the same way as tag names in training |
| Any columns indicating whether a category is active | AURORA should not train on archived categories |

What is the relationship between tags and categories? Are they mutually exclusive concepts, or can a video have both tags and categories that mean the same thing? Describe the semantic distinction Stream Luna makes between a tag and a category.

---

### 2.5 The `video_categories` Join Table

Provide the full schema. AURORA needs:

| Information Needed | Why |
|---|---|
| Video ID column name and type | JOIN condition |
| Category ID column name and type | JOIN condition |

---

### 2.6 The `users` Table

AURORA reads basic user metadata for two purposes: building the user tower features in the Two-Tower model (account age, event count) and resolving creator IDs when building the followed-creator candidate pool.

Provide the relevant schema. AURORA specifically needs:

| Information Needed | Why |
|---|---|
| Primary key / user ID column name and type | Every AURORA user reference uses this |
| Account creation date column name and type | Used to compute `account_age_days` as a user tower feature |
| Any column indicating whether the account is active or banned | AURORA should not serve content from banned creators |
| Username column name | Used in logging and debugging only, not in ML logic |

AURORA does not need the user's password hash, email, payment details, or any PII beyond the ID and creation date. Confirm Stream Luna is comfortable granting `aurora_reader` SELECT on the full users table, or specify which columns should be restricted.

---

### 2.7 The `follows` Table

AURORA uses follow relationships to build the followed-creator candidate pool. When generating a feed for user X, AURORA finds all creator IDs that X follows and pulls recent videos from those creators as priority candidates.

Provide the full schema. AURORA needs:

| Information Needed | Why |
|---|---|
| Follower ID column name and type | The user who is following |
| Following / followed ID column name and type | The creator being followed |
| Created at column name | Not strictly required but useful for recency filtering |
| Any column indicating the follow is pending, blocked, or inactive | AURORA must only use confirmed, active follow relationships |

Are follow relationships between users, or between a user and a creator profile? If Stream Luna has separate `users` and `creator_profiles` tables, clarify which IDs are used in the follows table and which ID AURORA should use as the `creator_id` when querying videos.

---

### 2.8 The `likes` Table (if separate from `videos`)

Stream Luna's architecture document mentions like counts on videos. Are like counts stored as a column directly on the `videos` table (e.g. `like_count INT`) or are they computed by counting rows in a separate `likes` table?

If they are a column on the `videos` table, this question is answered by Section 2.1.

If they are a separate table, provide the schema. AURORA needs to know whether to read the count from `videos.like_count` or compute it with `COUNT(*)` from a separate table. Counting at query time is expensive at scale. AURORA will use whichever approach Stream Luna uses, but needs to know which one.

---

### 2.9 Engagement Velocity / `avg_watch_ratio`

The `avg_watch_ratio` field is the single most important engagement signal in AURORA's ranking formula. It directly affects the final ranking score of every video in every feed.

Answer the following exactly:

1. Is `avg_watch_ratio` stored as a column on the `videos` table, or must it be computed by AURORA from raw event data?
2. If it is stored, what is the exact column name and PostgreSQL data type? Is it `FLOAT`, `DOUBLE PRECISION`, `NUMERIC`, or something else?
3. If it is stored, when is it updated? Is it updated in real time after each view, or on a schedule? How stale can it be?
4. If it is not stored and must be computed: does Stream Luna have an events table AURORA can read from, or does AURORA need to compute it from Stream Luna's `likes` and `views` tables?
5. What does a `watch_ratio` of `1.0` mean — did the user watch the full video? What does `0.0` mean?

---

## Section 3 — User and Video ID Format

AURORA's entire data model is built around user IDs and video IDs. If these formats are wrong, every database query fails silently or returns empty results.

---

### 3.1 User ID Format

What is the exact data type and format of user IDs in Stream Luna's PostgreSQL database?

Provide a concrete example of a real (or realistic test) user ID exactly as it appears in the database. For example:

- UUID v4 with hyphens: `550e8400-e29b-41d4-a716-446655440000`
- UUID without hyphens: `550e8400e29b41d4a716446655440000`
- Integer: `10482`
- ULID: `01ARZ3NDEKTSV4RRFFQ69G5FAV`

What is the PostgreSQL column type — `UUID`, `VARCHAR`, `BIGINT`, `TEXT`?

When Stream Luna sends a user ID to AURORA in the event forwarding payload or the feed request query parameter, will it send the ID in exactly the same format as it appears in the database? Or will it be transformed (e.g. stringified integer, lowercased UUID)?

---

### 3.2 Video ID Format

Same questions as 3.1, but for video IDs.

Provide a concrete example of a real video ID exactly as it appears in the database. Specify the PostgreSQL column type.

---

### 3.3 Creator ID vs User ID

When a user uploads a video, is the video's creator identified by the same ID that appears in the `users` table (i.e. the user's primary key), or does Stream Luna have a separate `creator_profiles` table with its own IDs?

If there is a `creator_profiles` table: what is the relationship between `users.id` and `creator_profiles.id`? Which ID is stored on the `videos` table as the creator reference? Which ID will Stream Luna use when forwarding event payloads to AURORA?

This must be unambiguous. AURORA's followed-creator candidate pool works like this:

```
1. Load follows where follower_id = current_user_id
2. Collect all following_id values (these are creator IDs)
3. Query videos where creator_id = ANY(collected_creator_ids)
```

If `following_id` in the follows table and `creator_id` in the videos table are different ID spaces, step 3 returns zero results and the followed-creator pool is permanently empty. AURORA needs these to be the same ID type pointing to the same entity.

---

## Section 4 — Event Forwarding Contract

Stream Luna's Asynq worker will forward engagement events to AURORA after every user interaction. AURORA's entire online learning loop — the HMM interest updater — depends on receiving these events correctly and immediately.

---

### 4.1 Which Engagement Actions Will Be Forwarded

Confirm explicitly which of the following actions Stream Luna will forward to AURORA. For each one, write either WILL FORWARD or WILL NOT FORWARD.

| Action | Forward? | Notes |
|---|---|---|
| User opens / views a video | | |
| User watches a video (with completion ratio) | | |
| User likes a video | | |
| User saves a video to a collection | | |
| User shares a video | | |
| User comments on a video | | |
| User skips past a video in the feed | | |
| User dislikes a video | | |

For any action marked WILL NOT FORWARD, explain why. AURORA's ranking and HMM logic depends on negative signals (SKIP, DISLIKE) as much as positive ones. If negative signals are not forwarded, AURORA cannot correctly reduce interest in content the user dislikes.

---

### 4.2 Watch Ratio — How Stream Luna Measures It

The `WATCH` event is the highest-value signal in AURORA's system. The `watch_ratio` value it carries is the primary input to AURORA's HMM when the signal is strong (≥ 0.6).

Answer the following:

1. Does the Flutter app currently report how far through a video the user watched? If yes, what is the data format — a float between 0.0 and 1.0, a percentage integer (0–100), or seconds watched?
2. At what point does Stream Luna fire the `WATCH` event — when the video ends, when the user scrolls away, or at some other trigger?
3. Is there a distinction between a `VIEW` (video was opened) and a `WATCH` (user actually engaged with it for some duration)? If Stream Luna only has one event type for video consumption, describe exactly what it captures.
4. If watch ratio is not currently tracked: is Stream Luna willing to add this tracking to the Flutter app and forward it? If not, AURORA needs to know so the WATCH event signal mapping can be adjusted.

---

### 4.3 Skip Event — How Stream Luna Detects It

A `SKIP` carries a signal of `-0.5` in AURORA's system. It tells the HMM to reduce interest in the video's tags. This is important for preventing the feed from getting stuck showing content the user repeatedly passes over.

How does Stream Luna currently define and detect a skip? Options:

- User scrolls past a video without watching any of it
- User watches less than a threshold (e.g. < 5 seconds or < 10%) and scrolls away
- Stream Luna does not currently track this and would need to add it

If Stream Luna does not currently track skip behavior, state this clearly. AURORA will still function without skip events but the HMM will be slower to respond to negative user preferences.

---

### 4.4 Asynq Task Timing

How quickly after the user action will the Asynq task fire and deliver the event to AURORA?

AURORA's Redis interest vector is updated synchronously when the event arrives. The next feed request the user makes will see the updated interest state. If the Asynq task is delayed by minutes (e.g. a long queue), there is a noticeable gap between the user's action and the feed updating.

Describe the typical delay between user action and Asynq task execution in Stream Luna's current deployment. Is there a queue depth concern at high throughput?

---

### 4.5 Retry Behavior on AURORA Failure

If AURORA's event endpoint is temporarily unavailable (restarting, overloaded), what happens to the Asynq task?

AURORA needs to know:
1. How many times will Stream Luna retry a failed event task?
2. What is the backoff strategy — fixed delay, exponential, or none?
3. After all retries are exhausted, is the event logged somewhere, dead-lettered, or silently dropped?
4. Is there any alerting if the AURORA event endpoint is consistently failing?

AURORA does not guarantee perfect uptime during model reloads (which take a few seconds) or FAISS rebuilds. Stream Luna's retry logic must be able to absorb short outages without losing large volumes of events.

---

## Section 5 — Feed Request Contract

Stream Luna's `recommendedFeed` GraphQL resolver will call AURORA's feed endpoint on every client feed request. The behavior of this call determines the entire user-facing feed experience.

---

### 5.1 Who Calls the Feed Endpoint

Confirm: the feed endpoint at `GET /api/v1/feed` will only ever be called by Stream Luna's Go backend, never directly by the Flutter app.

If there is any scenario where the Flutter app might call AURORA directly (e.g. during development or testing), state it explicitly. AURORA's service token middleware will reject any call without the correct token, but AURORA needs to design error responses accordingly.

---

### 5.2 Feed Request Frequency

How often will a single user trigger a `recommendedFeed` GraphQL query?

Specifically:
1. Does Stream Luna call AURORA once when the user opens the feed, or does it call AURORA on every scroll pagination event?
2. If pagination triggers a new call: with what frequency? Every 20 videos scrolled? Every 10?
3. Is there any client-side debouncing or caching in the Flutter app that reduces the number of GraphQL calls?

AURORA caches feed results per user per page for 5 minutes. If Stream Luna calls the feed endpoint 100 times per minute for a single user, AURORA will serve cached results after the first call. But AURORA needs to understand the call pattern to set appropriate cache TTLs and Redis memory budgets.

---

### 5.3 Unauthenticated Feed Requests

What happens when a user who is not logged in opens the Stream Luna app and views the feed?

Options:
- Stream Luna does not show a feed to unauthenticated users
- Stream Luna shows a generic feed and does not call AURORA (handles it internally)
- Stream Luna calls AURORA without a user ID

AURORA's feed endpoint requires a `user_id` to personalize results. If `user_id` is absent, AURORA falls back to a globally trending feed with no personalization. Clarify which behavior Stream Luna expects so AURORA handles the missing `user_id` case correctly.

---

### 5.4 Video Hydration After AURORA Response

After AURORA returns an ordered list of video IDs, Stream Luna queries its own database to hydrate the full video objects. AURORA needs to understand exactly what Stream Luna expects in the final GraphQL response so there are no surprises.

Provide the full list of fields that Stream Luna's `recommendedFeed` GraphQL response will include per video item. For example:

```graphql
type RecommendedFeedItem {
  id: ID!
  title: String!
  description: String
  thumbnailUrl: String!
  hlsMasterUrl: String!
  duration: Int!
  viewCount: Int!
  likeCount: Int!
  commentCount: Int!
  creator: CreatorProfile!
  tags: [String!]!
  createdAt: String!
}
```

This question is for AURORA's awareness only — AURORA does not produce these fields. But if Stream Luna's hydration query fails for any reason (e.g. a video was deleted between AURORA caching it and Stream Luna querying it), AURORA needs to know how Stream Luna will handle the gap. Specifically:

1. If AURORA returns 20 video IDs and 2 of them no longer exist in Stream Luna's database, does Stream Luna return 18 items or does it fill the gap with other content?
2. If Stream Luna fills the gap: where does the replacement content come from?

---

### 5.5 Feed Ordering Preservation

AURORA returns video IDs in ranked order. The first ID in the list is the highest-scoring video for that user. Stream Luna must preserve this order when hydrating and returning results.

When Stream Luna queries PostgreSQL with `WHERE id = ANY($1)`, PostgreSQL does not guarantee returning rows in the same order as the input array.

Confirm: Stream Luna will re-order the hydrated video rows to match AURORA's original ranking order before returning the GraphQL response. If Stream Luna is unsure how to do this, flag it — it is a one-time implementation detail AURORA can assist with.

---

## Section 6 — Redis Configuration

AURORA and Stream Luna both use Redis. If they share the same Redis instance (which is likely on a single VPS), they must use different database indexes to prevent key collisions.

---

### 6.1 Redis Host and Port

What is the hostname and port of Stream Luna's Redis instance as reachable from within the Docker network?

Is it a Docker Compose service (provide the service name) or an external managed Redis (provide the host and port)?

---

### 6.2 Redis Database Index

Which Redis database index does Stream Luna currently use?

The default is `0`. If Stream Luna uses `0`, AURORA will use `1`. If Stream Luna uses a different index, state it so AURORA can choose a non-conflicting one.

The AURORA Redis URL will be configured as:
```
redis://<host>:<port>/<index>
```

For example: `redis://redis:6379/1`

---

### 6.3 Redis Authentication

Does Stream Luna's Redis instance require a password (`requirepass` in Redis config)?

If yes, the same password must be provided to AURORA so its connection string can be:
```
redis://:<password>@<host>:<port>/<index>
```

---

### 6.4 Redis Memory Limit

What is the `maxmemory` setting on the shared Redis instance?

AURORA will add the following key categories to Redis:
- `iv:{user_id}` — one key per active user, ~2KB each, 30-day TTL
- `feed_cache:{user_id}:{page}` — one key per active user per page, ~5KB each, 5-minute TTL
- `session:{user_id}` — one sorted set per active user, capped at 200 entries, 4-hour TTL
- `viral:{video_id}` — one key per viral video, ~20 bytes each, 24-hour TTL
- `trending:global` — one sorted set, capped at 500 entries

AURORA needs to know the available memory headroom so it can set appropriate eviction policies without impacting Stream Luna's Redis usage.

---

## Section 7 — Docker and Network Configuration

---

### 7.1 Docker Network Name

What is the name of Stream Luna's Docker Compose network?

AURORA's containers must be added to this network so they can communicate with Stream Luna's engine, database, and Redis. Provide the exact network name as declared in Stream Luna's `docker-compose.yml`.

---

### 7.2 Stream Luna Engine Service Name

What is the Docker Compose service name for the Stream Luna Go engine?

This is the name AURORA uses if it ever needs to reach Stream Luna internally. More importantly, it is the service that will be calling AURORA, and knowing its name helps verify network routing.

---

### 7.3 VPS Specifications

What are the VPS specs — CPU cores, RAM, and disk — that Stream Luna and AURORA will share?

AURORA's worker training process is CPU and memory intensive. The Two-Tower model training run uses PyTorch and can spike CPU to 100% on all cores for several minutes. AURORA needs to know:

1. Total available RAM on the VPS
2. Number of CPU cores
3. Whether the VPS is shared-CPU (burstable) or dedicated-CPU

This determines the training batch size, FAISS index type, and whether the worker training schedule needs to be staggered to avoid competing with Stream Luna's request-handling load.

---

### 7.4 Existing Docker Compose File

Will AURORA's services (`aurora-api`, `aurora-worker`) be added to Stream Luna's existing `docker-compose.yml`, or will AURORA maintain a separate `docker-compose.yml` that connects to Stream Luna's network using `external: true`?

Either approach works. AURORA needs to know which one Stream Luna prefers so the deployment files are written correctly from the start.

If separate compose files: provide the exact network name declared in Stream Luna's compose file so AURORA can reference it as an external network.

---

## Section 8 — Service Token

AURORA authenticates all requests from Stream Luna using a shared secret token passed in the `X-Service-Token` HTTP header. This section establishes how that token is generated and shared.

---

### 8.1 Token Generation

One team must generate the token. It does not matter which. The token must be:
- At least 64 hexadecimal characters (32 bytes of entropy)
- Generated with a cryptographically secure random source
- Never committed to Git, never sent over Slack in plaintext, never logged

Generate it with:
```bash
openssl rand -hex 32
```

Which team will generate the token, and how will it be shared securely with the other team? Options: encrypted message, shared password manager entry, environment variable sync tool.

---

### 8.2 Token Rotation Policy

What happens if the token is compromised or needs to be rotated?

AURORA's service token middleware reads the token from an environment variable at startup. Rotating the token requires redeploying both Stream Luna (with the new `AURORA_SERVICE_TOKEN` env var) and AURORA (with the same new value). Both services must deploy simultaneously or the integration breaks during the window between deployments.

Does Stream Luna have a zero-downtime deployment process, or is a brief outage acceptable during token rotation?

---

## Section 9 — Video Upload and Status Lifecycle

AURORA only trains on and serves videos with `status = 'READY'` and `privacy = 'PUBLIC'`. Understanding exactly when a video reaches that state determines when it becomes eligible for recommendation.

---

### 9.1 Full Video Status Lifecycle

List every possible value of the video status field and describe exactly what each one means. For example:

| Status Value | Meaning |
|---|---|
| `UPLOADING` | Client is uploading the raw file |
| `PROCESSING` | Processing engine is transcoding |
| `READY` | HLS manifest is available, video is streamable |
| `FAILED` | Transcoding failed, video is not usable |
| `DELETED` | Soft deleted |

Provide Stream Luna's actual status values. AURORA will filter its SQL queries to only include the exact string value that means "this video is fully transcoded and ready to stream."

---

### 9.2 Time from Upload to READY

On average, how long does it take from when a creator uploads a video to when the video reaches `READY` status?

This determines AURORA's content freshness. If processing takes 10 minutes on average, AURORA's SQL fallback query ordered by `created_at DESC` may surface videos that are still processing. AURORA must filter by status, but understanding the typical delay helps calibrate the cold-start discovery window.

---

### 9.3 Privacy Change Behavior

If a creator changes a video from `PUBLIC` to `PRIVATE` after it has already been included in AURORA's FAISS index and Redis trending data, what should happen?

AURORA's FAISS index rebuilds every 30 minutes. During that window, a newly-privatized video may still appear in AURORA's feed results. When Stream Luna receives those video IDs and hydrates them from its database, the hydration query includes `AND privacy = 'PUBLIC'`, which will exclude the newly-private video.

Is this acceptable — a window of up to 30 minutes where AURORA may return a video ID that Stream Luna silently drops? Or does Stream Luna require AURORA to be notified immediately when a video's privacy changes?

If immediate notification is required, Stream Luna must send a webhook or API call to AURORA when privacy changes. Describe whether Stream Luna is willing to implement this.

---

### 9.4 Upload-to-Ranking Pipeline

**Current State**: AURORA can only rank content once StreamLunar has created a stable video record with a usable ID, creator ID, tags, status, and privacy value. The upload pipeline determines when that record becomes eligible for recommendation.

**Q9.4.1**: What is the exact upload flow in StreamLunar?
- Does the client upload directly to StreamLunar, to object storage, or through a presigned URL flow?
- Which service creates the initial video row in PostgreSQL?
- At what point is the video ID assigned?
- At what point is the creator ID written?

**Q9.4.2**: When does a newly uploaded video become eligible for ranking?
- Immediately after upload begins?
- Only after transcode finishes and status becomes `READY`?
- Only after a moderation or review step?
- Only after tags/categories are finalized?

**Q9.4.3**: What exact signal tells AURORA that a video is now rankable?
- A database state change StreamLunar exposes through AURORA's read-only DB access?
- An event or webhook from StreamLunar?
- A periodic AURORA poll of the StreamLunar database?

**Q9.4.4**: Which upload-side fields can still change after the video is created?
- Title?
- Description?
- Tags?
- Categories?
- Thumbnail?
- Privacy?
- Duration?

If any of those fields can change after upload, when should AURORA refresh its cache, FAISS index, trending state, and training data?

**Q9.4.5**: Does StreamLunar create draft or private uploads that AURORA must ignore completely, or should AURORA be aware of them for future activation once they become public?

**Q9.4.6**: If a video fails processing, is deleted during upload, or is abandoned before becoming `READY`, should AURORA ever see it in the read-only database, or will StreamLunar hide/remove it before AURORA can read it?

---

## Section 10 — Tags and Content Vocabulary

AURORA's recommendation quality depends entirely on the quality and consistency of video tags. The HMM interest vector, Two-Tower model inputs, and SQL fallback candidate queries all use tag names as their core semantic signal.

---

### 10.1 Who Creates Tags

Are tags in Stream Luna a fixed, predefined list managed by admins, or can creators define their own tags when uploading a video?

If creator-defined: are they free-text strings with no normalization, or are they validated against a controlled vocabulary?

If free-text: what is the maximum length of a tag name? Are tags stored exactly as the creator typed them, or are they lowercased/trimmed before storage?

---

### 10.2 Tag Consistency

AURORA's HMM uses tag name strings as dictionary keys. If the same concept appears as multiple tag strings (`Comedy`, `comedy`, `COMEDY`, `comedic`), the HMM treats them as completely different interests and splits probability mass incorrectly.

Answer the following:
1. Are all tag names lowercased before storage? If yes, by the application layer or a database constraint?
2. Is there any deduplication or synonym mapping in place?
3. Approximately how many unique tags currently exist in the `tags` table?
4. Is there a plan to curate or reduce the tag vocabulary? A vocabulary of 10,000 uncurated tags produces a much noisier interest vector than 500 well-defined tags.

---

### 10.3 Minimum Tags Per Video

Is there any validation that prevents a video from being uploaded without at least one tag?

If videos can have zero tags, AURORA's tag-based SQL fallback will not include those videos in any personalized candidate pool. They can only appear in the generic engagement-ranked fallback. Is this acceptable, or should Stream Luna enforce a minimum tag requirement?

---

### 10.4 Categories vs Tags — Semantic Distinction

Stream Luna's architecture mentions both tags and categories. AURORA's Two-Tower model can use both as video semantic features.

Describe the intended distinction:
- Are categories broad groupings (e.g. `Entertainment`, `Education`, `Sports`) while tags are specific descriptors (e.g. `stand-up comedy`, `python tutorial`, `NBA highlights`)?
- Can a video belong to multiple categories?
- Are categories mandatory on upload, optional, or admin-assigned?
- How many categories exist in total?

AURORA will use categories as an additional semantic signal alongside tags. If categories are very coarse (fewer than 20), they add less value than tags. If they are fine-grained, they may overlap significantly with tags. Understanding the distinction helps AURORA weight them correctly in the video tower.

---

## Section 11 — Existing Engagement Data

AURORA's worker training loop builds training pairs from historical events. The quality of the first trained model depends on how much engagement data exists at the time of the first training run.

---

### 11.1 Existing Events Table

Does Stream Luna currently store a history of user engagement events — specifically, records of which user interacted with which video, what type of interaction it was, and when?

If yes:
1. What is the table name?
2. What columns does it have — specifically the user ID column, video ID column, event type column, timestamp column, and any watch duration or ratio column?
3. Does Stream Luna grant AURORA's reader user SELECT access to this table?

If no (engagement is only tracked as aggregate counts on the videos table): AURORA will start with zero historical event data and will need to accumulate events from Stream Luna's Asynq forwarding before the first training run is possible. State this clearly so AURORA can set the right expectations for when the first personalized ML feed will be available.

---

### 11.2 Volume of Existing Data

Approximately how many videos currently exist in Stream Luna's database with `status = 'READY'` and `privacy = 'PUBLIC'`?

Approximately how many registered users are there?

Approximately how many total engagement events exist (if the events table exists)?

These numbers determine:
- Whether AURORA's first FAISS index will be meaningful or nearly empty
- How long the first worker training run will take
- What `MIN_EVENTS_FOR_MODEL` threshold is realistic for the current user base

---

## Section 12 — Operational Expectations

---

### 12.1 AURORA Downtime Tolerance

If AURORA's API container restarts (e.g. after a model reload or FAISS rebuild), there is a brief window of 5–30 seconds where AURORA is unavailable.

During this window, Stream Luna's `recommendedFeed` resolver will receive a connection error or timeout from AURORA. Stream Luna must fall back to its own SQL-based feed immediately.

Confirm: Stream Luna's resolver has a timeout configured on the AURORA HTTP call. What timeout value will be used? AURORA recommends 3–5 seconds maximum. A timeout longer than 5 seconds means AURORA unavailability directly causes user-visible latency on every feed load.

---

### 12.2 AURORA Feed Endpoint Latency Expectation

What is the maximum acceptable latency for the entire `recommendedFeed` GraphQL resolver from the Flutter client's perspective?

AURORA targets a p95 feed response time of under 80ms for cached results and under 300ms for cold cache. Stream Luna's database hydration query adds additional latency on top of AURORA's response. The total end-to-end latency budget for the resolver should be agreed upon.

If the total budget is 500ms and Stream Luna's hydration query takes 100ms, AURORA has 400ms to respond. If the budget is 300ms total, AURORA needs to optimize its cache hit rate more aggressively.

---

### 12.3 Monitoring and Alerting

How does Stream Luna currently monitor its services?

AURORA's `GET /health` endpoint is available for health checks with no authentication required. It returns `{"status": "ok"}` with HTTP 200 when healthy.

Does Stream Luna's monitoring infrastructure (e.g. Prometheus, Grafana, UptimeRobot) support polling an HTTP endpoint? If yes, AURORA's health endpoint can be added to the same monitoring setup.

If AURORA becomes unhealthy and the health check fails, who should be alerted on the Stream Luna side?

---

## Section 13 — Final Confirmation Checklist

Before AURORA begins any integration work, Stream Luna must confirm each item below. This is a sign-off checklist, not a suggestion.

- [ ] PostgreSQL read-only user `aurora_reader` created with SELECT grants on all tables in Section 2
- [ ] Full connection string provided to AURORA team securely
- [ ] Complete table schemas provided for all tables in Section 2 (exact column names, types, constraints, enum values)
- [ ] User ID and video ID formats confirmed with concrete examples
- [ ] Creator ID vs user ID relationship clarified unambiguously
- [ ] Confirmed list of which engagement events will be forwarded via Asynq
- [ ] Watch ratio measurement method confirmed
- [ ] Skip event detection method confirmed or absence acknowledged
- [ ] Asynq retry behavior for AURORA failures defined
- [ ] Redis host, port, database index, and password (if any) provided
- [ ] Docker network name provided
- [ ] VPS specs (CPU, RAM) provided
- [ ] Docker Compose integration approach confirmed (combined or external network)
- [ ] Service token generation and secure sharing method agreed
- [ ] Video status lifecycle and exact READY status string value confirmed
- [ ] Tag normalization behavior confirmed (cased, uncased, free-text or controlled)
- [ ] Existing events table schema provided or absence confirmed
- [ ] Feed resolver timeout value confirmed (AURORA recommends 3–5 seconds)
- [ ] Feed ordering preservation (re-ordering hydrated results to match AURORA's ranking) confirmed

No integration code will be written by the AURORA team until every item on this checklist is checked.
