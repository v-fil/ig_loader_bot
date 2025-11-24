# Instagram Loader Bot

Telegram bot for downloading videos from social media and sending them to Telegram channels.

## Supported Platforms

- **Instagram** - reels, posts, stories
- **TikTok** - videos
- **Twitter/X** - videos
- **Reddit** - videos with audio
- **YouTube Shorts** (disabled)

## Installation

### Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# System dependencies
sudo apt install ffmpeg  # for Reddit videos with audio

# Playwright browser
playwright install chromium
```

### Configuration

Create `ig_loader.sh` file based on `ig_loader.sh.sample`:

```bash
#!/bin/bash
source /path/to/venv/bin/activate
BOT_TOKEN=<YOUR_BOT_TOKEN> \
SENTRY_DSN=<SENTRY_DSN> \
python /path/to/ig_loader_bot/main.py
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BOT_TOKEN` | Telegram Bot API token | Yes |
| `SENTRY_DSN` | Sentry DSN for error monitoring | No |
| `DEBUG` | Debug mode (disables monitoring) | No |

## Running

```bash
./ig_loader.sh
```

Or directly:

```bash
BOT_TOKEN=<token> python main.py
```
