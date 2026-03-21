import asyncio
import numpy as np
import sys
import os

# Robust path handling for VPS/Containers
sys.path.append(os.getcwd())

async def test_2026_ranking_logic():
    print("\n--- 🧪 Testing TikTok 2026 'Interest-First' Algorithm ---")
    try:
        from core.ranking import score_video
    except ImportError:
        print("❌ Error: Could not import ranking.py. Ensure you are running from the project root.")
        return

    # Mock Candidates for specific 2026 scenarios
    # 1. The 'Generic Viral' (High views/likes, moderate watch, no saves)
    v1 = {
        "id": "generic_viral",
        "view_count": 1000000,
        "like_count": 100000,
        "share_count": 5000,
        "save_count": 0,
        "avg_watch_ratio": 0.6,
        "tag_ids": []
    }
    
    # 2. The 'Deep Intent Niche' (Low views, but HIGH SAVES and interest match)
    v2 = {
        "id": "niche_high_intent",
        "view_count": 1000,
        "like_count": 10,
        "share_count": 50,
        "save_count": 500, # 50% save rate!
        "avg_watch_ratio": 0.8,
        "tag_ids": ["tag_music_niche"]
    }

    # 3. The 'Skipped Low-Quality' (Good likes but <10% watch ratio)
    v3 = {
        "id": "skipped_video",
        "view_count": 10000,
        "like_count": 1000,
        "share_count": 100,
        "save_count": 10,
        "avg_watch_ratio": 0.05, # < 10%
        "tag_ids": []
    }
    
    candidates = [v1, v2, v3]
    user_emb = np.zeros(128) 
    interest = {"tag_music_niche": 1.0} 
    
    scored = await score_video(candidates, user_emb, {}, interest)
    
    print("\nSimulation Results (Sorted by Final Score):")
    for score, v in sorted(scored, reverse=True):
        status = "✅ PASS" if score > 0 else "❌ FAIL (Penalized)"
        print(f"  - Video {v['id'].ljust(20)}: Score = {score:8.4f} | {status}")
    
    print("\nKey Takeaways:")
    print("1. 'niche_high_intent' should rank near 'generic_viral' because saves (25%) and interest (50%) carry more weight than raw likes in 2026.")
    print("2. 'skipped_video' should have a drastically lower (likely negative) score due to the -1.0 skip penalty.")

async def main():
    print("=========================================")
    print("AURORA-VRS: TIKTOK 2026 ALGORITHM SIMULATOR")
    print("=========================================")
    try:
        await test_2026_ranking_logic()
        print("\n✅ Verification Simulation Complete.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n❌ Error during verification: {e}")

if __name__ == "__main__":
    asyncio.run(main())
