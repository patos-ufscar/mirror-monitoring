#!/usr/bin/env python
import requests
from datetime import datetime, timezone
from hashlib import shake_128
import firebase_admin
from firebase_admin import firestore

app = firebase_admin.initialize_app()
db = firestore.client()

hostname = 'mirror.ufscar.br'
expected_entries = 2
delay_mean = 30
delay_dev = 60

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

        url_hash = shake_128(url.encode()).hexdigest(8)

        found += 1

        alerts = []

        if not entry['last_sync']:
            alerts.append('ALERT: UNSYNCED')

        delay = entry['delay']
        doc_ref = db.collection('mirror-monitoring', 'arch', 'delay').document(url_hash)
        doc = doc_ref.get()
        last_delay = doc.to_dict()['last_delay'] if doc.exists else delay_mean
        if delay > last_delay + delay_dev:
            alerts.append(f'ALERT: DELAY INCREASED to {delay} seconds')

        if delay <= delay_mean + delay_dev and last_delay != delay_mean:
            alerts.append(f'SOLVED: delay: {delay} seconds')
            doc_ref.set({'url': url, 'last_delay': delay_mean})
        elif not (last_delay - delay_dev < delay < last_delay + delay_dev):
            doc_ref.set({'url': url, 'last_delay': delay})

        completion_pct = int(round(100*entry['completion_pct']))

        doc_ref = db.collection('mirror-monitoring', 'arch', 'completion_pct').document(url_hash)
        doc = doc_ref.get()
        last_completion_pct = doc.to_dict()['last_completion_pct'] if doc.exists else 100
        if last_completion_pct != completion_pct:
            doc_ref.set({'url': url, 'last_completion_pct': completion_pct})

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
