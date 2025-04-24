#!/usr/bin/env python
import requests

subdomain = 'br-mirror'

def check():
    alerts = []

    r = requests.get('https://status.chaotic.cx/mirrors.json', timeout=10)
    r.raise_for_status()

    entries = r.json()['mirrors']

    for entry in entries:
        if entry['subdomain'] != subdomain:
            continue

        if not entry['healthy']:
            alerts.append(f'ALERT: {subdomain} not healthy')

    if alerts != []:
        alerts = ['https://aur.chaotic.cx/mirrors'] + alerts

    return '\n'.join(alerts)

if __name__ == '__main__':
    print(check())
