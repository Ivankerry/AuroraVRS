import asyncio
import numpy as np
import sys
import os

# Robust path handling for VPS/Containers
sys.path.append(os.getcwd())

async def test_normalization_logic():
    print("\n--- 🧪 Testing Ranking Normalization Algorithm ---")
    try:
        from api.core.ranking import score_video
    except ImportError:
        print("❌ Error: Could not import ranking.py. Ensure you are running from the project root.")
        return

    # Mock Candidates
    # 1. Viral Monster (Max engagement, but no similarity)
    v1 = {
        "id": "viral_1",
        "view_count": 1000000,
        "like_count": 100000,
        "comment_count": 10000,
        "avg_watch_ratio": 0.9,
        "tag_ids": []
    }
    # 2. Niche Gold (Low engagement, but perfect similarity)
    v2 = {
        "id": "niche_1",
        "view_count": 100,
        "like_count": 5,
        "comment_count": 1,
        "avg_watch_ratio": 0.4,
        "tag_ids": ["tag_123"]
    }
    
    candidates = [v1, v2]
    user_emb = np.zeros(128) 
    interest = {"tag_123": 10.0} # Strong niche interest
    
    # We pass empty video_embeddings_map to force Tag Similarity fallback
    scored = await score_video(candidates, user_emb, {}, interest)
    
    print("\nResults:")
    for score, v in sorted(scored, reverse=True):
        print(f"  - Video {v['id']}: Score = {score:.4f}")
    
    # Validation Logic
    scores = [s[0] for s in scored]
    ratio = max(scores) / min(scores) if min(scores) > 0 else 999
    
    if ratio < 10:
        print("\n✅ SUCCESS: Normalization is working. Niche video is competitive with Viral Monster.")
    else:
        print("\n⚠️ WARNING: Score gap is high. Check normalization logic.")

async def main():
    print("=========================================")
    print("AURORA-VRS RANKING DIAGNOSTICS")
    print("=========================================")
    try:
        await test_normalization_logic()
        print("\n✅ Verification Simulation Complete.")
    except Exception as e:
        print(f"\n❌ Error during verification: {e}")

if __name__ == "__main__":
    asyncio.run(main())
