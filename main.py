#!/usr/bin/env python
import os
import asyncio
import subprocess
import telegram
from telegram.constants import MessageLimit
from telegram_send.utils import split_message

async def main():
    bot = telegram.Bot(os.getenv('TOKEN'))

    for file in os.listdir('monitors'):
        file = os.path.join('monitors', file)
        if not os.path.isfile(file) or not os.access(file, os.X_OK):
            continue
        p = subprocess.run([file], capture_output=True, encoding='utf-8')
        messages = []
        if p.stderr.strip() != '':
            messages.append(f'{file}: {p.stderr.strip()}')
        if p.stdout.strip() != '':
            messages.append(p.stdout.strip())
        for message in messages:
            for part in split_message(message, MessageLimit.MAX_TEXT_LENGTH):
                await bot.send_message(
                    text=part,
                    parse_mode=None,
                    disable_web_page_preview=True,
                    chat_id=os.getenv("CHAT_ID")
                )

if __name__ == '__main__':
    asyncio.run(main())
