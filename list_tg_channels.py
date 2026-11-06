"""
Запускати ЛОКАЛЬНО на вашому комп'ютері (не на GitHub Actions).

pip install telethon
python list_tg_channels.py

При першому запуску введе код з SMS → збереже сесію локально.
Виводить список усіх Telegram-каналів, на які ви підписані,
відсортований за кількістю учасників (спадно).
"""

import asyncio
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

API_ID   = 30430309
API_HASH = "4360b5aa9c5cf78aff7f3ba2d9c661fc"
PHONE    = "+380969025898"

async def main():
    client = TelegramClient("agro_list_session", API_ID, API_HASH)
    await client.start(phone=PHONE)

    print("\n📋 Всі канали та групи (підписки)\n")
    print(f"{'Username':<30} {'Назва':<45} {'Учасники':>10} {'Тип'}")
    print("-" * 100)

    rows = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if not isinstance(entity, (Channel, Chat)):
            continue
        username  = getattr(entity, "username", "") or ""
        title     = entity.title or ""
        members   = getattr(entity, "participants_count", None) or 0
        is_chan   = getattr(entity, "broadcast", False)
        kind      = "канал" if is_chan else "група"
        rows.append((members, username, title, kind))

    rows.sort(reverse=True)
    for members, username, title, kind in rows:
        u = f"@{username}" if username else "(приватний)"
        print(f"{u:<30} {title[:44]:<45} {members:>10,} {kind}")

    print(f"\nВсього: {len(rows)} каналів/груп")
    await client.disconnect()

asyncio.run(main())
