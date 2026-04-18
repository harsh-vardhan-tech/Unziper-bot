# ═══════════════════════════════════════════════════════════════════════
#  🚀 ULTRA ADVANCED UNZIPPER + LINK DOWNLOADER BOT
#  Admin: @F88UF  |  Channel: @F88UF9844
#  Features: Unzip • Link Download • 24/7 Keep-Alive • Policy Gate
#            1000+ users • Progress bars • Cancel • Forward cleaner
#  Run:  python bot.py
# ═══════════════════════════════════════════════════════════════════════

import subprocess, sys, os, threading

# ── Auto-install all dependencies ───────────────────────────────────────
_REQUIRED = [
    "telethon", "cryptography", "aiohttp", "aiofiles",
    "yt-dlp", "requests"
]
for _pkg in _REQUIRED:
    try:
        __import__(_pkg.replace("-", "_"))
    except ImportError:
        print(f"📦 Installing {_pkg}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", _pkg],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

# ── Stdlib ───────────────────────────────────────────────────────────────
import asyncio, zipfile, shutil, tarfile, time, re, logging, json
from pathlib import Path
from base64 import b64decode
from urllib.parse import urlparse
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Third-party ──────────────────────────────────────────────────────────
import aiohttp
import aiofiles
import yt_dlp
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import (
    ChannelParticipantAdmin, ChannelParticipantCreator,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.WARNING
)

# ═══════════════════════════════════════════════════════════════════════
#  CREDENTIALS  (base64 encoded — to change, encode your value:)
#  python3 -c "import base64; print(base64.b64encode(b'YOUR_VAL').decode())"
# ═══════════════════════════════════════════════════════════════════════
_AI = int(b64decode("Mjk2NDM0NzQ=").decode())
_AH = b64decode("NDkxNjMzZjAzNGMxYjUwYjFiYzBmMWU0ZDJiNDI2ZTM=").decode()
_BT = b64decode("ODcyMzk2NTI5MzpBQUdfd0hOZTkzNERNVHVTRlpZTFhNNDVXajN3dEdMTEdDUQ==").decode()

# ═══════════════════════════════════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════════════════════════════════
ADMIN_USERNAME  = "F88UF"
CHANNEL_HANDLE  = "@F88UF9844"
CHANNEL_LINK    = "https://t.me/F88UF9844"
BOT_TAG         = "@F88UF9844"
AUTO_DEL_SEC    = 90
MAX_PARALLEL    = 20          # simultaneous extractions (raised for scale)
MAX_LINK_DL     = 10          # simultaneous link downloads
KEEP_ALIVE_PORT = 8080        # UptimeRobot pings this
WORK_DIR        = Path("/tmp/uzbot")
SESSIONS_FILE   = Path("/tmp/uzbot_sessions.json")
WORK_DIR.mkdir(parents=True, exist_ok=True)

ARCHIVE_EXTS = {
    ".zip", ".7z", ".rar", ".tar",
    ".gz", ".tgz", ".bz2", ".xz",
}
VIDEO_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
    ".webm", ".m4v", ".mpg", ".mpeg", ".3gp",
    ".ts", ".m2ts", ".vob", ".rmvb", ".divx",
}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
AUDIO_EXTS = {".mp3", ".flac", ".aac", ".ogg", ".wav", ".m4a", ".opus"}

# Sites supported by yt-dlp (partial list for display)
SUPPORTED_SITES = (
    "YouTube • Instagram • Twitter/X • Facebook • TikTok • Vimeo\n"
    "Reddit • Dailymotion • Twitch • Pinterest • SoundCloud\n"
    "Direct .zip/.rar/.7z/.mp4/.pdf links + 1000s more sites"
)

POLICY_TEXT = (
    "📋 *Terms of Service & Policy*\n\n"
    "By using this bot, you agree:\n\n"
    "1️⃣ This bot is a *utility tool* only.\n"
    "2️⃣ You are *solely responsible* for any files you process.\n"
    "3️⃣ Do NOT use for illegal, 18+, or pirated content.\n"
    "4️⃣ The admin/bot bears *zero liability* for misuse.\n"
    "5️⃣ Abuse will result in permanent ban.\n\n"
    "⚠️ _All responsibility lies with the user._\n\n"
    "Tap ✅ *Accept* to start using the bot."
)

# ═══════════════════════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════════════════════
client = TelegramClient("uzbot_session", _AI, _AH).start(bot_token=_BT)

_flag_map: dict[str, dict] = {}
_sem_extract = asyncio.Semaphore(MAX_PARALLEL)
_sem_link    = asyncio.Semaphore(MAX_LINK_DL)

# Accepted policy users (persisted to file)
def _load_accepted() -> set:
    try:
        if SESSIONS_FILE.exists():
            return set(json.loads(SESSIONS_FILE.read_text()))
    except Exception:
        pass
    return set()

