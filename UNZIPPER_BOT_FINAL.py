# ═══════════════════════════════════════════════════════════
#  ADVANCED UNZIPPER BOT  |  Admin: @F88UF  |  Ch: @F88UF9844
#  Auto-installs all deps. Single file. Just run: python bot.py
# ═══════════════════════════════════════════════════════════

import subprocess, sys, os

# ── Auto-install all required packages ──────────────────────
_REQUIRED = ["telethon", "cryptography"]
for _pkg in _REQUIRED:
    try:
        __import__(_pkg)
    except ImportError:
        print(f"📦 Installing {_pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", _pkg])

# ── Stdlib ───────────────────────────────────────────────────
import asyncio, zipfile, shutil, tarfile, time, re, logging
from pathlib import Path
from base64 import b64decode, b64encode

# ── Telethon ─────────────────────────────────────────────────
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import (
    ChannelParticipantAdmin, ChannelParticipantCreator,
    MessageMediaDocument, MessageMediaPhoto,
)

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.WARNING)

# ═══════════════════════════════════════════════════════════
#  CREDENTIALS  (base64 obfuscated — change values below)
#  To encode a new value:
#    python3 -c "import base64; print(base64.b64encode(b'YOUR_VALUE').decode())"
# ═══════════════════════════════════════════════════════════
_AI  = int(b64decode("Mjk2NDM0NzQ=").decode())
_AH  = b64decode("NDkxNjMzZjAzNGMxYjUwYjFiYzBmMWU0ZDJiNDI2ZTM=").decode()
_BT  = b64decode("ODcyMzk2NTI5MzpBQUZ4bjBaYXZocHlaMmZWa0RPaFd6dHNpeVA0TGNjaWlKVQ==").decode()

# ═══════════════════════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════════════════════
ADMIN_USERNAME  = "F88UF"
CHANNEL_HANDLE  = "@F88UF9844"
CHANNEL_LINK    = "https://t.me/F88UF9844"
BOT_TAG         = "@F88UF9844"   # shown as "Unzipped by" in files
AUTO_DEL_SEC    = 90             # auto-delete bot status msgs (seconds)
MAX_PARALLEL    = 8              # max simultaneous extractions
WORK_DIR        = Path("/tmp/uzbot")
WORK_DIR.mkdir(parents=True, exist_ok=True)

ARCHIVE_EXTS = {
    ".zip",".7z",".rar",".tar",
    ".gz",".tgz",".bz2",".xz",".tar.gz",".tar.bz2",
}
VIDEO_EXTS = {
    ".mp4",".mkv",".avi",".mov",".wmv",".flv",
    ".webm",".m4v",".mpg",".mpeg",".3gp",
    ".ts",".m2ts",".vob",".rmvb",".divx",
}
IMAGE_EXTS = {".jpg",".jpeg",".png",".gif",".bmp",".webp",".tiff"}

DISCLAIMER = (
    "⚠️ *Disclaimer:* This bot is a utility tool only.\n"
    "The admin/bot is not responsible for any misuse, "
    "illegal content, or 18+ material. "
    "Users are solely responsible for files they process."
)

# ═══════════════════════════════════════════════════════════
#  CLIENT  &  STATE
# ═══════════════════════════════════════════════════════════
client = TelegramClient("uzbot_session", _AI, _AH).start(bot_token=_BT)

# { flag_id_str : flag_dict }
_flag_map: dict[str, dict] = {}
# { chat_id : asyncio.Semaphore } — per-chat concurrency slot
_sem = asyncio.Semaphore(MAX_PARALLEL)

# ═══════════════════════════════════════════════════════════
#  UTILS
# ═══════════════════════════════════════════════════════════
def human(n: float) -> str:
    for u in ("B","KB","MB","GB","TB"):
        if abs(n) < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

def pbar(done: int, total: int, w: int = 20) -> str:
    p = min(done / total, 1.0) if total else 0
    f = int(w * p)
    return f"[{'█'*f}{'░'*(w-f)}] {p*100:.0f}%"

