# Unziper Bot (Telegram Archive Extractor)

A Python-based Telegram bot that receives archive files, extracts them, and sends extracted files back to users with progress updates.

---

## Project Overview

**Unziper Bot** is built with **Telethon** and focuses on archive automation inside Telegram chats.

Primary runtime file:
- `UNZIPPER_BOT_ULTRA.py`

---

## Features

- Accepts archive files from Telegram users
- Detects archive type and selects extraction logic automatically
- Supports multiple archive formats
- Sends live extraction progress updates
- Sends extracted files back to user
- Supports cancellation during extraction
- Cleans temporary files after completion/failure

---

## Supported Archive Formats

- `.zip`
- `.tar`
- `.gz`
- `.tgz`
- `.bz2`
- `.xz`
- `.tar.gz`
- `.tar.bz2`
- `.7z`
- `.rar`

> Note: `.7z` and `.rar` extraction requires **7zip** (`p7zip-full`) on the host system.

---

## Tech Stack

- **Language:** Python
- **Telegram client library:** Telethon
- **Archive handling:** `zipfile`, `tarfile`
- **External extraction tool:** `7z` (for `.rar` / `.7z`)
- **Async processing:** `asyncio`

---

## How It Works

1. User uploads an archive file to the bot.
2. Bot downloads it to a temporary working path.
3. Bot detects extension and applies extractor:
   - ZIP via `zipfile`
   - TAR family via `tarfile`
   - RAR/7Z via `7z`
4. Bot updates extraction status in chat.
5. Bot gathers extracted files and sends them back.
6. Bot removes temporary files/folders.

---

## Setup & Run

### 1) Clone repository
```bash
git clone https://github.com/harsh-vardhan-tech/Unziper-bot.git
cd Unziper-bot
```

### 2) Create virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows
```

### 3) Install dependencies
```bash
pip install telethon
sudo apt-get update
sudo apt-get install -y p7zip-full
```

### 4) Configure credentials
Set Telegram API credentials and bot token in runtime configuration.

### 5) Run bot
```bash
python3 UNZIPPER_BOT_ULTRA.py
```

---

## Security Notes

- Do not commit `api_id`, `api_hash`, or `BOT_TOKEN` in source code.
- Prefer environment variables or `.env` files.
- Rotate token immediately if exposed.

---

## License

Add a license file (MIT or preferred) if public reuse is intended.
