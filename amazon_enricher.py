import asyncio
import os
import json
import random
import uuid
import asyncpg
import requests
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

# Expanded Seed Data (50+ Movies/Shows across all categories)
SAMPLE_MOVIES = [
    # TECH & SCI-FI
    {"title": "The Matrix Revolutions", "cats": ["Tech", "Sci-Fi"], "desc": "Neo and the rebel leaders estimate that they have very little time before 250,000 Sentinels destroy Zion."},
    {"title": "Interstellar", "cats": ["Tech", "Sci-Fi", "Drama"], "desc": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival."},
    {"title": "The Social Network", "cats": ["Tech", "Comedy"], "desc": "As Harvard student Mark Zuckerberg creates the social networking site that would become Facebook, he is sued by the twins who claimed he stole their idea."},
    {"title": "Silicon Valley", "cats": ["Tech", "Comedy"], "desc": "Follows the struggle of Richard Hendricks, a Silicon Valley engineer who tries to build his own company called Pied Piper."},
    {"title": "Black Mirror", "cats": ["Tech", "Sci-Fi", "Drama"], "desc": "An anthology series exploring a twisted, high-tech multiverse where humanity's greatest innovations and darkest instincts collide."},
    {"title": "Halt and Catch Fire", "cats": ["Tech", "Drama"], "desc": "Set in the 1980s, this series dramatizes the personal computing boom through the eyes of a visionary, an engineer and a prodigy."},
    {"title": "Mr. Robot", "cats": ["Tech", "Drama"], "desc": "Elliot, a brilliant but highly unstable young cyber-security engineer and vigilante hacker, becomes a key figure in a complex game of global dominance."},
    {"title": "The Imitation Game", "cats": ["Tech", "Drama"], "desc": "During World War II, the English mathematical genius Alan Turing tries to crack the German Enigma code with help from fellow mathematicians."},
    
    # GAMING
    {"title": "Cyberpunk: Edgerunners", "cats": ["Gaming", "Sci-Fi", "Tech"], "desc": "In a dystopia riddled with corruption and cybernetic implants, a talented but reckless street kid strives to become a mercenary outlaw."},
    {"title": "The Witcher", "cats": ["Gaming", "Fantasy"], "desc": "Geralt of Rivia, a solitary monster hunter, struggles to find his place in a world where people often prove more wicked than beasts."},
    {"title": "Arcane", "cats": ["Gaming", "Sci-Fi", "Drama"], "desc": "Set in utopian Piltover and the oppressed underground of Zaun, the story follows the origins of two iconic League champions-and the power that will tear them apart."},
    {"title": "Ready Player One", "cats": ["Gaming", "Sci-Fi"], "desc": "When the creator of a virtual reality called the OASIS dies, he makes a posthumous challenge to all OASIS users to find his Easter Egg."},
    {"title": "Wreck-It Ralph", "cats": ["Gaming", "Comedy"], "desc": "A video game villain wants to be a hero and sets out to fulfill his dream, but his quest brings havoc to the whole arcade where he lives."},
    {"title": "The Last of Us", "cats": ["Gaming", "Drama"], "desc": "After a global pandemic destroys civilization, a hardened survivor takes charge of a 14-year-old girl who may be humanity's last hope."},
    {"title": "Free Guy", "cats": ["Gaming", "Comedy"], "desc": "A bank teller discovers that he's actually an NPC inside a brutal, open world video game."},
    {"title": "Pixels", "cats": ["Gaming", "Comedy"], "desc": "When aliens misinterpret video feeds of classic arcade games as a declaration of war, they attack the Earth using the games as models."},

    # MUSIC
    {"title": "Whiplash", "cats": ["Music", "Drama"], "desc": "A promising young drummer enrolls at a cut-throat music conservatory where his dreams of greatness are mentored by an instructor who will stop at nothing."},
    {"title": "Bohemian Rhapsody", "cats": ["Music", "Drama"], "desc": "The story of the legendary British rock band Queen and their lead singer Freddie Mercury, leading up to their famous performance at Live Aid (1985)."},
    {"title": "A Star Is Born", "cats": ["Music", "Drama"], "desc": "A musician helps a young singer find fame as age and alcoholism send his own career into a downward spiral."},
    {"title": "Straight Outta Compton", "cats": ["Music", "Drama"], "desc": "The story of the pioneering hip-hop group N.W.A, and its members Eazy-E, Dr. Dre, and Ice Cube."},
    {"title": "School of Rock", "cats": ["Music", "Comedy"], "desc": "After being kicked out of his rock band, Dewey Finn becomes a substitute teacher of a strict elementary private school, only to try and turn it into a rock band."},
    {"title": "The Greatest Showman", "cats": ["Music", "Drama"], "desc": "Celebrates the birth of show business and tells of a visionary who rose from nothing to create a spectacle that became a worldwide sensation."},
    {"title": "Yesterday", "cats": ["Music", "Comedy"], "desc": "A struggling musician realizes he's the only person on Earth who can remember The Beatles after waking up in an alternate timeline."},
    {"title": "Coco", "cats": ["Music", "Fantasy"], "desc": "Aspiring musician Miguel, confronted with his family's ancestral ban on music, enters the Land of the Dead to find his great-great-grandfather, a legendary singer."},

    # EDUCATION
    {"title": "Planet Earth", "cats": ["Education", "Sci-Fi"], "desc": "Emmy Award-winning, 11-part nature documentary series from the BBC, five years in the making and the most expensive nature documentary series ever commissioned by the BBC."},
    {"title": "Cosmos: A Spacetime Odyssey", "cats": ["Education", "Tech"], "desc": "An exploration of our discovery of the laws of nature and coordinates in space and time."},
    {"title": "The Mind, Explained", "cats": ["Education"], "desc": "Ever wonder what's happening inside your head? From dreaming to anxiety disorders, discover how your brain works with this illuminating series."},
    {"title": "Abstract: The Art of Design", "cats": ["Education", "Tech"], "desc": "Step inside the minds of the most innovative designers in a variety of disciplines and learn how design impacts every aspect of life."},
    {"title": "Our Planet", "cats": ["Education"], "desc": "Documentary series focusing on the breadth of the diversity of habitats around the world, from the remote Arctic wilderness to the jungles of South America."},
    {"title": "Explained", "cats": ["Education", "Tech"], "desc": "This enlightening series from Vox digs into a wide range of topics such as the rise of cryptocurrency, why diets fail, and the wild world of K-pop."},
    {"title": "Apollo 11", "cats": ["Education", "Tech"], "desc": "A look at the Apollo 11 mission to land on the moon led by commander Neil Armstrong and pilots Buzz Aldrin and Michael Collins."},
    {"title": "Dead Poets Society", "cats": ["Education", "Drama"], "desc": "English teacher John Keating inspires his students to look at poetry with a different perspective of authentic self-expression."},

    # COMEDY
    {"title": "The Office", "cats": ["Comedy"], "desc": "A mockumentary on a group of typical office workers, where the workday consists of ego clashes, inappropriate behavior, and tedium."},
    {"title": "Brooklyn Nine-Nine", "cats": ["Comedy"], "desc": "Detective Jake Peralta, a talented and carefree cop, and his diverse group of colleagues investigate crimes in the 99th Precinct of the NYPD."},
    {"title": "Parks and Recreation", "cats": ["Comedy"], "desc": "The absurd antics of Indiana town's public officials as they pursue sundry projects to make their city a better place."},
    {"title": "The Big Bang Theory", "cats": ["Comedy", "Tech"], "desc": "A woman who moves into an apartment next door to two brilliant but socially awkward physicists shows them how little they know about life outside of the laboratory."},
    {"title": "Friends", "cats": ["Comedy"], "desc": "Follows the personal and professional lives of six twenty to thirty-something-year-old friends living in Manhattan."},
    {"title": "Superbad", "cats": ["Comedy"], "desc": "Two co-dependent high school seniors are forced to deal with separation anxiety after their plan to stage a booze-soaked party goes awry."},
    {"title": "Curb Your Enthusiasm", "cats": ["Comedy"], "desc": "The life and times of Larry David and the various predicaments he gets himself into with his friends and complete strangers."},
    {"title": "Modern Family", "cats": ["Comedy"], "desc": "Three different but related families face trials and tribulations in their own uniquely comedic ways."},

    # DRAMA & FANTASY
    {"title": "Breaking Bad", "cats": ["Drama"], "desc": "A high school chemistry teacher diagnosed with inoperable lung cancer turns to manufacturing and selling methamphetamine in order to secure his family's future."},
    {"title": "Game of Thrones", "cats": ["Drama", "Fantasy"], "desc": "Nine noble families fight for control over the lands of Westeros, while an ancient enemy returns after being dormant for millennia."},
    {"title": "Stranger Things", "cats": ["Drama", "Sci-Fi", "Fantasy"], "desc": "When a young boy disappears, his mother, a police chief and his friends must confront terrifying supernatural forces in order to get him back."},
    {"title": "Lord of the Rings", "cats": ["Fantasy", "Drama"], "desc": "A meek Hobbit from the Shire and eight companions set out on a journey to destroy the powerful One Ring and save Middle-earth from the Dark Lord Sauron."},
    {"title": "Parasite", "cats": ["Drama", "Comedy"], "desc": "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan."},
    {"title": "Succession", "cats": ["Drama", "Comedy"], "desc": "The Roy family is known for controlling the biggest media and entertainment company in the world. However, their world changes when their father steps down from the company."},
    {"title": "The Queen's Gambit", "cats": ["Drama"], "desc": "Orphaned at nine, prodigious chess player Beth Harmon struggles with addiction while on a quest to become the greatest chess player in the world."},
    {"title": "Chernobyl", "cats": ["Drama", "Education"], "desc": "In April 1986, an explosion at the Chernobyl nuclear power plant in the Union of Soviet Socialist Republics becomes one of the world's worst man-made catastrophes."},
]

async def enrich_from_amazon():
    print("\n" + "═" * 80)
    print("       🚀 AURORA-VRS AMAZON METADATA ENRICHER (BEEF VERSION)")
    print("═" * 80)
    
    conn = await asyncpg.connect(DATABASE_URL)

    # 1. Sync Categories
    categories = list(set([c for m in SAMPLE_MOVIES for c in m.get("cats", [])]))
    print(f"📦 Syncing categories: {', '.join(categories)}")
    
    for cat in categories:
        await conn.execute("""
            INSERT INTO categories (id, name)
            VALUES ($1, $2)
            ON CONFLICT (name) DO NOTHING
        """, uuid.uuid4(), cat)

    # 2. Add Anchor Videos
    print(f"\n🎥 Injecting {len(SAMPLE_MOVIES)} Semantic Anchor Videos...")
    
    count = 0
    now = datetime.utcnow()
    
    for movie in SAMPLE_MOVIES:
        v_id = uuid.uuid4()
        title = movie.get("title")
        desc = movie.get("desc")
        cats = movie.get("cats", [])
        
        # Insert video
        await conn.execute("""
            INSERT INTO videos (id, title, description, privacy, status, created_at, view_count, like_count, duration_sec)
            VALUES ($1, $2, $3, 'PUBLIC', 'READY', $4, $5, $6, $7)
            ON CONFLICT DO NOTHING
        """, v_id, title, desc, now, random.randint(100, 1000), random.randint(10, 50), random.randint(30, 180))
        
        # Link to categories
        for cat_name in cats:
            cat_id = await conn.fetchval("SELECT id FROM categories WHERE name = $1", cat_name)
            if cat_id:
                await conn.execute("""
                    INSERT INTO video_categories (video_id, category_id)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                """, v_id, cat_id)
        
        if count % 10 == 0:
            print(f"  ... Injecting {count}/{len(SAMPLE_MOVIES)}")
        count += 1

    await conn.close()
    print(f"\n🚀 SUCCESS: Injected {count} high-quality anchor videos.")
    print("═" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(enrich_from_amazon())
