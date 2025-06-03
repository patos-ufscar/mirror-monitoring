#!/usr/bin/env python
import requests
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import firestore

app = firebase_admin.initialize_app()
db = firestore.client()

hostname = 'mirror.ufscar.br'
expected_entries = 2
max_delay = 90

def check():
    all_alerts = []

    r = requests.get('https://archlinux.org/mirrors/status/json/', timeout=10)
    r.raise_for_status()

    entries = r.json()['urls']

    found = 0

    for entry in entries:
        url = entry['url']
        if f'//{hostname}/' not in url:
            continue

        found += 1

        alerts = []

        if not entry['last_sync']:
            alerts.append('ALERT: UNSYNCED')
        if entry['delay'] > max_delay:
            alerts.append(f'ALERT: delay: {entry['delay']} seconds')

        completion_pct = int(round(100*entry['completion_pct']))

        doc_ref = db.collection('mirror-monitoring', 'arch', 'completion_pct').document(url)
        doc = doc_ref.get()
        last_completion_pct = doc.to_dict()['last_completion_pct'] if doc.exists else 100
        doc_ref.set({'last_completion_pct': completion_pct})

        if completion_pct < last_completion_pct:
            alerts.append(f'ALERT: completion_pct: {completion_pct}%')

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
