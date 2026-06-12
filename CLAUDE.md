# CLAUDE.md

Telegram bot (aiogram, Python 3.11+) that downloads media from Instagram /
TikTok / X / Threads links posted in chats. See README.md for the overview.

## Commands

```bash
.venv/bin/python -m pytest                 # offline tests (default; no network)
.venv/bin/python -m pytest -m live         # live smoke tests vs real services
.venv/bin/python tests/fixtures/capture.py [name [url]]   # refresh HTTP fixtures
BOT_TOKEN=... DEBUG=1 python main.py       # run locally (DEBUG skips newrelic/sentry)
```

## Deployment

Runs on this host as the systemd service `ig_loader.service`. The user
restarts it after deploys — do not restart it yourself unless asked.

## Architecture

- `main.py` — Dispatcher; every URL-bearing message fans out to
  `registry.run(provider, message, url)` under a 120 s timeout.
- `strategies/__init__.py` — the registry: per-provider strategy list,
  `extract_id`, optional `preprocess_url` (awaited before strategies run).
- `strategies/base.py` — `Registry.run` tries strategies in order until one
  returns an `Answer`; `ResultType` decides delivery (`video_url` →
  `upload_video`, `items_list` → `answer_with_album`, `url`/`text` → direct).
  A falsy strategy result moves to the next strategy.
- `strategies/utils.py` — upload pipeline: HEAD size check → Telegram URL
  upload → download fallback → ffmpeg transcode when over the 50 MB bot limit.
- `strategies/yt.py` is disabled in the registry (empty strategy list).

## Critical gotchas

- **Signed CDN URLs must hit the wire byte-for-byte.** Always fetch with
  `yarl.URL(url, encoded=True)`; yarl's default requoting decodes `%2F`/`%21`/
  `%2C` in query values and breaks IG's URL signatures. `aioresponses`
  normalizes URLs and CANNOT catch regressions here — the regression tests in
  `tests/test_upload_video.py` use a real localhost server instead.
- **TikTok short links:** the shortener 302s server-side clients (any
  User-Agent) to a degraded `tiktok.com/@/video/<id>` URL that snaptik
  rejects. `tiktok.preprocess_url` must keep the short form in that case.
- **IG `/reels/` vs `/reel/`:** both forms must route and extract
  (`FilterUrlRegex.instagram`, `ig.extract_id`).
- **The fastdl fixture self-expires:** its JS payload only emits output while
  `+new Date()` is below an embedded timestamp; `tests/test_fastdl.py` shims
  `Date` to the capture date. Details in `tests/fixtures/README.md`.
- **Threads sometimes serves a JS-only shell** on the first request; the live
  test retries once.
- `tmp/ig.session` is the instaloader session (gitignored, never commit).
  Without it IG runs anonymously and gets rate-limited (429/500).

## Test conventions

- Live tests carry the `live` marker and are excluded by default
  (`addopts = -m "not live"` in pyproject.toml). Run them manually before a
  commit; never enable them in CI (no IG session there, flaky externals).
- **Never invent social-media URLs** for tests or fixtures — always ask the
  user for real ones. The URLs in `tests/test_live_smoke.py` and
  `tests/fixtures/capture.py` are user-approved. The world_record_egg post
  (`/p/BsOGulcndj-`) was deliberately retired — do not reintroduce it.
- Fixtures are sanitized at capture (Meta session tokens redacted); keep
  `capture.py` doing that for new fixtures.
