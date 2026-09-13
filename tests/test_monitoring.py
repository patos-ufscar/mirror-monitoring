from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

import main
from monitors import arch, archlinux32, debian, opensuse


def response(**kwargs):
    result = Mock()
    for key, value in kwargs.items():
        if key == 'json':
            result.json.return_value = value
        else:
            setattr(result, key, value)
    return result


class CycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(patch.object(main, "logger"))

    def document(self, states):
        document = Mock()
        document.get.return_value.exists = True
        document.get.return_value.to_dict.return_value = {'version': 1, 'monitors': states}
        return document

    async def test_one_read_and_write_for_all_monitors(self):
        document = self.document({})
        runner = Mock(side_effect=lambda name, state: ('alert', {'observed': name}))
        send = AsyncMock()
        self.assertTrue(await main.run_cycle(send, lambda: document, runner))
        document.get.assert_called_once_with(retry=None, timeout=15)
        document.set.assert_called_once()
        self.assertEqual(len(document.set.call_args.args[0]['monitors']), len(main.MONITORS))
        self.assertEqual(send.await_count, len(main.MONITORS))

    async def test_first_run_creates_single_document(self):
        document = self.document({})
        document.get.return_value.exists = False
        self.assertTrue(await main.run_cycle(AsyncMock(), lambda: document, lambda n, s: ('', s)))
        document.get.assert_called_once()
        document.set.assert_called_once()
        self.assertEqual(document.set.call_args.args[0]['version'], 1)

    async def test_unchanged_state_does_not_write(self):
        document = self.document({name: {} for name in main.MONITORS})
        self.assertTrue(await main.run_cycle(AsyncMock(), lambda: document, lambda n, s: ('', s)))
        document.set.assert_not_called()

    async def test_failure_preserves_state_and_runs_remaining_monitors(self):
        document = self.document({'arch': {'old': True}})
        visited = []
        def run(name, state):
            visited.append(name)
            state['new'] = True
            if name == 'arch':
                raise RuntimeError('crash')
            return '', state
        self.assertFalse(await main.run_cycle(AsyncMock(), lambda: document, run))
        self.assertEqual(visited, list(main.MONITORS))
        self.assertEqual(document.set.call_args.args[0]['monitors']['arch'], {'old': True})

    async def test_send_failure_does_not_acknowledge_transition(self):
        document = self.document({'opensuse': {'old': True}})
        send = AsyncMock(side_effect=[RuntimeError('Telegram unavailable'), None, None])
        with patch.object(main, 'MONITORS', ('opensuse', 'ubuntu')):
            self.assertFalse(await main.run_cycle(send, lambda: document, lambda n, s: ('alert', {'new': True})))
        stored = document.set.call_args.args[0]['monitors']
        self.assertEqual(stored['opensuse'], {'old': True})
        self.assertEqual(stored['ubuntu'], {'new': True})

    async def test_read_failure_still_runs_all_without_overwriting(self):
        document = self.document({})
        document.get.side_effect = RuntimeError('offline')
        runner = Mock(return_value=('', {}))
        self.assertFalse(await main.run_cycle(AsyncMock(), lambda: document, runner))
        self.assertEqual(runner.call_count, len(main.MONITORS))
        document.set.assert_not_called()

    async def test_write_failure_reported_without_retry(self):
        document = self.document({})
        document.set.side_effect = RuntimeError('offline')
        send = AsyncMock()
        self.assertFalse(await main.run_cycle(send, lambda: document, lambda n, s: ('', {})))
        document.set.assert_called_once()
        self.assertIn('Firestore write failed', send.call_args.args[0])

    async def test_invalid_schema_is_not_overwritten(self):
        document = self.document({})
        document.get.return_value.to_dict.return_value = {'version': 999}
        runner = Mock(return_value=('', {}))
        self.assertFalse(await main.run_cycle(AsyncMock(), lambda: document, runner))
        document.set.assert_not_called()
        self.assertEqual(runner.call_count, len(main.MONITORS))