def _save_accepted(s: set):
    try:
        SESSIONS_FILE.write_text(json.dumps(list(s)))
    except Exception:
        pass

_policy_accepted: set = _load_accepted()

# Per-chat channel destinations {chat_id: "@channel"}
_dest_channels: dict[int, str] = {}

# Forward store {key: event}
_fwd_store: dict[str, dict] = {}

# ═══════════════════════════════════════════════════════════════════════
#  KEEP-ALIVE WEB SERVER  (for UptimeRobot 24/7 pinging)
# ═══════════════════════════════════════════════════════════════════════
class _PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, *args):
        pass  # suppress server logs

def _start_keep_alive():
    server = HTTPServer(("0.0.0.0", KEEP_ALIVE_PORT), _PingHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"🌐 Keep-alive server running on port {KEEP_ALIVE_PORT}")

# ═══════════════════════════════════════════════════════════════════════
#  UTILS
# ═══════════════════════════════════════════════════════════════════════
def human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

def pbar(done: int, total: int, w: int = 18) -> str:
    p = min(done / total, 1.0) if total else 0
    f = int(w * p)
    return f"[{'█' * f}{'░' * (w - f)}] {p * 100:.0f}%"

def suffix(path) -> str:
    return Path(str(path)).suffix.lower()

def is_archive(name: str) -> bool:
    n = name.lower()
    if n.endswith(".tar.gz") or n.endswith(".tar.bz2"):
        return True
    return suffix(name) in ARCHIVE_EXTS

def is_video(name: str) -> bool:
    return suffix(name) in VIDEO_EXTS

def is_image(name: str) -> bool:
    return suffix(name) in IMAGE_EXTS

def is_audio(name: str) -> bool:
    return suffix(name) in AUDIO_EXTS

def is_url(text: str) -> bool:
    try:
        r = urlparse(text.strip())
        return r.scheme in ("http", "https") and bool(r.netloc)
    except Exception:
        return False

def extract_urls(text: str) -> list:
    return re.findall(r'https?://[^\s<>"]+', text or "")

def strip_promo(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"@\w+", f"@{ADMIN_USERNAME}", text)
    text = re.sub(r"https?://t\.me/\S+", CHANNEL_LINK, text)
    return text.strip()

def file_caption(fname: str, sz: int, idx: int, total: int, source: str = "") -> str:
    src_line = f"🔗 Source: {source}\n" if source else ""
    return (
        f"📄 `{fname}`\n"
        f"{src_line}"
        f"📦 {human(sz)}  •  {idx}/{total}\n\n"
        f"_Processed by {BOT_TAG}_"
    )

async def auto_del(msg, delay: int = AUTO_DEL_SEC):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass

async def cleanup(*paths):
    for p in paths:
        try:
            if os.path.isfile(p):
                os.remove(p)
            elif os.path.isdir(p):
                shutil.rmtree(p)
        except Exception:
            pass

def bot_footer() -> str:
    return f"📢 Channel: {CHANNEL_LINK}\n👤 Admin: @{ADMIN_USERNAME}"

# ═══════════════════════════════════════════════════════════════════════
#  POLICY GATE
# ═══════════════════════════════════════════════════════════════════════
async def check_policy(event) -> bool:
    """Returns True if user accepted policy, else sends policy message."""
    uid = event.sender_id
    if uid in _policy_accepted:
        return True

    await event.reply(
        POLICY_TEXT,
        parse_mode="markdown",
        buttons=[[
            Button.inline("✅ I Accept — Start Bot", data=f"policy:accept:{uid}"),
        ]],
    )
    return False

@client.on(events.CallbackQuery(pattern=rb"policy:accept:(\d+)"))
async def cb_policy_accept(event):
    uid = int(event.data.decode().split(":")[-1])
    if event.sender_id != uid:
        await event.answer("❌ This is not your button!", alert=True)
        return
    _policy_accepted.add(uid)
    _save_accepted(_policy_accepted)
    await event.answer("✅ Policy accepted! You can now use the bot.", alert=False)
    try:
        await event.edit(
            "✅ *Policy Accepted!*\n\n"
            "You can now use all features.\n"
            "Send /start to see the menu.",
            parse_mode="markdown",
        )
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════
#  CHANNEL ADMIN CHECK
# ═══════════════════════════════════════════════════════════════════════
async def bot_is_admin_in(channel) -> bool:
    try:
        me = await client.get_me()
        part = await client(GetParticipantRequest(channel, me.id))
        return isinstance(
            part.participant, (ChannelParticipantAdmin, ChannelParticipantCreator)
        )
    except Exception:
        return False

