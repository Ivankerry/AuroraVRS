param(
    [string]$BaseUrl = "http://localhost:8080",
    [switch]$SkipComposeUp,
    [switch]$NoDocker
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host "[FAIL] $Message" -ForegroundColor Red
    exit 1
}

function Pass([string]$Message) {
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Info([string]$Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Invoke-WithRetry {
    param(
        [scriptblock]$Action,
        [int]$Retries = 30,
        [int]$DelaySeconds = 2
    )

    for ($i = 1; $i -le $Retries; $i++) {
        try {
            return & $Action
        }
        catch {
            if ($i -eq $Retries) {
                throw
            }
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

if (-not $NoDocker) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Fail "Docker is required unless -NoDocker is specified."
    }
}

if ((-not $NoDocker) -and (-not $SkipComposeUp)) {
    Info "Starting stack with docker compose up -d --build"
    docker compose up -d --build | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail "docker compose up failed."
    }
    Pass "Compose stack started"
}

Info "Waiting for API health endpoint"
$health = Invoke-WithRetry -Action {
    Invoke-RestMethod -Method Get -Uri "$BaseUrl/health" -TimeoutSec 10
}
if ($health.status -ne "ok") {
    Fail "Health check returned unexpected payload."
}
Pass "Health endpoint is OK"

$stamp = Get-Date -Format "yyyyMMddHHmmssfff"
$email = "hmm-smoke-$stamp@example.com"
$password = "StrongPass123!"
$names = "HMM Smoke User"

Info "Registering synthetic smoke user $email"
$registerBody = @{
    email = $email
    password = $password
    names = $names
} | ConvertTo-Json

$auth = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/auth/register" -ContentType "application/json" -Body $registerBody
if (-not $auth.access_token) {
    Fail "Register succeeded but access_token missing."
}
$token = $auth.access_token
Pass "User registered and token acquired"

$headers = @{ Authorization = "Bearer $token" }
$me = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/users/me" -Headers $headers
if (-not $me.id) {
    Fail "Could not resolve user id via /users/me."
}
$userId = "$($me.id)"
Pass "Resolved user id $userId"

if ($NoDocker) {
        Info "Seeding one synthetic READY PUBLIC video via API /api/v1/videos/register"
        $videoId = [guid]::NewGuid().ToString()
        $registerVideoBody = @{
                id = $videoId
                title = "Synthetic Test Video"
                description = "HMM smoke test synthetic content"
                type = "QUICK"
                privacy = "PUBLIC"
                manifest_url = "synthetic.m3u8"
                categories = @("hmm-test-category")
                tags = @("hmm-test-tag")
                view_count = 1
                like_count = 0
        } | ConvertTo-Json -Depth 10

        $regResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/videos/register" -Headers $headers -ContentType "application/json" -Body $registerVideoBody
        if ("$($regResp.status)" -ne "success") {
                Fail "Video register endpoint did not return success."
        }
        Pass "Seeded video via API: $videoId"
}
else {
        Info "Seeding one synthetic READY PUBLIC video + tag mapping"
        $seedSql = @"
WITH u AS (
    SELECT id FROM users WHERE email = '$email' LIMIT 1
),
v AS (
    INSERT INTO videos (
        creator_id, title, description, type, privacy, status, duration_sec, view_count, like_count, avg_watch_ratio
    )
    SELECT id, 'Synthetic Test Video', 'HMM smoke test synthetic content', 'QUICK', 'PUBLIC', 'READY', 30, 1, 0, 0.1
    FROM u
    RETURNING id
),
t AS (
    INSERT INTO tags (name)
    VALUES ('hmm-test-tag')
    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
)
INSERT INTO video_tags (video_id, tag_id)
SELECT v.id, t.id FROM v, t
ON CONFLICT DO NOTHING;
"@

        $seedSql | docker compose exec -T db psql -U user -d db | Out-Null
        if ($LASTEXITCODE -ne 0) {
                Fail "Failed to seed synthetic video/tag in Postgres."
        }
        Pass "Seeded synthetic video"

        $videoId = (docker compose exec -T db psql -U user -d db -t -A -c "SELECT id FROM videos WHERE creator_id = '$userId' ORDER BY created_at DESC LIMIT 1;").Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($videoId)) {
                Fail "Could not fetch seeded video id."
        }
        Pass "Seeded video id: $videoId"
}

Info "Posting high-watch VIEW event to trigger HMM update path"
$eventBody = @{
    video_id = $videoId
    event_type = "VIEW"
    watch_ratio = 0.85
    metadata = @{}
} | ConvertTo-Json -Depth 5

$eventResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/events" -Headers $headers -ContentType "application/json" -Body $eventBody
if ("$($eventResp.status)" -ne "success") {
    Fail "Event ingestion did not return success."
}
Pass "Event ingested"

if ($NoDocker) {
    Info "Skipping direct Redis IV invariant check in -NoDocker mode (no container redis-cli)."
    $sum = [double]::NaN
    $min = [double]::NaN
}
else {
    Info "Validating Redis IV invariants (exists, sums to 1.0, floor >= 0.02)"
    $ivRaw = (docker compose exec -T redis redis-cli GET "iv:$userId").Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($ivRaw) -or $ivRaw -eq "(nil)") {
        Fail "Redis iv key missing for user $userId"
    }

    $ivObj = $ivRaw | ConvertFrom-Json
    $values = @()
    foreach ($p in $ivObj.PSObject.Properties) {
        $values += [double]$p.Value
    }
    if ($values.Count -eq 0) {
        Fail "Redis iv vector has no values."
    }

    $sum = ($values | Measure-Object -Sum).Sum
    $min = ($values | Measure-Object -Minimum).Minimum

    if ([math]::Abs($sum - 1.0) -gt 1e-6) {
        Fail "IV sum invariant failed. Sum=$sum"
    }
    if ($min -lt 0.02 - 1e-9) {
        Fail "IV floor invariant failed. Min=$min"
    }
    Pass "Redis IV invariants verified (sum=$sum, min=$min)"
}

Info "Requesting feed to verify end-to-end serving"
$feed = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/feed?page=1&limit=20&video_type=QUICK" -Headers $headers
if (-not $feed.videos -or $feed.videos.Count -lt 1) {
    Fail "Feed returned no videos."
}
Pass "Feed returned $($feed.videos.Count) video(s)"

Write-Host ""
Write-Host "=== Smoke Test Summary ===" -ForegroundColor Yellow
Write-Host "Base URL: $BaseUrl"
Write-Host "Mode: $(if ($NoDocker) { 'API-only (no Docker)' } else { 'Docker-backed' })"
Write-Host "User: $email"
Write-Host "User ID: $userId"
Write-Host "Video ID: $videoId"
Write-Host "IV Sum: $sum"
Write-Host "IV Min: $min"
Write-Host "Feed Count: $($feed.videos.Count)"
Write-Host "Result: PASS" -ForegroundColor Green