def suffix(path) -> str:
    return Path(str(path)).suffix.lower()

def is_archive(name: str) -> bool:
    n = name.lower()
    if n.endswith(".tar.gz") or n.endswith(".tar.bz2"): return True
    return suffix(name) in ARCHIVE_EXTS

def is_video(name: str) -> bool:
    return suffix(name) in VIDEO_EXTS

def is_image(name: str) -> bool:
    return suffix(name) in IMAGE_EXTS

def strip_promo(text: str) -> str:
    """Remove any @username or t.me links from forwarded text."""
    if not text: return ""
    text = re.sub(r"@\w+", f"@{ADMIN_USERNAME}", text)
    text = re.sub(r"https?://t\.me/\S+", CHANNEL_LINK, text)
    return text.strip()

def file_caption(fname: str, sz: int, idx: int, total: int) -> str:
    return (
        f"📄 `{fname}`\n"
        f"📦 {human(sz)}  •  {idx}/{total}\n\n"
        f"_Unzipped by {BOT_TAG}_"
    )

async def auto_del(msg, delay: int = AUTO_DEL_SEC):
    await asyncio.sleep(delay)
    try: await msg.delete()
    except Exception: pass

async def cleanup(*paths):
    for p in paths:
        try:
            if os.path.isfile(p):  os.remove(p)
            elif os.path.isdir(p): shutil.rmtree(p)
        except Exception: pass

# ═══════════════════════════════════════════════════════════
#  CHANNEL ADMIN CHECK
# ═══════════════════════════════════════════════════════════
async def bot_is_admin_in(channel) -> bool:
    try:
        me   = await client.get_me()
        part = await client(GetParticipantRequest(channel, me.id))
        return isinstance(part.participant,
                          (ChannelParticipantAdmin, ChannelParticipantCreator))
    except Exception:
        return False

