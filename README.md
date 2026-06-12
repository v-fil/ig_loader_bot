# ig_loader_bot

Telegram bot that turns social-media links into the media itself: post a
message containing an Instagram / TikTok / X (Twitter) / Threads link and the
bot replies with the video, photo, album or text.

## How it works

Any message matching a URL ([`main.py`](main.py), `UrlFilter`) is routed by
`get_provider_by_url` to a provider, and the `Registry`
([`strategies/base.py`](strategies/base.py)) runs that provider's strategies
in order until one produces a result:

| Provider | Strategies (in order) |
| --- | --- |
| Instagram (`/p/`, `/reel(s)/`, `/share/`) | instaloader (authenticated), fastdown.to (dukpy), fastdown.to (Playwright) |
| TikTok (full and `vt.`/`vm.` short links) | snaptik.pro |
| X / Twitter | fxtwitter API |
| Threads | embedded-JSON parser (unrolls the OP chain with text + images) |
| YouTube Shorts | disabled |

Delivery (`strategies/utils.py`): videos are uploaded by URL when they fit
Telegram's 50 MB bot limit, otherwise downloaded and, if needed, transcoded
with ffmpeg; albums are sent as media groups in chunks of 10; long texts are
split under Telegram's message limits.

## Requirements

- Python 3.11+
- `ffmpeg`/`ffprobe` — transcoding oversized videos
- Playwright Chromium for the Instagram fallback strategy:
  `playwright install chromium`

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

- `BOT_TOKEN` (required) — Telegram bot token.
- `tmp/ig.session` — instaloader session file; without it Instagram requests
  are anonymous and get rate-limited hard. Create it with
  `instaloader --login <user>` and copy the resulting session file.
- `DEBUG=1` — skips New Relic/Sentry init and runs Playwright headed.
- `SENTRY_DSN`, `newrelic.ini` — optional, production telemetry
  (samples: `newrelic.ini.sample`, `ig_loader.sh.sample`).

Run with `python main.py` (see `ig_loader.sh.sample` for a launcher; in
production the bot runs as a systemd service).

## Tests

```bash
.venv/bin/python -m pytest            # offline suite, no network
.venv/bin/python -m pytest -m live    # live smoke tests, run before a commit
```

Live tests hit the real external services and are excluded by default;
the instaloader ones skip automatically when `tmp/ig.session` is missing.
HTTP fixtures are captured from the real services — see
[`tests/fixtures/README.md`](tests/fixtures/README.md) for re-capture
instructions when a scraped site changes.