# ═══════════════════════════════════════════════════════════════════════
#  EXTRACTION ENGINE
# ═══════════════════════════════════════════════════════════════════════
async def extract_archive(
    zip_path: Path,
    out_dir: Path,
    flag: dict,
    status_cb,
) -> list | None:
    ext = zip_path.suffix.lower()
    name = zip_path.name.lower()
    out_files: list[Path] = []

    async def upd(text: str):
        try:
            await status_cb(text)
        except Exception:
            pass

    # ── ZIP ──────────────────────────────────────────────────
    if ext == ".zip":
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                members = zf.infolist()
                total_sz = sum(m.file_size for m in members) or 1
                done_sz = 0
                t_last = 0
                for m in members:
                    if flag["stop"]:
                        return None
                    zf.extract(m, out_dir)
                    done_sz += m.file_size
                    p = out_dir / m.filename
                    if p.is_file():
                        out_files.append(p)
                    if time.time() - t_last > 1.8:
                        await upd(
                            f"⚡ *Extracting ZIP*\n\n"
                            f"`{pbar(done_sz, total_sz)}`\n"
                            f"{human(done_sz)} / {human(total_sz)}\n"
                            f"📄 `{Path(m.filename).name[:45]}`"
                        )
                        t_last = time.time()
        except zipfile.BadZipFile:
            await upd("❌ Corrupted or invalid ZIP file.")
            return []

    # ── TAR family ───────────────────────────────────────────
    elif ext in (".tar", ".gz", ".tgz", ".bz2", ".xz") or name.endswith(
        (".tar.gz", ".tar.bz2")
    ):
        try:
            with tarfile.open(zip_path, "r:*") as tf:
                members = tf.getmembers()
                total_sz = sum(m.size for m in members) or 1
                done_sz = 0
                t_last = 0
                for m in members:
                    if flag["stop"]:
                        return None
                    tf.extract(m, out_dir, set_attrs=False)
                    done_sz += m.size
                    p = out_dir / m.name
                    if p.is_file():
                        out_files.append(p)
                    if time.time() - t_last > 1.8:
                        await upd(
                            f"⚡ *Extracting TAR*\n\n"
                            f"`{pbar(done_sz, total_sz)}`\n"
                            f"{human(done_sz)} / {human(total_sz)}"
                        )
                        t_last = time.time()
        except Exception as e:
            await upd(f"❌ TAR error: `{e}`")
            return []

    # ── 7Z / RAR ─────────────────────────────────────────────
    elif ext in (".7z", ".rar"):
        r = subprocess.run(["which", "7z"], capture_output=True)
        if r.returncode != 0:
            await upd("⏳ Installing 7zip (one-time)…")
            subprocess.run(
                ["apt-get", "install", "-y", "p7zip-full"],
                capture_output=True,
            )
        await upd(f"⚡ *Extracting {ext.upper()}*…\n\n⏳ Please wait…")
        proc = await asyncio.create_subprocess_exec(
            "7z", "x", str(zip_path), f"-o{out_dir}", "-y",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        t_last = time.time()
        while proc.returncode is None:
            if flag["stop"]:
                proc.kill()
                return None
            await asyncio.sleep(0.8)
            if time.time() - t_last > 2:
                await upd(f"⚡ *Extracting {ext.upper()}*…\n\n⏳ Running…")
                t_last = time.time()
        await proc.wait()
        if proc.returncode != 0:
            err = (await proc.stderr.read()).decode(errors="ignore")[:300]
            await upd(f"❌ 7z error:\n`{err}`")
            return []
        for root, _, fs in os.walk(out_dir):
            for f in fs:
                out_files.append(Path(root) / f)

    else:
        await upd(f"❌ Unsupported format: `{ext}`")
        return []

    return out_files

# ═══════════════════════════════════════════════════════════════════════
#  LINK DOWNLOADER (yt-dlp + direct HTTP)
# ═══════════════════════════════════════════════════════════════════════
async def download_link(
    url: str,
    out_dir: Path,
    flag: dict,
    status_cb,
) -> list | None:
    """Download a URL. Returns list of downloaded file paths or None on cancel."""
    out_files: list[Path] = []

    async def upd(text: str):
        try:
            await status_cb(text)
        except Exception:
            pass

    await upd(
        f"🔗 *Downloading from link…*\n\n"
        f"`{url[:60]}{'…' if len(url) > 60 else ''}`\n\n"
        f"⏳ Please wait…"
    )

    # Try yt-dlp first (handles YouTube, Instagram, TikTok, etc.)
    ydl_out = str(out_dir / "%(title).80s.%(ext)s")
    ydl_opts = {
        "outtmpl": ydl_out,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "noplaylist": True,
    }

    loop = asyncio.get_event_loop()

    def _ydl_download():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info
        except Exception as e:
            return e

    result = await loop.run_in_executor(None, _ydl_download)

    if isinstance(result, Exception):
        # yt-dlp failed → try direct HTTP download
        await upd(
            f"🔗 *Direct download…*\n\n"
            f"`{url[:60]}{'…' if len(url) > 60 else ''}`"
        )
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=600)) as resp:
                    if resp.status != 200:
                        await upd(f"❌ HTTP {resp.status}: cannot download link.")
                        return []

                    total_size = int(resp.headers.get("Content-Length", 0))
                    # Guess filename from URL or Content-Disposition
                    cd = resp.headers.get("Content-Disposition", "")
                    fname_match = re.search(r'filename="?([^";]+)"?', cd)
                    if fname_match:
                        fname = fname_match.group(1).strip()
                    else:
                        fname = Path(urlparse(url).path).name or "downloaded_file"
                    if not Path(fname).suffix:
                        ctype = resp.content_type or ""
                        ext_map = {
                            "video/mp4": ".mp4", "video/webm": ".webm",
                            "image/jpeg": ".jpg", "image/png": ".png",
                            "image/gif": ".gif", "application/zip": ".zip",
                            "application/x-rar-compressed": ".rar",
                            "application/pdf": ".pdf",
                            "application/octet-stream": ".bin",
                        }
                        for ct, ex in ext_map.items():
                            if ct in ctype:
                                fname += ex
                                break

                    dl_path = out_dir / fname
                    done = 0
                    t_last = 0
                    async with aiofiles.open(dl_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(65536):
                            if flag["stop"]:
                                return None
                            await f.write(chunk)
                            done += len(chunk)
                            if time.time() - t_last > 1.8:
                                pb = pbar(done, total_size) if total_size else "⏳"
                                await upd(
                                    f"📥 *Downloading*\n\n"
                                    f"`{fname[:45]}`\n"
                                    f"`{pb}`\n"
                                    f"{human(done)}"
                                    + (f" / {human(total_size)}" if total_size else "")
                                )
                                t_last = time.time()

                    out_files.append(dl_path)
        except Exception as e:
            await upd(f"❌ Download failed: `{e}`")
            return []
    else:
        # yt-dlp succeeded
        for fp in out_dir.iterdir():
            if fp.is_file():
                out_files.append(fp)

    return out_files

# ═══════════════════════════════════════════════════════════════════════
#  SEND FILES
# ═══════════════════════════════════════════════════════════════════════
async def send_files(
    chat_id,
    files: list,
    flag: dict,
    status_msg,
    dest_channel=None,
    source_url: str = "",
):
    total = len(files)
    sent = 0
    skipped = []
    target = dest_channel or chat_id

    for i, fp in enumerate(files, 1):
        if flag["stop"]:
            break
        if not fp.exists():
            continue

        sz = fp.stat().st_size
        name = fp.name

        try:
            await status_msg.edit(
                f"📤 *Sending* `{name}`\n"
                f"`{pbar(i - 1, total)}`\n"
                f"_{i - 1}/{total} sent_",
                parse_mode="markdown",
                buttons=[[Button.inline("❌ Cancel Send", data=f"stop:{id(flag)}")]],
            )
        except Exception:
            pass

        cap = file_caption(name, sz, i, total, source_url)

        try:
            if is_video(name):
                await client.send_file(
                    target, str(fp),
                    caption=cap, parse_mode="markdown",
                    supports_streaming=True,
                )
            elif is_image(name):
                await client.send_file(
                    target, str(fp),
                    caption=cap, parse_mode="markdown",
                )
            elif is_audio(name):
                await client.send_file(
                    target, str(fp),
                    caption=cap, parse_mode="markdown",
                    voice_note=False,
                )
            else:
                await client.send_file(
                    target, str(fp),
                    caption=cap, parse_mode="markdown",
                    force_document=True,
                )
            sent += 1
        except Exception as e:
            skipped.append(f"`{name}`: {str(e)[:80]}")

    return sent, skipped

# ═══════════════════════════════════════════════════════════════════════
#  FULL PIPELINE — ARCHIVE FILE
# ═══════════════════════════════════════════════════════════════════════
async def pipeline_archive(event, zip_path: Path, fname: str, dest_channel=None):
    chat_id = event.chat_id
    flag = {"stop": False}
    flag_key = str(id(flag))
    _flag_map[flag_key] = flag

    jid = f"{chat_id}_{int(time.time() * 1000)}"
    out_dir = WORK_DIR / jid
    out_dir.mkdir(parents=True, exist_ok=True)

    cancel_btn = [[Button.inline("❌ Cancel", data=f"stop:{flag_key}")]]

    status = await event.reply(
        f"⚡ *Starting extraction*\n\n📦 `{fname}`",
        parse_mode="markdown",
        buttons=cancel_btn,
    )

    async def status_cb(text: str):
        try:
            await status.edit(text, parse_mode="markdown", buttons=cancel_btn)
        except Exception:
            pass

    async with _sem_extract:
        files = await extract_archive(zip_path, out_dir, flag, status_cb)

    if files is None:
        await status.edit("🚫 *Cancelled.*", parse_mode="markdown")
        _flag_map.pop(flag_key, None)
        await cleanup(str(zip_path), str(out_dir))
        asyncio.create_task(auto_del(status, 30))
        return

    if not files:
        await status.edit(
            "❌ *No files extracted.* Check the archive format.",
            parse_mode="markdown",
        )
        _flag_map.pop(flag_key, None)
        await cleanup(str(zip_path), str(out_dir))
        asyncio.create_task(auto_del(status, 60))
        return

    total_sz = sum(f.stat().st_size for f in files if f.exists())
    archives_in = [f for f in files if is_archive(f.name)]
    videos_in = [f for f in files if is_video(f.name)]
    images_in = [f for f in files if is_image(f.name)]

    await status.edit(
        f"✅ *Extracted!* `{fname}`\n\n"
        f"📦 `{len(files)}` file(s) — `{human(total_sz)}`\n"
        f"🎬 Videos: `{len(videos_in)}`\n"
        f"🖼️ Images: `{len(images_in)}`\n"
        f"📁 Other: `{len(files) - len(videos_in) - len(images_in)}`\n\n"
        f"📤 Sending to {'channel' if dest_channel else 'you'}…",
        parse_mode="markdown",
        buttons=[[Button.inline("❌ Cancel Send", data=f"stop:{flag_key}")]],
    )

    sent, skipped = await send_files(
        chat_id, files, flag, status, dest_channel
    )

    lines = [f"🎉 *Done!* `{fname}`\n",
             f"✅ Sent: `{sent}/{len(files)}`"]
    if skipped:
        lines.append(f"⚠️ Failed: `{len(skipped)}`")
    if archives_in:
        lines.append(
            f"\n📦 Found nested archives: `{len(archives_in)}`\n"
            f"_Send them separately to extract._"
        )
    lines.append(f"\n{bot_footer()}")

    await status.edit("\n".join(lines), parse_mode="markdown")
    _flag_map.pop(flag_key, None)
    await cleanup(str(zip_path), str(out_dir))
    asyncio.create_task(auto_del(status, AUTO_DEL_SEC))

# ═══════════════════════════════════════════════════════════════════════
#  FULL PIPELINE — LINK
# ═══════════════════════════════════════════════════════════════════════
async def pipeline_link(event, url: str, dest_channel=None):
    chat_id = event.chat_id
    flag = {"stop": False}
    flag_key = str(id(flag))
    _flag_map[flag_key] = flag

    jid = f"{chat_id}_{int(time.time() * 1000)}"
    out_dir = WORK_DIR / jid
    out_dir.mkdir(parents=True, exist_ok=True)

    cancel_btn = [[Button.inline("❌ Cancel", data=f"stop:{flag_key}")]]

    status = await event.reply(
        f"🔗 *Link received!*\n\n`{url[:80]}`\n\n⏳ Analyzing…",
        parse_mode="markdown",
        buttons=cancel_btn,
    )

    async def status_cb(text: str):
        try:
            await status.edit(text, parse_mode="markdown", buttons=cancel_btn)
        except Exception:
            pass

    async with _sem_link:
        files = await download_link(url, out_dir, flag, status_cb)

    if files is None:
        await status.edit("🚫 *Cancelled.*", parse_mode="markdown")
        _flag_map.pop(flag_key, None)
        await cleanup(str(out_dir))
        asyncio.create_task(auto_del(status, 30))
        return

    if not files:
        await status.edit(
            "❌ *Could not download from this link.*\n\n"
            "_Make sure the link is public and accessible._",
            parse_mode="markdown",
        )
        _flag_map.pop(flag_key, None)
        await cleanup(str(out_dir))
        asyncio.create_task(auto_del(status, 60))
        return

    # Check if downloaded file is an archive → auto-extract it too
    archives = [f for f in files if is_archive(f.name)]
    non_archives = [f for f in files if not is_archive(f.name)]

    all_send_files: list[Path] = list(non_archives)

    # Auto-extract any archives found in the download
    for arch in archives:
        arch_out = out_dir / f"extracted_{arch.stem}"
        arch_out.mkdir(exist_ok=True)
        arch_flag = {"stop": False}

        async def arch_status_cb(text: str, _f=flag_key):
            try:
                await status.edit(text, parse_mode="markdown", buttons=cancel_btn)
            except Exception:
                pass

        extracted = await extract_archive(arch, arch_out, arch_flag, arch_status_cb)
        if extracted:
            all_send_files.extend(extracted)

    total_sz = sum(f.stat().st_size for f in all_send_files if f.exists())

    await status.edit(
        f"✅ *Downloaded!*\n\n"
        f"📦 `{len(all_send_files)}` file(s) — `{human(total_sz)}`\n\n"
        f"📤 Sending to {'channel' if dest_channel else 'you'}…",
        parse_mode="markdown",
        buttons=[[Button.inline("❌ Cancel Send", data=f"stop:{flag_key}")]],
    )

    sent, skipped = await send_files(
        chat_id, all_send_files, flag, status, dest_channel, source_url=url
    )

    lines = [
        f"🎉 *Done!*\n",
        f"🔗 `{url[:60]}`\n",
        f"✅ Sent: `{sent}/{len(all_send_files)}`",
    ]
    if skipped:
        lines.append(f"⚠️ Failed: `{len(skipped)}`")
    lines.append(f"\n{bot_footer()}")

    await status.edit("\n".join(lines), parse_mode="markdown")
    _flag_map.pop(flag_key, None)
    await cleanup(str(out_dir))
    asyncio.create_task(auto_del(status, AUTO_DEL_SEC))

# ═══════════════════════════════════════════════════════════════════════
#  FORWARD HANDLER
# ═══════════════════════════════════════════════════════════════════════
async def handle_forward(event, dest_channel=None):
    msg = event.message
    chat_id = event.chat_id
    target = dest_channel or chat_id
    caption = strip_promo(msg.message or "")
    clean_cap = (
        caption + f"\n\n📢 {CHANNEL_LINK}" if caption else f"📢 {CHANNEL_LINK}"
    )
    try:
        if msg.media:
            await client.send_file(
                target, msg.media,
                caption=clean_cap, parse_mode="markdown",
            )
        elif msg.message:
            await client.send_message(target, clean_cap, parse_mode="markdown")

        confirm = await event.reply(
            "✅ *Re-posted clean!* Original source removed.",
            parse_mode="markdown",
        )
        try:
            await msg.delete()
        except Exception:
            pass
        asyncio.create_task(auto_del(confirm, 20))
    except Exception as e:
        await event.reply(f"❌ Failed: `{e}`", parse_mode="markdown")

# ═══════════════════════════════════════════════════════════════════════
#  COMMANDS
# ═══════════════════════════════════════════════════════════════════════

@client.on(events.NewMessage(pattern="/start"))
async def cmd_start(event):
    me = await client.get_me()
    uid = event.sender_id
    if uid not in _policy_accepted:
        await event.reply(
            POLICY_TEXT,
            parse_mode="markdown",
            buttons=[[Button.inline("✅ I Accept — Start Bot", data=f"policy:accept:{uid}")]],
        )
        return

    await event.reply(
        f"👋 *Welcome to Ultra Unzipper Bot!*\n\n"
        f"📦 *Archive formats:*\n"
        f"`.zip` `.7z` `.rar` `.tar` `.gz` `.bz2` `.xz`\n\n"
        f"🔗 *Link downloader supports:*\n"
        f"{SUPPORTED_SITES}\n\n"
        f"⚡ *Features:*\n"
        f"• Auto-extract from any link\n"
        f"• Live progress bar + cancel\n"
        f"• Send to your channel (admin)\n"
        f"• Forward cleaner (strip source)\n"
        f"• 1000+ users simultaneously\n"
        f"• 24/7 uptime (UptimeRobot)\n\n"
        f"*Commands:*\n"
        f"/start — Main menu\n"
        f"/help — Full guide\n"
        f"/setchannel @ch — Set destination channel\n"
        f"/clearchannel — Send here instead\n"
        f"/status — Active jobs\n"
        f"/links — Supported link sites\n"
        f"/admin — Admin panel\n\n"
        f"👤 Admin: @{ADMIN_USERNAME}\n"
        f"📢 Channel: {CHANNEL_LINK}",
        parse_mode="markdown",
        buttons=[
            [Button.inline("📖 Help", data="help"), Button.inline("📊 Status", data="statusbtn")],
            [Button.inline("📢 Join Channel", url=CHANNEL_LINK)],
        ],
    )

@client.on(events.NewMessage(pattern="/help"))
async def cmd_help(event):
    if not await check_policy(event):
        return
    await event.reply(
        "📖 *Full Guide*\n\n"
        "*📦 Unzip archives:*\n"
        "Just send any `.zip` `.7z` `.rar` `.tar` etc. file\n\n"
        "*🔗 Download from links:*\n"
        "Just paste any URL — video/image/archive link\n"
        "• YouTube, Instagram, TikTok, Twitter/X, etc.\n"
        "• Direct `.mp4`, `.zip`, `.pdf` links\n"
        "• 1000+ sites via yt-dlp\n\n"
        "*📢 Channel mode:*\n"
        "1. Make bot admin in your channel\n"
        "2. `/setchannel @yourchannel`\n"
        "3. All files go to that channel\n\n"
        "*🔄 Forward cleaner:*\n"
        "Forward any message → bot asks where to repost (removes source)\n\n"
        "*❌ Cancel:*\n"
        "Press cancel button at any time to stop\n\n"
        f"👤 Admin: @{ADMIN_USERNAME}",
        parse_mode="markdown",
    )

@client.on(events.NewMessage(pattern="/links"))
async def cmd_links(event):
    if not await check_policy(event):
        return
    await event.reply(
        "🔗 *Supported Link Types*\n\n"
        "📹 *Video platforms:*\n"
        "YouTube • Instagram Reels/Posts • TikTok\n"
        "Twitter/X • Facebook • Vimeo • Twitch\n"
        "Dailymotion • Reddit • Pinterest\n\n"
        "🎵 *Audio:*\n"
        "SoundCloud • Bandcamp • Mixcloud\n\n"
        "📦 *Direct files:*\n"
        "`.zip` `.rar` `.7z` `.tar` `.mp4` `.pdf`\n"
        "`.jpg` `.png` `.gif` `.mp3` and any direct URL\n\n"
        "✅ _1000+ sites supported via yt-dlp_\n\n"
        "*Just paste the link — bot handles the rest!*",
        parse_mode="markdown",
    )

@client.on(events.NewMessage(pattern=r"/setchannel\s+(@\S+|[-\d]+)"))
async def cmd_setchannel(event):
    if not await check_policy(event):
        return
    channel = event.pattern_match.group(1)
    chat_id = event.chat_id

    wait = await event.reply(
        f"🔍 Checking if bot is admin in `{channel}`…",
        parse_mode="markdown",
    )
    is_admin = await bot_is_admin_in(channel)
    if not is_admin:
        await wait.edit(
            f"❌ *Bot is not admin in `{channel}`*\n\n"
            f"*Steps to fix:*\n"
            f"1. Open your channel settings\n"
            f"2. Tap *Administrators → Add Admin*\n"
            f"3. Add this bot with *Post Messages* permission\n"
            f"4. Run `/setchannel {channel}` again",
            parse_mode="markdown",
        )
        return

    _dest_channels[chat_id] = channel
    await wait.edit(
        f"✅ *Channel set to `{channel}`!*\n\n"
        f"All extracted/downloaded files will be sent there.\n"
        f"Use /clearchannel to disable.",
        parse_mode="markdown",
    )

@client.on(events.NewMessage(pattern="/clearchannel"))
async def cmd_clearchannel(event):
    _dest_channels.pop(event.chat_id, None)
    await event.reply("✅ Channel cleared. Files will come here.", parse_mode="markdown")

@client.on(events.NewMessage(pattern="/status"))
async def cmd_status(event):
    active = len(_flag_map)
    accepted = len(_policy_accepted)
    await event.reply(
        f"📊 *Bot Status*\n\n"
        f"⚡ Active jobs: `{active}`\n"
        f"🔧 Max parallel: `{MAX_PARALLEL}`\n"
        f"👥 Users accepted policy: `{accepted}`\n"
        f"🌐 Keep-alive: port `{KEEP_ALIVE_PORT}`",
        parse_mode="markdown",
    )

@client.on(events.NewMessage(pattern="/admin"))
async def cmd_admin(event):
    if event.sender_id != (await client.get_me()).id:
        try:
            sender = await event.get_sender()
            if not sender or getattr(sender, "username", "") != ADMIN_USERNAME:
                await event.reply("❌ Admin only command.", parse_mode="markdown")
                return
        except Exception:
            return

    active = len(_flag_map)
    channels = len(_dest_channels)
    users = len(_policy_accepted)
    await event.reply(
        f"🛠️ *Admin Panel*\n\n"
        f"Active jobs: `{active}`\n"
        f"Channels configured: `{channels}`\n"
        f"Policy accepted users: `{users}`\n"
        f"Work dir: `{WORK_DIR}`\n"
        f"Keep-alive port: `{KEEP_ALIVE_PORT}`\n\n"
        f"_Bot is running smoothly._",
        parse_mode="markdown",
    )

# ── Inline button callbacks ──────────────────────────────────────────────
@client.on(events.CallbackQuery(data=b"help"))
async def cb_help(event):
    await event.answer()
    await event.reply(
        "📖 Send any archive file or paste a URL!\n"
        "Use /help for full guide.",
        parse_mode="markdown",
    )

@client.on(events.CallbackQuery(data=b"statusbtn"))
async def cb_status_btn(event):
    await event.answer(
        f"Active jobs: {len(_flag_map)} | Max: {MAX_PARALLEL}",
        alert=False,
    )

@client.on(events.CallbackQuery(pattern=b"stop:"))
async def cb_cancel(event):
    flag_key = event.data.decode().split(":", 1)[1]
    flag = _flag_map.get(flag_key)
    if not flag:
        await event.answer("⚠️ Job already finished.", alert=False)
        return
    flag["stop"] = True
    await event.answer("🚫 Cancel signal sent!", alert=False)
    try:
        await event.edit("🚫 *Cancelling…* please wait.", parse_mode="markdown")
    except Exception:
        pass

@client.on(events.CallbackQuery(pattern=rb"fwd:(here|ch):"))
async def cb_fwd(event):
    data = event.data.decode()
    parts = data.split(":", 2)
    mode = parts[1]  # "here" or "ch"
    key = data

    stored = _fwd_store.get(key)
    if not stored:
        await event.answer("⚠️ Expired.", alert=False)
        return

    chat_id = event.chat_id
    ch = _dest_channels.get(chat_id)

    if mode == "ch" and not ch:
        await event.answer("No channel set! Use /setchannel first.", alert=True)
        return

    await event.answer()
    await handle_forward(stored["event"], dest_channel=(ch if mode == "ch" else None))
    _fwd_store.pop(key, None)

# ═══════════════════════════════════════════════════════════════════════
#  MAIN MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage)
async def main_handler(event):
    msg = event.message
    chat_id = event.chat_id

    # Skip commands (handled above)
    if msg.text and msg.text.startswith("/"):
        return

    # Policy gate
    if not await check_policy(event):
        return

    dest_ch = _dest_channels.get(chat_id)

    # ── Forwarded message ──────────────────────────────────────────────
    if msg.forward:
        fwd_key = f"fwd:here:{chat_id}_{int(time.time() * 1000)}"
        _fwd_store[fwd_key] = {"event": event}

        buttons = [[Button.inline("📤 Repost here (clean)", data=fwd_key)]]
        if dest_ch:
            ch_key = f"fwd:ch:{chat_id}_{int(time.time() * 1000)}"
            _fwd_store[ch_key] = {"event": event}
            buttons.append([Button.inline(f"📢 Send to {dest_ch} (clean)", data=ch_key)])

        prompt = await event.reply(
            "🔄 *Forwarded message detected!*\n\n"
            "I'll repost this *without* the original source.\n"
            "Where should I send it?",
            parse_mode="markdown",
            buttons=buttons,
        )
        asyncio.create_task(auto_del(prompt, 60))
        return

    # ── Archive file ───────────────────────────────────────────────────
    if msg.document:
        fname = ""
        for attr in (msg.document.attributes or []):
            if hasattr(attr, "file_name"):
                fname = attr.file_name
                break
        if not fname:
            fname = f"file_{int(time.time())}"

        if is_archive(fname):
            dl_msg = await event.reply(
                f"📥 *Downloading* `{fname}`…\n"
                f"_{human(msg.document.size or 0)}_",
                parse_mode="markdown",
            )
            try:
                dl_path = (
                    WORK_DIR / f"{chat_id}_{int(time.time() * 1000)}{Path(fname).suffix}"
                )
                await event.download_media(file=str(dl_path))
            except Exception as e:
                await dl_msg.edit(f"❌ Download failed: `{e}`", parse_mode="markdown")
                return
            await dl_msg.delete()
            asyncio.create_task(pipeline_archive(event, dl_path, fname, dest_ch))
            return
        else:
            # Non-archive doc — forward it cleanly if dest_ch, else ignore
            await event.reply(
                f"⚠️ `{fname}` is not a supported archive.\n\n"
                f"*Supported:* `.zip` `.7z` `.rar` `.tar` `.gz` `.bz2` `.xz`\n\n"
                f"Or paste a *link* to download from a URL.",
                parse_mode="markdown",
            )
            return

    # ── URL / link in text ─────────────────────────────────────────────
    if msg.text:
        urls = extract_urls(msg.text)
        if urls:
            url = urls[0]  # process first URL
            asyncio.create_task(pipeline_link(event, url, dest_ch))
            return

        # No URL, no archive — prompt user
        await event.reply(
            "🤔 *What should I do?*\n\n"
            "📦 Send an *archive file* to extract it\n"
            "🔗 Paste a *URL/link* to download it\n"
            "📋 Use /help for full guide",
            parse_mode="markdown",
            buttons=[
                [Button.inline("📖 Help", data="help")],
                [Button.inline("📢 Join Channel", url=CHANNEL_LINK)],
            ],
        )

# ═══════════════════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════════════════
async def main():
    _start_keep_alive()
    me = await client.get_me()
    print(f"""
╔══════════════════════════════════════════╗
║   🚀 ULTRA UNZIPPER BOT — ONLINE        ║
╠══════════════════════════════════════════╣
║  Bot   : @{me.username:<30}║
║  Admin : @{ADMIN_USERNAME:<30}║
║  Ch    : {CHANNEL_HANDLE:<31}║
║  Port  : {KEEP_ALIVE_PORT:<31}║
║  Workers: {MAX_PARALLEL} extract | {MAX_LINK_DL} link dl    ║
╚══════════════════════════════════════════╝
🌐 UptimeRobot ping URL: http://YOUR_REPLIT_URL:{KEEP_ALIVE_PORT}/
""")
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())
