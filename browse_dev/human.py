"""Free, practical human-like interaction helpers for QA/automation on sites you are allowed to test.

These are *input* and *pacing* helpers: natural typing rhythm, curved mouse movement, eased scroll, think time and a
per-origin polite interval. They are not a CAPTCHA solver or a fingerprint spoofer; `fingerprint_audit()` only reports
inconsistencies so you can fix your own setup. Nothing here contacts a service or needs an account.

Configure with `browse-dev human --profile natural|fast|off --show`, or call configure() from a cell.
"""

from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path
from typing import Any

PROFILES = {
	'natural': {'key_ms': 95, 'key_jitter': 45, 'word_pause_ms': 180, 'mouse_steps': 14, 'mouse_jitter': 2.5, 'think_ms': 700, 'min_interval_ms': 350},
	'fast': {'key_ms': 25, 'key_jitter': 12, 'word_pause_ms': 60, 'mouse_steps': 6, 'mouse_jitter': 1.0, 'think_ms': 200, 'min_interval_ms': 80},
	'off': {'key_ms': 0, 'key_jitter': 0, 'word_pause_ms': 0, 'mouse_steps': 1, 'mouse_jitter': 0, 'think_ms': 0, 'min_interval_ms': 0},
}
_SETTINGS_FILE = 'human.json'
_LOG_FILE = 'audit.jsonl'
_enabled = dict(PROFILES['natural'])
_profile = 'natural'
_rng = random.Random()
_last_request: dict[str, float] = {}


def config_dir() -> Path:
	from browse_dev.config import CONFIG

	return CONFIG.BROWSE_DEV_CONFIG_DIR


def _settings_path() -> Path:
	return config_dir() / _SETTINGS_FILE


def load() -> dict[str, Any]:
	"""Load persisted settings, falling back to the natural profile."""
	try:
		data = json.loads(_settings_path().read_text(encoding='utf-8'))
	except (OSError, ValueError):
		return {'profile': _profile, **_enabled}
	profile = data.get('profile', 'natural')
	if profile not in PROFILES:
		profile = 'natural'
	return {'profile': profile, **{k: data.get(k, v) for k, v in PROFILES[profile].items()}}


