# Unzipper Bot (single advanced version)

Use `UNZIPPER_BOT_V5.py` as the main bot file.

Features:
- Archive extract: zip, 7z, rar, tar, gz, tgz, bz2, xz
- Sends extracted video/image/audio/document correctly
- Multiple archive files in one album are accepted and processed
- Parallel extraction/download jobs

Secure setup (no hardcoded token):
1) Set environment variables:
   - `API_ID`
   - `API_HASH`
   - `BOT_TOKEN`
2) Install dependencies:
   - `pip install telethon cryptography aiohttp aiofiles yt-dlp requests`
3) Run:
   - `python UNZIPPER_BOT_V5.py`
