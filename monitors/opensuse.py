#!/usr/bin/env python
import requests
from bs4 import BeautifulSoup

hostname = 'mirror.ufscar.br'
status_url = f'https://download.opensuse.org/app/server/{hostname}'
# No MirrorCache, ratings positivos mantêm a capacidade disponível.
ok_ratings = {'ratinggood', 'ratingquestionable', 'ratingquestinable', 'ratingpoor'}

def check(state=None):
    if state is None:
        state = {}
    previous = state.get("ratings", {})
    current = {}
    alerts = []

    r = requests.get(status_url, timeout=10)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, 'html.parser')

    health_label = soup.find('span', string='Health:')
    if health_label is None:
        return '\n'.join([
            status_url,
            'ALERT: Health section not found'
        ])

    health_div = health_label.find_parent('div')
    if health_div is None:
        return '\n'.join([
            status_url,
            'ALERT: Health section not found'
        ])

    protocols = health_div.find_all('span')[1:]
    if protocols == []:
        alerts.append('ALERT: no protocol health status found')

    for protocol in protocols:
        protocol_name = ''.join(protocol.strings).strip()
        ratings = [x for x in protocol.attrs.get('class', []) if x.startswith('rating')]
        rating = ratings[0] if ratings else 'missing rating'
        current[protocol_name] = rating
        old = previous.get(protocol_name)
        if rating not in ok_ratings and (old is None or old in ok_ratings):
            alerts.append(f'ALERT: {protocol_name}: {rating}')
        elif rating in ok_ratings and old is not None and old not in ok_ratings:
            alerts.append(f'SOLVED: {protocol_name}: {old} → {rating}')

    for missing in previous.keys() - current.keys():
        current[missing] = 'missing protocol'
        if previous[missing] != 'missing protocol':
            alerts.append(f'ALERT: {missing}: missing protocol')
    if protocols:
        state['ratings'] = current

    if alerts != []:
        alerts = [status_url] + alerts

    return '\n'.join(alerts)

if __name__ == '__main__':
    print(check())
