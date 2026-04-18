# Discord Music & TTS Bot

A Discord bot with YouTube music playback and text-to-speech capabilities, powered by ElevenLabs.

## Features

- **Music Playback** — Play audio from YouTube URLs or search queries with a per-server queue system
- **Text-to-Speech** — Generate speech in a voice channel using ElevenLabs multilingual v2 model
- **Auto-Leave** — Automatically disconnects from voice channels when no humans remain (5s timeout)
- **Queue Management** — Full queue support with skip, stop, and queue listing

## Commands

| Command | Description |
|---------|-------------|
| `!pley <url or search>` | Play a YouTube video or add it to the queue |
| `!skip` | Skip the current track |
| `!stop` | Stop playback and clear the queue |
| `!queue` | Show the current queue |
| `!tts <text>` | Generate and play speech from text |
| `!setvoz <voice_id>` | Change the ElevenLabs voice ID |
| `!leave` | Disconnect the bot from the voice channel |

## Setup

### Prerequisites

- Python 3.10+
- FFmpeg installed and available in `PATH`
- Opus library (`libopus`) for voice encoding
- YouTube cookies file (optional, for restricted videos)

### Installation

```bash
git clone <repo-url>
cd disc-bot
python -m venv venv
source venv/bin/activate
pip install discord.py yt-dlp python-dotenv elevenlabs
```

### Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```env
DISCORD_TOKEN=your_discord_bot_token
ELEVENLABS_API_KEY=your_elevenlabs_api_key
VOICE_ID=JBFqnCBsd6RMkjVDRZzb
```

- **DISCORD_TOKEN** — Obtain from the [Discord Developer Portal](https://discord.com/developers/applications)
- **ELEVENLABS_API_KEY** — Obtain from [ElevenLabs](https://elevenlabs.io/)
- **VOICE_ID** — Default voice for TTS (find available voices in your ElevenLabs dashboard)

### Discord Bot Permissions

Enable the following in the Discord Developer Portal:

- **Intents**: Message Content Intent
- **Bot Permissions**: Connect, Speak, Send Messages

### Run

```bash
source venv/bin/activate
python app.py
```

## Notes

- The bot loads Opus from `/lib/x86_64-linux-gnu/libopus.so.0` by default. Adjust the path in `app.py` if needed.
- Place a `cookies.txt` file in the project root for yt-dlp to bypass YouTube age/login restrictions.
- Generated TTS audio files are cleaned up automatically after playback.
