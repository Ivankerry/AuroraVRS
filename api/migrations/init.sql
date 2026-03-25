CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    names TEXT,
    email TEXT UNIQUE,
    password_hash TEXT,
    phone_number TEXT,
    country TEXT,
    bio TEXT,
    avatar_url TEXT,
    role TEXT CHECK(role IN ('USER','ADMIN')) DEFAULT 'USER',
    is_verified BOOL DEFAULT FALSE,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    language TEXT DEFAULT 'en',
    location TEXT,
    appearance TEXT DEFAULT 'system',
    restricted_mode BOOL DEFAULT FALSE
);

CREATE TABLE user_privacy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    keep_account_private BOOL DEFAULT FALSE,
    keep_mentions_private BOOL DEFAULT FALSE,
    keep_subscriptions_private BOOL DEFAULT FALSE,
    allow_direct_messages BOOL DEFAULT TRUE,
    suggest_account_to_others BOOL DEFAULT TRUE
);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT UNIQUE,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE follows (
    follower_id UUID REFERENCES users(id) ON DELETE CASCADE,
    following_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (follower_id, following_id)
);

CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE
);

CREATE TABLE tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE
);

CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title TEXT,
    description TEXT,
    type TEXT CHECK(type IN ('QUICK','LONGFORM')),
    privacy TEXT CHECK(privacy IN ('PUBLIC','PRIVATE','UNLISTED')) DEFAULT 'PUBLIC',
    status TEXT CHECK(status IN ('UPLOADING','UPLOADED','PROCESSING','READY','FAILED')) DEFAULT 'UPLOADING',
    original_path TEXT,
    manifest_url TEXT,
    thumbnail_url TEXT,
    duration_sec FLOAT,
    file_size_bytes BIGINT,
    streaming_ready BOOL DEFAULT FALSE,
    view_count INT DEFAULT 0,
    like_count INT DEFAULT 0,
    dislike_count INT DEFAULT 0,
    comment_count INT DEFAULT 0,
    share_count INT DEFAULT 0,
    avg_watch_ratio FLOAT DEFAULT 0,
    impression_count INT DEFAULT 0,
    engagement_velocity FLOAT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE video_tags (
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    tag_id UUID REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (video_id, tag_id)
);

CREATE TABLE video_categories (
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    category_id UUID REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (video_id, category_id)
);

CREATE TABLE likes (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, video_id)
);

CREATE TABLE dislikes (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, video_id)
);

CREATE TABLE comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    content TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    event_type TEXT CHECK(event_type IN ('VIEW','WATCH','LIKE','SAVE','DISLIKE','SHARE','COMMENT','SKIP','SEARCH','PROFILE_VISIT')),
    watch_ratio FLOAT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_user_id ON events (user_id);
CREATE INDEX IF NOT EXISTS idx_events_created_at_type ON events (created_at DESC, event_type);

CREATE TABLE user_interest_vectors (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    vector vector(256),
    tag_weights JSONB DEFAULT '{}',
    event_count INT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE video_tag_vectors (
    video_id UUID PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
    vector vector(256),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE feed_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    seen_video_ids UUID[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE trending_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    engagement_velocity FLOAT,
    z_score FLOAT,
    tier TEXT,
    snapshot_at TIMESTAMPTZ DEFAULT NOW()
);
