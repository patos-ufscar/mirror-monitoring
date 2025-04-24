#!/usr/bin/env python
import requests
from bs4 import BeautifulSoup

hostname = 'mirror.ufscar.br'

def check():
    alerts = []

    status_url = f'https://launchpad.net/ubuntu/+mirror/{hostname}-archive'
    r = requests.get(status_url, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, 'html.parser')

    table = soup.find('table', {'id': 'arches'})

    for tr in table.find('tbody').find_all('tr'):
        tds = tr.find_all('td')
        status = tds[-1]
        if not 'distromirrorstatusUP' in status.attrs['class']:
            alerts.append('ALERT: ' + ': '.join(''.join(td.strings) for td in tds))

    if alerts != []:
        alerts = [status_url] + alerts

    return '\n'.join(alerts)

if __name__ == '__main__':
    print(check())
