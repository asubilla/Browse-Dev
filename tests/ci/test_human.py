from __future__ import annotations

import pytest

import browse_dev.human as human


@pytest.fixture(autouse=True)
def local_settings(monkeypatch, tmp_path):
	monkeypatch.setenv('BROWSE_DEV_CONFIG_DIR', str(tmp_path))
	original = human.settings()
	human.configure('fast', seed=1)
	yield
	human.configure(original['profile'])


def test_configure_persists_settings(monkeypatch, tmp_path):
	human.configure('natural', seed=7, key_ms=50)
	assert human.settings()['profile'] == 'natural'
	assert human.settings()['key_ms'] == 50
	assert human.load()['key_ms'] == 50
	with pytest.raises(ValueError, match='unknown profile'):
		human.configure('robot')


def test_human_type_chunks_and_pauses(monkeypatch):
	from browser_harness import helpers

	typed = []
	slept = []
	monkeypatch.setattr(helpers, 'type_text', lambda text: typed.append(text))
	monkeypatch.setattr(human.time, 'sleep', lambda seconds: slept.append(seconds))
	human.configure('natural', seed=3)
	human.human_type('hello world')
	assert ''.join(typed) == 'hello world'
	assert typed != ['hello world']  # chunked, not one paste
	assert slept and all(s >= 0 for s in slept)


def test_off_profile_types_in_one_piece(monkeypatch):
	from browser_harness import helpers

	typed = []
	monkeypatch.setattr(helpers, 'type_text', lambda text: typed.append(text))
	monkeypatch.setattr(human.time, 'sleep', lambda seconds: pytest.fail('off profile must not sleep'))
	human.configure('off')
	human.human_type('hello world')
	assert typed == ['hello world']


def test_human_click_moves_then_clicks(monkeypatch):
	from browser_harness import helpers

	moves = []
	clicks = []
	monkeypatch.setattr(helpers, 'cdp', lambda method, **params: moves.append(params) if method == 'Input.dispatchMouseEvent' else None)
	monkeypatch.setattr(helpers, 'click_at_xy', lambda x, y: clicks.append((x, y)))
	monkeypatch.setattr(human.time, 'sleep', lambda seconds: None)
	human.configure('natural', seed=2)
	human.human_click(100, 200)
	assert len(moves) == 14
	assert len(clicks) == 1
	assert abs(clicks[0][0] - 100) < 5 and abs(clicks[0][1] - 200) < 5


def test_pace_enforces_a_minimum_interval(monkeypatch):
	clock = [0.0]
	slept = []
	monkeypatch.setattr(human.time, 'monotonic', lambda: clock[0])
	monkeypatch.setattr(human.time, 'sleep', lambda seconds: (slept.append(seconds), clock.__setitem__(0, clock[0] + seconds)))
	human.configure('natural', min_interval_ms=200)
	human._last_request.clear()
	human.pace('example.com')
	clock[0] += 0.05
	human.pace('example.com')
	assert slept and slept[0] > 0
	human.pace('other.test')
	assert len(slept) == 1  # per origin


def test_audit_log_round_trip():
	human.audit_log('click', url='https://example.com')
	human.audit_log('type', field='password')  # no value recorded
	entries = human.audit_read()
	assert [e['event'] for e in entries] == ['click', 'type']
	assert 'value' not in entries[1]


def test_fingerprint_audit_reports_webdriver(monkeypatch):
	from browser_harness import helpers

	monkeypatch.setattr(
		helpers, 'js',
		lambda code: {'userAgent': 'Mozilla/5.0 (Macintosh)', 'platform': 'Linux x86_64', 'webdriver': True, 'touch': False},
	)
	report = human.fingerprint_audit()
	assert any('webdriver' in p or 'platform' in p for p in report['problems'])
	assert 'No fingerprint is spoofed' in report['note']
