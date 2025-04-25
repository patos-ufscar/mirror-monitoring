#!/usr/bin/env python
import requests
from bs4 import BeautifulSoup

hostname = 'mirror.ufscar.br'

def check():
    alerts = []

    status_url = f'https://launchpad.net/ubuntu/+mirror/{hostname}-archive'
    try:
        r = requests.get(status_url, timeout=30)
    except requests.Timeout:
        # launchpad is heavy and suffers from timeout quite frequently
        # let's just hope that next time it comes back
        return ''
    r.raise_for_status()

    soup = BeautifulSoup(r.text, 'html.parser')

    table = soup.find('table', {'id': 'arches'})

    for tr in table.find('tbody').find_all('tr'):
        tds = tr.find_all('td')
        status = tds[-1]
        status_class = status.attrs['class']
        if 'distromirrorstatusUP' not in status_class and 'distromirrorstatusUNKNOWN' not in status_class:
            # each 2 days, status remains unknown for several hours
            # let's just hope it is temporary, alert only if too much sync delay is detected
            alerts.append('ALERT: ' + ': '.join(''.join(td.strings) for td in tds))

    if alerts != []:
        alerts = [status_url] + alerts

    return '\n'.join(alerts)

if __name__ == '__main__':
    print(check())
