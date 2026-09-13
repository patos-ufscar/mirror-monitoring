#!/usr/bin/env python
import requests
from datetime import datetime, timezone
from hashlib import shake_128

hostname = 'mirror.ufscar.br'
expected_entries = 2
delay_mean = 30
delay_dev = 60

def check(state=None):
    if state is None:
        state = {}
    all_alerts = []

    r = requests.get('https://archlinux.org/mirrors/status/json/', timeout=10)
    r.raise_for_status()

    entries = r.json()['urls']

    found = 0

    for entry in entries:
        url = entry['url']
        if f'//{hostname}/' not in url:
            continue

        url_hash = shake_128(url.encode()).hexdigest(8)

        found += 1

        alerts = []

        if not entry['last_sync']:
            alerts.append('ALERT: UNSYNCED')

        delay = entry['delay']
        previous = state.setdefault(url_hash, {'url': url})
        last_delay = previous.get('last_delay', delay_mean)
        if delay is None:
            alerts.append('ALERT: delay unavailable')
        elif delay > last_delay + delay_dev:
            alerts.append(f'ALERT: DELAY INCREASED to {delay} seconds')
            previous['last_delay'] = delay
        elif delay <= delay_mean + delay_dev and last_delay != delay_mean:
            alerts.append(f'SOLVED: delay: {delay} seconds')
            previous['last_delay'] = delay_mean
        elif delay < last_delay - delay_dev:
            previous['last_delay'] = delay

        completion_pct = int(round(100*entry['completion_pct']))

        last_completion_pct = previous.get('last_completion_pct', 100)
        previous['last_completion_pct'] = completion_pct

        if completion_pct < last_completion_pct:
            alerts.append(f'ALERT: completion_pct: {completion_pct}%')
        elif completion_pct == 100 and last_completion_pct < 100:
            alerts.append(f'SOLVED: completion_pct: {completion_pct}%')

        if alerts != []:
            alerts = [url, entry['details']] + alerts
        all_alerts.extend(alerts)

    if found != expected_entries:
        all_alerts.extend([
            'https://archlinux.org/mirrors/status',
            f'ALERT: found only {found} entries for {hostname}, expected {expected_entries}'
        ])

    return '\n'.join(all_alerts)

def parse_time(s):
    return datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)

if __name__ == '__main__':
    print(check())