class MessageTests(unittest.TestCase):
    def test_long_unicode_message_is_preserved(self):
        message = 'Sincronização 🐧\n' * 1000
        parts = list(main.split_message(message, 4096))
        self.assertEqual(''.join(parts), message)
        self.assertTrue(all(len(part.encode('utf-16-le')) // 2 <= 4096 for part in parts))
        self.assertEqual(list(main.split_message('', 4096)), [])


class WorkerTests(unittest.TestCase):
    def test_real_process_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'main.py').write_text(Path(main.__file__).read_text(), encoding='utf-8')
            (root / 'monitors').mkdir()
            cases = [
                ('raise RuntimeError("bug")', RuntimeError),
                ('raise SystemExit(2)', RuntimeError),
                ('import os; os._exit(9)', RuntimeError),
                ('import time; time.sleep(30)', subprocess.TimeoutExpired),
                ('print("invalid JSON"); return ""', json.JSONDecodeError),
            ]
            with patch.object(main, 'ROOT', root):
                for body, error in cases:
                    with self.subTest(body=body):
                        (root / 'monitors/arch.py').write_text(f'def check(state):\n    {body}\n')
                        with self.assertRaises(error):
                            main.run_monitor('arch', {}, timeout=0.5)
                (root / 'monitors/ubuntu.py').write_text('def check(state):\n    state["ok"] = True\n    return "recuperação"\n', encoding='utf-8')
                self.assertEqual(main.run_monitor('ubuntu', {}), ('recuperação', {'ok': True}))


class OpenSUSETests(unittest.TestCase):
    def check(self, state, rating, http='ratinggood'):
        html = f'<div><span>Health:</span><span class="{http}">http</span><span class="{rating}">https</span></div>'
        with patch.object(opensuse.requests, 'get', return_value=response(text=html)):
            return opensuse.check(state)

    def test_transitions_and_recovery_per_protocol(self):
        state = {}
        self.assertEqual(self.check(state, 'ratinggood'), '')
        self.assertIn('ALERT: https: ratingdisabled', self.check(state, 'ratingdisabled'))
        self.assertEqual(self.check(state, 'ratingdisabled'), '')
        self.assertIn('SOLVED: https:', self.check(state, 'ratinggood'))
        self.assertEqual(self.check(state, 'ratinggood'), '')
        self.assertIn('INFO: https:', self.check(state, 'ratingquestionable'))
        self.assertIn('ALERT: http:', self.check(state, 'ratingquestionable', 'ratingdisabled'))

    def test_initial_failure_and_bad_to_bad_transition(self):
        state = {}
        self.assertIn('ALERT:', self.check(state, 'ratingdisabled'))
        self.assertIn('ALERT:', self.check(state, 'ratingbad'))
        self.assertEqual(self.check(state, 'ratingbad'), '')

    def test_missing_health_preserves_state(self):
        state = {'ratings': {'https': 'ratingdisabled'}}
        with patch.object(opensuse.requests, 'get', return_value=response(text='<html/>')):
            self.assertIn('Health section not found', opensuse.check(state))
        self.assertEqual(state['ratings']['https'], 'ratingdisabled')


class ArchTests(unittest.TestCase):
    def test_arch_delay_completion_and_null_delay(self):
        entry = {'url': 'https://mirror.ufscar.br/archlinux/', 'details': 'details',
                 'last_sync': '2026-09-13T00:00:00Z', 'delay': 200, 'completion_pct': 0.5}
        state = {}
        with patch.object(arch, 'expected_entries', 1), patch.object(arch.requests, 'get', return_value=response(json={'urls': [entry]})):
            self.assertIn('DELAY INCREASED', arch.check(state))
            self.assertEqual(arch.check(state), '')
            entry.update(delay=30, completion_pct=1)
            self.assertEqual(arch.check(state).count('SOLVED:'), 2)
            entry.update(delay=None, last_sync=None)
            self.assertIn('UNSYNCED', arch.check(state))

    def test_arch32_stalled_sync_recovers_and_ignores_delay_units(self):
        now = datetime.now(timezone.utc)
        entry = {'url': 'https://mirror.ufscar.br/archlinux32/',
                 'last_sync': (now - timedelta(days=21)).isoformat(),
                 'delay': 0.001, 'completion_pct': 1}
        data = {'last_check': now.isoformat(), 'urls': [entry]}
        state = {}
        with patch.object(archlinux32, 'expected_entries', 1), patch.object(archlinux32.requests, 'get', return_value=response(json=data)):
            self.assertIn('ALERT: last_sync:', archlinux32.check(state))
            self.assertEqual(archlinux32.check(state), '')
            entry['last_sync'] = now.isoformat()
            self.assertIn('SOLVED:', archlinux32.check(state))
            self.assertEqual(archlinux32.check(state), '')
            entry['last_sync'] = None
            self.assertIn('UNSYNCED', archlinux32.check(state))
            entry['completion_pct'] = 0.5
            self.assertIn('completion_pct: 50%', archlinux32.check(state))
            entry['completion_pct'] = 1
            self.assertIn('SOLVED: completion_pct', archlinux32.check(state))

    def test_arch32_missing_mirror_and_stale_feed(self):
        data = {'last_check': datetime.now(timezone.utc).isoformat(), 'urls': []}
        with patch.object(archlinux32.requests, 'get', return_value=response(json=data)):
            self.assertIn('found 0 entries', archlinux32.check({}))
            data['last_check'] = '2026-01-01T00:00:00Z'
            state = {'previous': True}
            self.assertIn('status data', archlinux32.check(state))
            self.assertEqual(state, {'previous': True})


class DebianTests(unittest.TestCase):
    def page(self, overrides=None, missing=(), extra='', error=False):
        lags = {name: '24000' for name in debian.primary_upstreams | {debian.hostname, 'debian.c3sl.ufpr.br'}}
        lags.update(overrides or {})
        header = '<thead><tr><th>Site</th><th>mastertrace</th><th><abbr>archive version</abbr></th><th>last update</th><th>extra</th></tr></thead>'
        rows = []
        for name, lag in lags.items():
            if name in missing:
                continue
            archive_class = 'error' if error and name == debian.hostname else 'age2'
            rows.append(f'<tr><td class="hostname" data-text="{name}">{name}</td><td class="age2">12 h</td><td class="{archive_class}" data-text="{lag}">7 h</td><td class="age2">12 h</td><td>{extra if name == debian.hostname else ""}</td></tr>')
        return '<table>' + header + ''.join(rows) + '</table>'

    def check(self, **kwargs):
        with patch.object(debian.requests, 'get', return_value=response(text=self.page(**kwargs))):
            return debian.check({})

    def test_global_delay_suppressed(self):
        self.assertEqual(self.check(), '')

    def test_any_primary_newer_preserves_alerts(self):
        for upstream in debian.primary_upstreams:
            with self.subTest(upstream=upstream):
                self.assertEqual(self.check(overrides={upstream: '0'}).count('ALERT:'), 3)

    def test_other_mirror_newer_even_when_c3sl_stalled(self):
        self.assertIn('archive version', self.check(overrides={'alternate.example': '0'}))

    def test_missing_or_invalid_primary_preserves_alerts(self):
        for lag in ['max', 'nan', '-1', '']:
            self.assertIn('archive version', self.check(overrides={'syncproxy2.eu.debian.org': lag}))
        self.assertIn('archive version', self.check(missing=['syncproxy2.eu.debian.org']))

    def test_errors_and_extra_are_never_suppressed(self):
        self.assertIn('ALERT: extra: failure', self.check(extra='failure'))
        self.assertIn('ALERT: archive version', self.check(error=True))

    def test_missing_local_mirror(self):
        self.assertIn('not found', self.check(missing=[debian.hostname]))


if __name__ == '__main__':
    unittest.main()
