import faiss
import numpy as np
import asyncio

class FAISSIndex:
    def __init__(self):
        self._index = None
        self._video_ids = []
        self._lock = asyncio.Lock()
        self._is_ready = False
        
    async def build(self, video_embeddings: dict[str, np.ndarray]):
        if not video_embeddings:
            async with self._lock:
                self._index = None
                self._video_ids = []
                self._is_ready = False
            return
            
        dim = 128
        new_index = faiss.IndexFlatIP(dim)
        
        new_video_ids = list(video_embeddings.keys())
        embeddings_list = [video_embeddings[vid][:128] for vid in new_video_ids]
        
        embeddings_arr = np.vstack(embeddings_list).astype(np.float32)
        new_index.add(embeddings_arr)
        
        async with self._lock:
            self._index = new_index
            self._video_ids = new_video_ids
            self._is_ready = True

    async def search(self, user_embedding: np.ndarray, k: int = 100) -> list[str]:
        try:
            async with self._lock:
                if not self._index or self._index.ntotal == 0:
                    return []
                index_snapshot = self._index
                ids_snapshot = self._video_ids

            user_emb = user_embedding.astype(np.float32).reshape(1, -1)
            
            def _do_search():
                return index_snapshot.search(user_emb, k)
                
            distances, indices = await asyncio.to_thread(_do_search)
            
            return [
                ids_snapshot[idx]
                for idx in indices[0]
                if idx != -1 and idx < len(ids_snapshot)
            ]
        except Exception:
            return []

    def is_ready(self) -> bool:
        return self._is_ready and self._index is not None and self._index.ntotal > 0

    def size(self) -> int:
        return self._index.ntotal if (self._index and self._is_ready) else 0
