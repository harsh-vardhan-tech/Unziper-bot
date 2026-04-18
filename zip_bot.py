import os
import asyncio
import zipfile
import shutil
import subprocess
from telethon import TelegramClient, events, Button

api_id = 29643474
api_hash = "491633f034c1b50b1bc0f1e4d2b426e3"
BOT_TOKEN = "8762635107:AAGsSYcGN4zzbwgXiKzW7dLoLJYqTz7XnEc"

client = TelegramClient("session", api_id, api_hash).start(
    bot_token=BOT_TOKEN
)

active_jobs = {}


def human(n):
    for unit in ["B","KB","MB","GB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


async def cleanup(file_path, folder):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(folder):
            shutil.rmtree(folder)
    except:
        pass


async def send_live(chat_id, files, cancel_flag):

    total = len(files)

    for i, f in enumerate(files, 1):

        if cancel_flag["stop"]:
            return

        await client.send_file(
            chat_id,
            f,
            caption=f"📤 Sending {i}/{total}"
        )


async def extract(chat_id, file_path, msg, cancel_flag):

    folder = f"out_{chat_id}"
    os.makedirs(folder, exist_ok=True)

    try:

        await msg.edit("📦 Extracting... 0%")

        if file_path.endswith(".zip"):

            with zipfile.ZipFile(file_path) as z:

                members = z.infolist()
                total = len(members)

                extracted = []

                for i, m in enumerate(members, 1):

                    if cancel_flag["stop"]:
                        return

                    z.extract(m, folder)
                    extracted.append(os.path.join(folder, m.filename))

                    percent = int(i * 100 / total)

                    await msg.edit(
                        f"📦 Extracting... {percent}%"
                    )

                    if os.path.isfile(extracted[-1]):
                        await client.send_file(
                            chat_id,
                            extracted[-1]
                        )

        else:

            subprocess.run(
                ["7z", "x", file_path, f"-o{folder}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            files = []

            for root, _, fs in os.walk(folder):
                for f in fs:
                    files.append(os.path.join(root, f))

            await send_live(chat_id, files, cancel_flag)

        await msg.edit("✅ Extraction completed")

    except:

        await msg.edit("❌ Extraction failed")

    await cleanup(file_path, folder)


@client.on(events.CallbackQuery)
async def cancel(event):

    if event.data == b"stop":

        chat = event.chat_id

        if chat in active_jobs:
            active_jobs[chat]["stop"] = True

            await event.edit("⛔ Extraction cancelled")


@client.on(events.NewMessage)
async def handler(event):

    if not event.document:
        return

    chat = event.chat_id

    cancel_flag = {"stop": False}
    active_jobs[chat] = cancel_flag

    msg = await event.reply(
        "📥 Downloading...",
        buttons=[[Button.inline("⛔ Stop", b"stop")]]
    )

    file_path = await event.download_media()

    await msg.edit("⚡ Download complete. Starting extraction...")

    asyncio.create_task(
        extract(chat, file_path, msg, cancel_flag)
    )


print("🚀 Advanced Unzip Bot Running...")
client.run_until_disconnected()