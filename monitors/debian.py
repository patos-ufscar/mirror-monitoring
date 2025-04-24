#!/usr/bin/env python
import requests
from bs4 import BeautifulSoup

hostname = 'mirror.ufscar.br'

def check():
    alerts = []

    r = requests.get('https://mirror-master.debian.org/status/mirror-status.html', timeout=10)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, 'html.parser')

    thead = soup.find('thead')
    column_names = [x.string for x in thead.find_all('th')]

    #tr = soup.find('tr', {'id': hostname})   # does not work if mirror is errored for a long time
    for tr in soup.find_all('tr'):
        td_hostname = tr.find('td', {'class': 'hostname'})
        if td_hostname is None:
            continue
        if td_hostname.attrs['data-text'] != hostname:
            continue
        for td, col_name in zip(tr.find_all('td'), column_names):
            td_class = td.attrs.get('class', [])
            age = [x for x in td_class if x.startswith('age')]
            value = ''.join(td.strings).strip()
            age_warn = age != [] and age != ['age0']
            if col_name == 'last update':
                # be more tolerant
                age_warn = age_warn and age != ['age1']
            if 'error' in td_class or age_warn:
                alerts.append(f'ALERT: {col_name}: {value}')
            if col_name == 'extra' and value != '':
                alerts.append(f'ALERT: extra: {value}')

    if alerts != []:
        alerts = [f'https://mirror-master.debian.org/status/mirror-status.html#{hostname}'] + alerts

    return '\n'.join(alerts)

if __name__ == '__main__':
    print(check())
