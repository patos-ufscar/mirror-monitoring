#!/usr/bin/env python
import requests
from datetime import datetime, timezone

hostname = 'mirror.ufscar.br'
min_completion_pct = 1.0
max_delay = 90

def check():
    all_alerts = []

    r = requests.get('https://archlinux.org/mirrors/status/json/', timeout=10)
    r.raise_for_status()

    entries = r.json()['urls']

    for entry in entries:
        url = entry['url']
        if f'//{hostname}/' not in url:
            continue

        alerts = []

        if not entry['last_sync']:
            alerts.append('ALERT: UNSYNCED')
        if entry['completion_pct'] < min_completion_pct:
            alerts.append(f'ALERT: completion_pct: {100*entry['completion_pct']:.1f}%')
        if entry['delay'] > max_delay:
            alerts.append(f'ALERT: delay: {entry['delay']} seconds')

        if alerts != []:
            alerts = [url, entry['details']] + alerts
        all_alerts.extend(alerts)

    return '\n'.join(all_alerts)

def parse_time(s):
    return datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)

if __name__ == '__main__':
    print(check())
