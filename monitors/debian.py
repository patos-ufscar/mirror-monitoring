#!/usr/bin/env python
import math
import requests
from bs4 import BeautifulSoup

hostname = 'mirror.ufscar.br'

# A ausência de qualquer referência impede a supressão de alertas.
primary_upstreams = {
    'ftp-master.debian.org',
    'syncproxy2.eu.debian.org', 'syncproxy4.eu.debian.org',
    'syncproxy2.wna.debian.org', 'syncproxy3.wna.debian.org',
}
age_columns = {'mastertrace', 'archive version', 'last update'}


def archive_lag(row, columns):
    cell = dict(zip(columns, row.find_all('td'))).get('archive version')
    if cell is None or 'error' in cell.get('class', []) or cell.select_one('.error'):
        return None
    try:
        value = float(cell['data-text'])
        return value if math.isfinite(value) and value >= 0 else None
    except (KeyError, ValueError, TypeError):
        return None


def no_newer_archive(rows, columns):
    local_lag = archive_lag(rows[hostname], columns)
    if local_lag is None:
        return False
    required = primary_upstreams | {
        name for name in rows if name.startswith('syncproxy') and name.endswith('.debian.org')
    }
    if not required.issubset(rows):
        return False
    for name in required:
        lag = archive_lag(rows[name], columns)
        if lag is None or lag < local_lag:
            return False
    # Qualquer outro mirror com versão mais nova também impede a supressão,
    # inclusive se o C3SL e os syncproxies estiverem temporariamente atrasados.
    return all(
        lag is None or lag >= local_lag
        for row in rows.values()
        for lag in [archive_lag(row, columns)]
    )


def check(state=None):
    alerts = []

    r = requests.get('https://mirror-master.debian.org/status/mirror-status.html', timeout=10)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, 'html.parser')

    thead = soup.find('thead')
    column_names = [x.get_text(strip=True) for x in thead.find_all('th')]
    rows = {}
    for row in soup.find_all('tr'):
        cell = row.find('td', {'class': 'hostname'})
        if cell is not None:
            rows[cell['data-text']] = row
    suppress_age = hostname in rows and no_newer_archive(rows, column_names)

    found = False

    # O atributo id desaparece após falhas prolongadas; usamos data-text.
    for tr in soup.find_all('tr'):
        td_hostname = tr.find('td', {'class': 'hostname'})
        if td_hostname is None:
            continue
        if td_hostname.attrs['data-text'] != hostname:
            continue
        found = True
        for td, col_name in zip(tr.find_all('td'), column_names):
            td_class = td.attrs.get('class', [])
            age = [x for x in td_class if x.startswith('age')]
            value = ''.join(td.strings).strip()
            age_warn = age != [] and age != ['age0']
            if col_name in {'mastertrace', 'last update'}:
                # Toleramos mais atraso nestas colunas.
                age_warn = age_warn and age != ['age1']
            if suppress_age and col_name in age_columns:
                age_warn = False
            if 'error' in td_class or td.select_one('.error') or age_warn:
                alerts.append(f'ALERT: {col_name}: {value}')
            if col_name == 'extra' and value != '':
                alerts.append(f'ALERT: extra: {value}')

    if alerts != []:
        alerts = [f'https://mirror-master.debian.org/status/mirror-status.html#{hostname}'] + alerts

    if not found:
        alerts.extend([
            'https://mirror-master.debian.org/status/mirror-status.html',
            f'ALERT: {hostname} not found in the mirror list'
        ])

    return '\n'.join(alerts)

if __name__ == '__main__':
    print(check())
