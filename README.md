# wizdo_1 — Telegram bot

A starter Telegram bot written in Python with
[python-telegram-bot](https://python-telegram-bot.org/).

## Setup

1. **Create a bot**: open Telegram, message [@BotFather](https://t.me/BotFather),
   send `/newbot`, and follow the prompts. BotFather gives you a token.
2. **Install dependencies** (Python 3.10+):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Add your token**:
   ```bash
   cp .env.example .env
   # then edit .env and paste your token
   ```
4. **Run it**:
   ```bash
   python bot.py
   ```
   Open your bot in Telegram and send `/start`.

## What it does

- `/start` — greets the user
- `/help` — lists commands
- Any other text — echoed back

Keep `.env` private: anyone with the token can control your bot.