def configure(profile: str = 'natural', *, seed: int | None = None, **overrides: Any) -> dict[str, Any]:
	"""Set the active profile (and optional RNG seed for reproducible tests), persist it, and return the settings."""
	global _enabled, _profile
	if profile not in PROFILES:
		raise ValueError(f'unknown profile {profile!r}; pick natural, fast or off')
	_profile = profile
	_enabled = dict(PROFILES[profile])
	for key, value in overrides.items():
		if key not in _enabled:
			raise ValueError(f'unknown human setting {key!r}')
		if not isinstance(value, (int, float)) or value < 0:
			raise ValueError(f'{key} must be a non-negative number')
		_enabled[key] = value
	if seed is not None:
		_rng.seed(seed)
	_settings_path().write_text(json.dumps({'profile': profile, **_enabled}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
	return settings()


def settings() -> dict[str, Any]:
	"""A copy of the active settings (safe to print)."""
	return {'profile': _profile, **_enabled}


def _sleep(ms: float) -> None:
	if ms > 0:
		time.sleep(ms / 1000.0)


def think(ms: float | None = None) -> None:
	"""A natural reading pause around the configured think time."""
	base = _enabled['think_ms'] if ms is None else ms
	_spread = max(1.0, base * 0.4)
	_sleep(max(0.0, _rng.gauss(base, _spread)))


def human_type(text: str) -> None:
	"""Type text in small chunks with per-key jitter and short pauses at word boundaries."""
	from browser_harness import helpers

	if not text:
		return
	if _enabled['key_ms'] == 0:
		helpers.type_text(text)
		return
	buffer = ''
	for ch in text:
		buffer += ch
		if ch.isspace() or len(buffer) >= 12:
			helpers.type_text(buffer)
			buffer = ''
			delay = _enabled['word_pause_ms'] if ch.isspace() else _enabled['key_ms']
			_sleep(max(0.0, _rng.gauss(delay, _enabled['key_jitter'])))
	if buffer:
		helpers.type_text(buffer)


def human_click(x: float, y: float) -> None:
	"""Move along a slightly curved path, then click with a small offset from the exact center."""
	global _current_mouse
	from browser_harness import helpers

	steps = max(1, int(_enabled['mouse_steps']))
	jitter = float(_enabled['mouse_jitter'])
	start = _current_mouse or (x, y)
	for i in range(1, steps + 1):
		t = i / steps
		ease = t * t * (3 - 2 * t)  # smoothstep: slow at both ends
		cx = start[0] + (x - start[0]) * ease + math.sin(t * math.pi) * jitter * _rng.uniform(-1, 1)
		cy = start[1] + (y - start[1]) * ease + math.sin(t * math.pi) * jitter * _rng.uniform(-1, 1)
		helpers.cdp('Input.dispatchMouseEvent', type='mouseMoved', x=cx, y=cy)
		_sleep(_enabled['key_ms'] / 3)
	_current_mouse = (x, y)
	helpers.click_at_xy(x + _rng.uniform(-jitter, jitter), y + _rng.uniform(-jitter, jitter))


_current_mouse: tuple[float, float] | None = None


def human_scroll(dy: float, *, x: float = 0, y: float = 0) -> None:
	"""Scroll in eased steps instead of one large jump."""
	from browser_harness import helpers

	steps = max(1, int(_enabled['mouse_steps']))
	done = 0.0
	for i in range(steps):
		t = (i + 1) / steps
		target = dy * t * t * (3 - 2 * t)
		helpers.scroll(x, y, target - done)
		done = target
		_sleep(_enabled['key_ms'] / 2)


def pace(origin: str) -> None:
	"""Keep a minimum interval between actions on the same origin, so bursts never happen."""
	minimum = float(_enabled['min_interval_ms']) / 1000.0
	if minimum <= 0:
		return
	now = time.monotonic()
	previous = _last_request.get(origin)
	if previous is not None:
		wait = previous + minimum - now
		if wait > 0:
			_sleep(wait * 1000)
	_last_request[origin] = time.monotonic()


def fingerprint_audit() -> dict[str, Any]:
	"""Read-only page audit: report signals that disagree, with fix suggestions. No spoofing."""
	from browser_harness import helpers

	info = helpers.js("""(() => {
		const n = navigator;
		return {
			userAgent: n.userAgent,
			platform: n.platform,
			languages: n.languages || [n.language],
			webdriver: !!n.webdriver,
			screen: [screen.width, screen.height, screen.colorDepth],
			viewport: [innerWidth, innerHeight],
			dpr: devicePixelRatio,
			timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
			touch: 'ontouchstart' in window,
			hardwareConcurrency: n.hardwareConcurrency,
		};
	})()""") or {}
	problems = []
	if info.get('webdriver'):
		problems.append('navigator.webdriver is true: Chrome was launched with --enable-automation')
	if info.get('platform', '').lower().startswith('linux') and 'Mac' in str(info.get('userAgent')):
		problems.append('platform and userAgent disagree')
	if info.get('touch') and 'Mobile' not in str(info.get('userAgent')):
		problems.append('touch support without a mobile userAgent')
	return {'signals': info, 'problems': problems, 'note': 'Read-only audit. No fingerprint is spoofed.'}


def audit_log(event: str, **fields: Any) -> None:
	"""Append one JSON line to the local audit log (never secrets)."""
	from datetime import datetime, timezone

	entry = {'at': datetime.now(timezone.utc).isoformat(), 'event': event, **fields}
	with (config_dir() / _LOG_FILE).open('a', encoding='utf-8') as f:
		f.write(json.dumps(entry, sort_keys=True) + '\n')


def audit_read(limit: int = 50) -> list[dict[str, Any]]:
	"""Return the last `limit` audit entries (most recent last)."""
	path = config_dir() / _LOG_FILE
	if not path.exists():
		return []
	lines = path.read_text(encoding='utf-8').splitlines()
	result = []
	for line in lines[-limit:]:
		try:
			result.append(json.loads(line))
		except ValueError:
			continue
	return result


HELP = """browse-dev human - free human-like input, pacing and audit settings

  browse-dev human --show                  print the active profile and settings
  browse-dev human --profile natural|fast|off
  browse-dev human --profile fast --key-ms 40   override a single setting
  browse-dev human --seed 7                reproducible randomness (tests)

Profiles: natural (default), fast, off (full speed). In a cell: human_type(), human_click(),
human_scroll(), think(), pace(origin), fingerprint_audit(), audit_log(), audit_read().
"""


def handle(args: list[str]) -> int:
	"""CLI entry point. Returns a process exit code."""
	import sys

	if not args or '--help' in args or '-h' in args:
		print(HELP)
		return 0
	profile = None
	seed = None
	overrides = {}
	i = 0
	while i < len(args):
		arg = args[i]
		if arg == '--profile' and i + 1 < len(args):
			profile = args[i + 1]
			i += 2
		elif arg == '--seed' and i + 1 < len(args):
			try:
				seed = int(args[i + 1])
			except ValueError:
				print('--seed needs an integer', file=sys.stderr)
				return 2
			i += 2
		elif arg.startswith('--') and arg[2:].replace('-', '_') in PROFILES['natural'] and i + 1 < len(args):
			key = arg[2:].replace('-', '_')
			try:
				overrides[key] = float(args[i + 1])
			except ValueError:
				print(f'{arg} needs a number', file=sys.stderr)
				return 2
			i += 2
		elif arg == '--show':
			i += 1
		else:
			print(f'Unknown argument {arg!r}\n\n{HELP}', file=sys.stderr)
			return 2
	try:
		if profile or overrides or seed is not None:
			configure(profile or load()['profile'], seed=seed, **overrides)
		for key, value in settings().items():
			print(f'{key}: {value}')
	except ValueError as e:
		print(str(e), file=sys.stderr)
		return 1
	return 0


def install() -> None:
	"""Expose these helpers in REPL cells, like live view."""
	from browser_harness import helpers

	for name in (
		'configure', 'settings', 'think', 'human_type', 'human_click', 'human_scroll', 'pace',
		'fingerprint_audit', 'audit_log', 'audit_read',
	):
		setattr(helpers, name, globals()[name])
