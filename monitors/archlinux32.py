#!/usr/bin/env python
from datetime import datetime, timezone
from hashlib import shake_128
from urllib.parse import urlsplit

import requests

hostname = 'mirror.ufscar.br'
status_url = 'https://archlinux32.org/mirrors/status/'
expected_entries = 2
max_sync_age = 12 * 60 * 60
max_status_age = 2 * 60 * 60


def parse_time(value):
    timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if timestamp.tzinfo is None:
        raise ValueError('Timestamp without timezone')
    return timestamp


def check(state=None):
    if state is None:
        state = {}
    response = requests.get(status_url + 'json/', timeout=10)
    response.raise_for_status()
    data = response.json()
    now = datetime.now(timezone.utc)
    if (now - parse_time(data['last_check'])).total_seconds() > max_status_age:
        return f'{status_url}\nALERT: mirror status data is more than 2 hours old'

    alerts = []
    found = 0
    for entry in data['urls']:
        url = entry['url']
        if urlsplit(url).hostname != hostname:
            continue
        found += 1
        key = shake_128(url.encode()).hexdigest(8)
        previous = state.get(key, {})
        sync = entry['last_sync']
        # Usamos last_sync: o campo delay da API tem unidades inconsistentes.
        stale = not sync or (now - parse_time(sync)).total_seconds() > max_sync_age
        completion = int(round(100 * entry['completion_pct']))
        messages = []
        if stale and not previous.get('stale', False):
            messages.append(f'ALERT: last_sync: {sync or "UNSYNCED"} (limit: 12 hours)')
        elif not stale and previous.get('stale', False):
            messages.append(f'SOLVED: last_sync: {sync}')
        old_completion = previous.get('completion_pct', 100)
        if completion < old_completion:
            messages.append(f'ALERT: completion_pct: {completion}%')
        elif completion == 100 and old_completion < 100:
            messages.append('SOLVED: completion_pct: 100%')
        state[key] = {'url': url, 'stale': stale, 'completion_pct': completion}
        if messages:
            alerts.extend([url, *messages])

    if found != expected_entries:
        alerts.append(f'ALERT: found {found} entries for {hostname}, expected {expected_entries}')
    return '\n'.join([status_url, *alerts]) if alerts else ''


if __name__ == '__main__':
    print(check())