# ═══════════════════════════════════════════════════════════
#  EXTRACTION ENGINE
# ═══════════════════════════════════════════════════════════
async def extract_archive(
    zip_path: Path,
    out_dir: Path,
    flag: dict,
    status_cb,          # async callable(text, pct)
) -> list[Path] | None:
    """Extract any supported archive. Returns list of files or None if cancelled."""
    ext = zip_path.suffix.lower()
    name = zip_path.name.lower()
    out_files: list[Path] = []

    async def upd(text: str):
        try: await status_cb(text)
        except Exception: pass

    # ── ZIP ─────────────────────────────────────────────────
    if ext == ".zip":
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                members  = zf.infolist()
                total_sz = sum(m.file_size for m in members) or 1
                done_sz  = 0
                t_last   = 0
                for m in members:
                    if flag["stop"]: return None
                    zf.extract(m, out_dir)
                    done_sz += m.file_size
                    p = out_dir / m.filename
                    if p.is_file(): out_files.append(p)
                    if time.time() - t_last > 1.8:
                        await upd(
                            f"⚡ Extracting ZIP\n\n"
                            f"{pbar(done_sz, total_sz)}\n"
                            f"`{human(done_sz)}` / `{human(total_sz)}`\n"
                            f"📄 `{Path(m.filename).name[:40]}`"
                        )
                        t_last = time.time()
        except zipfile.BadZipFile:
            await upd("❌ Corrupted / invalid ZIP file.")
            return []

    # ── TAR family ──────────────────────────────────────────
    elif ext in (".tar",".gz",".tgz",".bz2",".xz") or name.endswith((".tar.gz",".tar.bz2")):
        try:
            with tarfile.open(zip_path, "r:*") as tf:
                members  = tf.getmembers()
                total_sz = sum(m.size for m in members) or 1
                done_sz  = 0
                t_last   = 0
                for m in members:
                    if flag["stop"]: return None
                    tf.extract(m, out_dir, set_attrs=False)
                    done_sz += m.size
                    p = out_dir / m.name
                    if p.is_file(): out_files.append(p)
                    if time.time() - t_last > 1.8:
                        await upd(
                            f"⚡ Extracting TAR\n\n"
                            f"{pbar(done_sz, total_sz)}\n"
                            f"`{human(done_sz)}` / `{human(total_sz)}`"
                        )
                        t_last = time.time()
        except Exception as e:
            await upd(f"❌ TAR error: {e}")
            return []

    # ── 7Z / RAR ────────────────────────────────────────────
    elif ext in (".7z", ".rar"):
        # check 7z installed
        r = subprocess.run(["which","7z"], capture_output=True)
        if r.returncode != 0:
            # try auto-install
            await upd("⏳ Installing 7zip...")
            subprocess.run(
                ["apt-get","install","-y","p7zip-full"],
                capture_output=True
            )
        await upd(f"⚡ Extracting {ext.upper()}...\n\n⏳ Please wait…")
        proc = await asyncio.create_subprocess_exec(
            "7z","x", str(zip_path), f"-o{out_dir}", "-y",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        while proc.returncode is None:
            if flag["stop"]:
                proc.kill()
                return None
            await asyncio.sleep(0.8)
            await upd(f"⚡ Extracting {ext.upper()}...\n\n⏳ Running…")
        await proc.wait()
        if proc.returncode != 0:
            err = (await proc.stderr.read()).decode(errors="ignore")[:200]
            await upd(f"❌ 7z error:\n`{err}`")
            return []
        # collect files
        for root, _, fs in os.walk(out_dir):
            for f in fs:
                out_files.append(Path(root) / f)

    else:
        await upd(f"❌ Unsupported format: `{ext}`")
        return []

    return out_files

# ═══════════════════════════════════════════════════════════
#  SEND FILES
# ═══════════════════════════════════════════════════════════
async def send_files(
    chat_id,
    files: list[Path],
    flag: dict,
    status_msg,
    dest_channel=None,  # if set, send there instead
):
    total   = len(files)
    sent    = 0
    skipped = []
    target  = dest_channel or chat_id

    for i, fp in enumerate(files, 1):
        if flag["stop"]:
            break
        if not fp.exists():
            continue

        sz   = fp.stat().st_size
        name = fp.name

        # Update status
        try:
            await status_msg.edit(
                f"📤 Sending `{name}`\n"
                f"{pbar(i-1, total)}\n"
                f"{i-1}/{total} sent",
                parse_mode="markdown",
                buttons=[[Button.inline("❌ Cancel Send", data=f"stop:{id(flag)}")]],
            )
        except Exception:
            pass

        try:
            cap = file_caption(name, sz, i, total)
            if is_video(name):
                await client.send_file(
                    target, str(fp),
                    caption=cap,
                    parse_mode="markdown",
                    supports_streaming=True,
                    attributes=[],
                )
            elif is_image(name):
                await client.send_file(
                    target, str(fp),
                    caption=cap,
                    parse_mode="markdown",
                )
            else:
                await client.send_file(
                    target, str(fp),
                    caption=cap,
                    parse_mode="markdown",
                    force_document=True,
                )
            sent += 1
        except Exception as e:
            skipped.append(f"`{name}`: {e}")

    return sent, skipped

# ═══════════════════════════════════════════════════════════
#  FULL PIPELINE
# ═══════════════════════════════════════════════════════════
async def full_pipeline(event, zip_path: Path, fname: str, dest_channel=None):
    chat_id  = event.chat_id
    flag     = {"stop": False}
    flag_key = str(id(flag))
    _flag_map[flag_key] = flag

    jid     = f"{chat_id}_{int(time.time()*1000)}"
    out_dir = WORK_DIR / jid
    out_dir.mkdir(parents=True, exist_ok=True)

    status = await event.reply(
        f"📥 *Downloaded!*\n\n"
        f"⚡ Starting extraction of `{fname}`…",
        parse_mode="markdown",
        buttons=[[Button.inline("❌ Cancel", data=f"stop:{flag_key}")]],
    )

    async def status_cb(text: str):
        try:
            await status.edit(
                text,
                parse_mode="markdown",
                buttons=[[Button.inline("❌ Cancel", data=f"stop:{flag_key}")]],
            )
        except Exception:
            pass

    # Extract
    async with _sem:
        files = await extract_archive(zip_path, out_dir, flag, status_cb)

    if files is None:
        # Cancelled
        await status.edit("🚫 *Cancelled.*", parse_mode="markdown")
        _flag_map.pop(flag_key, None)
        await cleanup(str(zip_path), str(out_dir))
        asyncio.create_task(auto_del(status, 30))
        return

    if not files:
        await status.edit("❌ *No files extracted.* Check the archive.", parse_mode="markdown")
        _flag_map.pop(flag_key, None)
        await cleanup(str(zip_path), str(out_dir))
        asyncio.create_task(auto_del(status, 60))
        return

    total_sz = sum(f.stat().st_size for f in files if f.exists())

    # Categorize
    archives_inside = [f for f in files if is_archive(f.name)]
    videos_inside   = [f for f in files if is_video(f.name)]
    normal_files    = [f for f in files if not is_archive(f.name)]

    await status.edit(
        f"✅ *Extracted!* `{fname}`\n\n"
        f"📦 `{len(files)}` file(s) — `{human(total_sz)}`\n"
        f"🎬 Videos: `{len(videos_inside)}`\n"
        f"📁 Other files: `{len(normal_files)}`\n\n"
        f"📤 Sending to {'channel' if dest_channel else 'you'}…",
        parse_mode="markdown",
        buttons=[[Button.inline("❌ Cancel Send", data=f"stop:{flag_key}")]],
    )

    sent, skipped = await send_files(
        chat_id, normal_files, flag, status, dest_channel
    )

    # Result message
    result_lines = [f"🎉 *Done!* `{fname}`\n"]
    result_lines.append(f"✅ Sent: `{sent}/{len(files)}` files")
    if skipped:
        result_lines.append(f"⚠️ Failed: `{len(skipped)}`")
    if archives_inside:
        result_lines.append(
            f"\n📦 Found nested archives: `{len(archives_inside)}`\n"
            f"_Reply /unzip to extract them too._"
        )
    result_lines.append(f"\n{bot_footer()}")

    await status.edit(
        "\n".join(result_lines),
        parse_mode="markdown",
    )

    _flag_map.pop(flag_key, None)
    await cleanup(str(zip_path), str(out_dir))
    asyncio.create_task(auto_del(status, AUTO_DEL_SEC))

# ═══════════════════════════════════════════════════════════
#  FORWARD HANDLER  (remove original source, re-post clean)
# ═══════════════════════════════════════════════════════════
async def handle_forward(event, dest_channel=None):
    """Re-post forwarded media/text without original source info."""
    msg     = event.message
    chat_id = event.chat_id
    target  = dest_channel or chat_id
    caption = strip_promo(msg.message or "")
    clean_cap = caption + f"\n\n📢 {CHANNEL_LINK}" if caption else f"📢 {CHANNEL_LINK}"

    try:
        if msg.media:
            await client.send_file(
                target,
                msg.media,
                caption=clean_cap,
                parse_mode="markdown",
            )
        elif msg.message:
            await client.send_message(target, clean_cap, parse_mode="markdown")

        confirm = await event.reply(
            "✅ Re-posted without original source!\n_Original message will be deleted._",
            parse_mode="markdown",
        )
        try: await msg.delete()
        except Exception: pass
        asyncio.create_task(auto_del(confirm, 20))
    except Exception as e:
        await event.reply(f"❌ Failed to re-post: `{e}`", parse_mode="markdown")

# ═══════════════════════════════════════════════════════════
#  EVENT HANDLERS
# ═══════════════════════════════════════════════════════════

@client.on(events.NewMessage(pattern="/start"))
async def cmd_start(event):
    me = await client.get_me()
    await event.reply(
        f"👋 *Welcome to Advanced Unzipper Bot!*\n\n"
        f"📦 *Supported formats:*\n"
        f"`.zip` `.7z` `.rar` `.tar` `.gz` `.bz2` `.xz`\n\n"
        f"⚡ *Features:*\n"
        f"• Fast multi-threaded extraction\n"
        f"• Live progress bar\n"
        f"• Cancel anytime\n"
        f"• Send to channel or here\n"
        f"• Forward cleaner (removes source)\n"
        f"• Multiple files simultaneously\n\n"
        f"*Commands:*\n"
        f"/start — this message\n"
        f"/setchannel — set destination channel\n"
        f"/clearchannel — send files here instead\n"
        f"/status — active jobs\n"
        f"/help — full guide\n\n"
        f"{DISCLAIMER}\n\n"
        f"👤 Admin: @{ADMIN_USERNAME}\n"
        f"📢 Channel: {CHANNEL_LINK}",
        parse_mode="markdown",
    )

@client.on(events.NewMessage(pattern="/help"))
async def cmd_help(event):
    await event.reply(
        "📖 *How to use:*\n\n"
        "1️⃣ Send any archive file directly\n"
        "2️⃣ Bot extracts and sends files back\n"
        "3️⃣ Use ❌ Cancel button to stop anytime\n\n"
        "*Channel mode:*\n"
        "• `/setchannel @yourchannel` — extracted files go to channel\n"
        "• Make sure bot is admin in that channel first!\n\n"
        "*Forward cleaner:*\n"
        "• Forward any message to bot\n"
        "• Bot asks where to re-post it (clean, no source)\n\n"
        f"👤 Admin: @{ADMIN_USERNAME}",
        parse_mode="markdown",
    )

@client.on(events.NewMessage(pattern=r"/setchannel\s+(@\S+|[-\d]+)"))
async def cmd_setchannel(event):
    channel = event.pattern_match.group(1)
    chat_id = event.chat_id

    wait = await event.reply(f"🔍 Checking if bot is admin in `{channel}`…", parse_mode="markdown")

    is_admin = await bot_is_admin_in(channel)
    if not is_admin:
        await wait.edit(
            f"❌ *Bot is not admin in `{channel}`*\n\n"
            f"*How to fix:*\n"
            f"1. Open your channel\n"
            f"2. Go to *Administrators*\n"
            f"3. Add this bot as admin\n"
            f"4. Give *Post Messages* permission\n"
            f"5. Then run `/setchannel {channel}` again",
            parse_mode="markdown",
        )
        return

    # Store per-chat channel preference (in-memory, resets on restart)
    if not hasattr(client, "_dest_channels"):
        client._dest_channels = {}
    client._dest_channels[chat_id] = channel

    await wait.edit(
        f"✅ *Channel set!*\n\n"
        f"Extracted files will be sent to `{channel}`\n\n"
        f"Use /clearchannel to send here instead.",
        parse_mode="markdown",
    )

@client.on(events.NewMessage(pattern="/clearchannel"))
async def cmd_clearchannel(event):
    chat_id = event.chat_id
    if hasattr(client, "_dest_channels"):
        client._dest_channels.pop(chat_id, None)
    await event.reply("✅ Channel cleared. Files will be sent here.", parse_mode="markdown")

@client.on(events.NewMessage(pattern="/status"))
async def cmd_status(event):
    active = len(_flag_map)
    await event.reply(
        f"📊 *Bot Status*\n\n"
        f"⚡ Active jobs: `{active}`\n"
        f"🔧 Max parallel: `{MAX_PARALLEL}`",
        parse_mode="markdown",
    )

@client.on(events.CallbackQuery(pattern=b"stop:"))
async def cb_cancel(event):
    flag_key = event.data.decode().split(":", 1)[1]
    flag     = _flag_map.get(flag_key)

    if not flag:
        await event.answer("⚠️ Job already finished.", alert=False)
        return

    flag["stop"] = True
    await event.answer("🚫 Cancel signal sent!", alert=False)
    try:
        await event.edit("🚫 *Cancelling…* please wait.", parse_mode="markdown")
    except Exception:
        pass

@client.on(events.CallbackQuery(pattern=b"fwd:here"))
async def cb_fwd_here(event):
    # Retrieve stored forward event
    key = event.data.decode()
    stored = getattr(client, "_fwd_store", {}).get(key)
    if not stored:
        await event.answer("Expired.", alert=False)
        return
    await event.answer()
    await handle_forward(stored["event"], dest_channel=None)

@client.on(events.CallbackQuery(pattern=b"fwd:ch"))
async def cb_fwd_ch(event):
    key     = event.data.decode()
    stored  = getattr(client, "_fwd_store", {}).get(key)
    chat_id = event.chat_id
    ch      = getattr(client, "_dest_channels", {}).get(chat_id)

    if not stored:
        await event.answer("Expired.", alert=False)
        return
    if not ch:
        await event.answer("No channel set! Use /setchannel first.", alert=True)
        return

    await event.answer()
    await handle_forward(stored["event"], dest_channel=ch)

@client.on(events.NewMessage)
async def main_handler(event):
    msg     = event.message
    chat_id = event.chat_id

    # ── Forwarded message ───────────────────────────────────
    if msg.forward:
        fwd_key = f"fwd:{chat_id}_{int(time.time()*1000)}"
        if not hasattr(client, "_fwd_store"):
            client._fwd_store = {}
        client._fwd_store[fwd_key] = {"event": event}

        ch = getattr(client, "_dest_channels", {}).get(chat_id)
        buttons = [[Button.inline("📤 Re-post here (clean)", data=f"fwd:here")]]
        if ch:
            buttons.append([Button.inline(f"📢 Send to {ch} (clean)", data=f"fwd:ch")])

        prompt = await event.reply(
            "🔄 *Forwarded message detected!*\n\n"
            "I can re-post this *without* the original source/username.\n"
            "Where should I send it?",
            parse_mode="markdown",
            buttons=buttons,
        )
        asyncio.create_task(auto_del(prompt, 60))
        return

    # ── Archive file ────────────────────────────────────────
    if msg.document:
        fname = ""
        if msg.document.attributes:
            for attr in msg.document.attributes:
                if hasattr(attr, "file_name"):
                    fname = attr.file_name
                    break
        if not fname:
            fname = f"file_{int(time.time())}"

        if not is_archive(fname):
            await event.reply(
                f"⚠️ `{fname}` is not a supported archive.\n\n"
                f"Supported: `.zip` `.7z` `.rar` `.tar` `.gz` `.bz2` `.xz`",
                parse_mode="markdown",
            )
            return

        dl_msg = await event.reply(
            f"📥 *Downloading* `{fname}`…\n"
            f"_{human(msg.document.size or 0)}_",
            parse_mode="markdown",
        )

        try:
            dl_path = WORK_DIR / f"{chat_id}_{int(time.time()*1000)}{Path(fname).suffix}"
            await event.download_media(file=str(dl_path))
        except Exception as e:
            await dl_msg.edit(f"❌ Download failed: `{e}`", parse_mode="markdown")
            return

        await dl_msg.delete()

        dest_ch = getattr(client, "_dest_channels", {}).get(chat_id)
        asyncio.create_task(
            full_pipeline(event, dl_path, fname, dest_channel=dest_ch)
        )
        return

    # ── Text commands catch-all ─────────────────────────────
    if msg.text and msg.text.startswith("/"):
        pass  # handled by specific handlers above

# ═══════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════
async def main():
    me = await client.get_me()
    print(f"""
╔══════════════════════════════════════╗
║   ⚡ ADVANCED UNZIPPER BOT RUNNING  ║
╠══════════════════════════════════════╣
║  Bot  : @{me.username:<28}║
║  Admin: @{ADMIN_USERNAME:<28}║
║  Ch   : {CHANNEL_HANDLE:<29}║
╚══════════════════════════════════════╝
""")
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())
