import os
import asyncio
import logging
from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager

from core.two_tower import TwoTowerModel
from core.faiss_index import FAISSIndex
from core.auth import require_admin

logger = logging.getLogger(__name__)

async def _rebuild_faiss_index(app: FastAPI):
    try:
        from core.db import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            import numpy as np, math, json
            from datetime import datetime

            tag_rows = await db.execute(text("SELECT video_id, tag_id FROM video_tags"))
            tag_map = {}
            for r in tag_rows.mappings():
                vid = str(r['video_id'])
                tag_map.setdefault(vid, []).append(str(r['tag_id']))

            rows = await db.execute(text("""
                SELECT v.id AS video_id, v.view_count, v.like_count, v.avg_watch_ratio,
                       v.created_at, v.duration_sec, vtv.vector
                FROM videos v
                LEFT JOIN video_tag_vectors vtv ON v.id = vtv.video_id
                WHERE v.status = 'READY' AND v.privacy = 'PUBLIC'
            """))

            embeddings = {}
            now = datetime.utcnow()
            for r in rows.mappings():
                vid_str = str(r['video_id'])
                vec = r['vector']
                if vec is not None:
                    if isinstance(vec, str):
                        vec = json.loads(vec)
                    embeddings[vid_str] = np.array(vec, dtype=np.float32)
                elif app.state.two_tower_model is not None:
                    created_at = r['created_at']
                    if created_at.tzinfo:
                        created_at = created_at.replace(tzinfo=None)
                    age_hours = (now - created_at).total_seconds() / 3600.0
                    views = r['view_count'] or 0
                    likes = r['like_count'] or 0
                    emb = await asyncio.to_thread(
                        app.state.two_tower_model.encode_video,
                        tag_map.get(vid_str, []),
                        math.log1p(views),
                        likes / max(views, 1),
                        float(r['avg_watch_ratio'] or 0.0),
                        min(age_hours, 7200) / 7200.0,
                        min(r['duration_sec'] or 0.0, 600) / 600.0
                    )
                    embeddings[vid_str] = emb

            await app.state.faiss_index.build(embeddings)
            logger.info(f"FAISS index rebuilt with {len(embeddings)} videos.")
    except Exception as e:
        logger.error(f"Error rebuilding FAISS index: {e}")

async def _faiss_rebuild_loop(app: FastAPI):
    while True:
        await asyncio.sleep(1800) # 30 mins
        await _rebuild_faiss_index(app)

async def _load_two_tower_model(app: FastAPI):
    model_path = "/app/storage/models/two_tower.pt"
    try:
        if os.path.exists(model_path):
            # Load in a thread to avoid blocking event loop
            model = await asyncio.to_thread(TwoTowerModel.load, model_path)
            app.state.two_tower_model = model
            logger.info("Two-Tower model loaded successfully.")
            return True
        else:
            logger.info("No Two-Tower model file found at startup.")
    except Exception as e:
        logger.error(f"Error loading Two-Tower model: {e}")
    
    app.state.two_tower_model = None
    return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.two_tower_model = None
    await _load_two_tower_model(app)
        
    app.state.faiss_index = FAISSIndex()
    app.state.faiss_task = asyncio.create_task(_faiss_rebuild_loop(app))
    asyncio.create_task(_rebuild_faiss_index(app))
    
    yield
    
    if hasattr(app.state, 'faiss_task'):
        app.state.faiss_task.cancel()


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

from routers import auth, users, feed, videos, events, misc
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(feed.router)
app.include_router(videos.router)
app.include_router(events.router)
app.include_router(misc.router)

@app.post("/api/v1/ml/reload-model", dependencies=[Depends(require_admin)])
async def reload_model():
    success = await _load_two_tower_model(app)
    return {"status": "success" if success else "failed", "detail": "Model reloaded" if success else "Model file not found or load error"}

@app.post("/api/v1/ml/rebuild-index", dependencies=[Depends(require_admin)])
async def rebuild_index():
    # Reload model first to ensure index uses latest embeddings
    await _load_two_tower_model(app)
    asyncio.create_task(_rebuild_faiss_index(app))
    return {"status": "rebuild triggered"}


@app.get("/api/v1/ml/status", dependencies=[Depends(require_admin)])
async def ml_status():
    from core.ranking import MIN_EVENTS_FOR_MODEL
    return {
        "model_loaded": app.state.two_tower_model is not None,
        "model_path": "/app/storage/models/two_tower.pt",
        "faiss_size": app.state.faiss_index.size(),
        "faiss_ready": app.state.faiss_index.is_ready(),
        "min_events_threshold": MIN_EVENTS_FOR_MODEL,
        "two_tower_active": app.state.two_tower_model is not None and app.state.faiss_index.is_ready()
    }
