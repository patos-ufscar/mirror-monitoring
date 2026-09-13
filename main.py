#!/usr/bin/env python
import asyncio
from copy import deepcopy
import importlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
MONITORS = ('arch', 'archlinux32', 'chaotic', 'debian', 'opensuse', 'ubuntu')
MONITOR_TIMEOUT = 90
logger = logging.getLogger(__name__)


def state_document():
    # Só o processo principal inicializa o Firestore.
    import firebase_admin
    from firebase_admin import firestore

    firebase_admin.initialize_app()
    return firestore.client().collection('mirror-monitoring').document('state')


def run_monitor(name, state, timeout=MONITOR_TIMEOUT):
    result = subprocess.run(
        [sys.executable, str(ROOT / 'main.py'), '--worker', name],
        input=json.dumps(state, ensure_ascii=False, allow_nan=False),
        capture_output=True, encoding='utf-8', timeout=timeout, cwd=ROOT,
    )
    if result.returncode:
        raise RuntimeError(f'exit {result.returncode}: {result.stderr.strip()}')
    if result.stderr.strip():
        logger.warning('%s: %s', name, result.stderr.strip())
    payload = json.loads(result.stdout)
    if not isinstance(payload['state'], dict) or not isinstance(payload['message'], str):
        raise ValueError('Invalid monitor response')
    return payload['message'], payload['state']


async def run_cycle(send, document_factory=state_document, runner=run_monitor):
    errors = []
    document = None
    states = {}
    try:
        candidate = document_factory()
        snapshot = candidate.get(retry=None, timeout=15)
        data = snapshot.to_dict() if snapshot.exists else {'version': 1, 'monitors': {}}
        if data.get('version') != 1 or not isinstance(data.get('monitors'), dict):
            raise ValueError('Invalid persisted state schema')
        states = data['monitors']
        document = candidate
    except Exception as exc:
        errors.append(f'Firestore read failed: {exc}')
        logger.exception('Falha na leitura do estado')

    updated = deepcopy(states)
    for name in MONITORS:
        try:
            message, new_state = runner(name, deepcopy(states.get(name, {})))
            # Só confirmamos transições depois que todas as partes forem enviadas.
            if message:
                await send(message)
            updated[name] = new_state
        except Exception as exc:
            errors.append(f'{name}: {exc}')
            logger.exception('Falha no monitor %s', name)

    if document is not None and updated != states:
        try:
            document.set({'version': 1, 'monitors': updated}, retry=None, timeout=15)
        except Exception as exc:
            errors.append(f'Firestore write failed: {exc}')
            logger.exception('Falha na gravação do estado')

    for error in errors:
        try:
            await send(f'ALERT: {error}')
        except Exception:
            logger.exception('Falha no envio de diagnóstico ao Telegram')
    return not errors


def worker(name):
    if name not in MONITORS:
        raise ValueError(f'Unknown monitor: {name}')
    state = json.load(sys.stdin)
    monitor = importlib.import_module(f'monitors.{name}')
    message = monitor.check(state)
    print(json.dumps({'message': message, 'state': state}, ensure_ascii=False, allow_nan=False))


def split_message(message, limit):
    # Contamos unidades UTF-16 para também respeitar o limite com emojis.
    part = []
    length = 0
    for char in message:
        size = len(char.encode('utf-16-le')) // 2
        if length + size > limit:
            yield ''.join(part)
            part, length = [], 0
        part.append(char)
        length += size
    if part:
        yield ''.join(part)


async def main():
    import telegram
    from telegram.constants import MessageLimit

    async with telegram.Bot(os.environ['TOKEN']) as bot:
        async def send(message):
            for part in split_message(message, MessageLimit.MAX_TEXT_LENGTH):
                await deliver(part)

        async def deliver(part):
            await bot.send_message(
                text=part, parse_mode=None, disable_web_page_preview=True,
                chat_id=os.environ['CHAT_ID'],
            )

        return await run_cycle(send)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
    else:
        sys.exit(0 if asyncio.run(main()) else 1)
