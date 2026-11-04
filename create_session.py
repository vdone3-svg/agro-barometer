"""
Одноразовий скрипт для створення Telegram StringSession.
Запускай локально, отриманий рядок вставляй у GitHub Secret TELEGRAM_SESSION.
"""
import asyncio, base64
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID   = input("Введи API_ID (число з my.telegram.org): ").strip()
API_HASH = input("Введи API_HASH (рядок з my.telegram.org): ").strip()

async def create():
    async with TelegramClient(StringSession(), int(API_ID), API_HASH) as client:
        session_str = client.session.save()
        b64 = base64.b64encode(session_str.encode()).decode()
        print("\n" + "="*60)
        print("✅ Сесія створена!")
        print("\nTELEGRAM_SESSION (вставляй у GitHub Secret):")
        print(session_str)
        print("\nTELEGRAM_SESSION_B64 (якщо потрібен base64):")
        print(b64)
        print("="*60)

asyncio.run(create())
