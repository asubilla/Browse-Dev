"""The line a failed CLI or --cli-mcp call gets when PyPI has a newer browse-dev. An agent on an old version kept
retrying an error a later release fixed (1.0.2's no-display remote-debugging-setup, fixed in 1.0.3): it never learned
to upgrade. Only the CLI uses it, never the Agent."""

import json
import os
import re
import sys
import threading
import time
from pathlib import Path

PYPI_JSON = 'https://pypi.org/pypi/browse-dev/json'
CACHE_SECONDS = 24 * 3600
OFFLINE_CACHE_SECONDS = 3600  # a failed lookup is not retried for an hour: a call offline waits once, not each time
TIMEOUT_SECONDS = 2.0


def upgrade_hint(e: BaseException, mcp: bool = False) -> str:
	"""One line naming the newer version and the command that installs it (mcp: then the server restart that loads
	it), for an error attaching a browser; '' when up to date, unknown, offline, in CI, opted out
	(BROWSE_DEV_NO_UPDATE_CHECK=1), from a checkout, or for an error an upgrade does not fix. Never raises, and waits at
	most TIMEOUT_SECONDS (once a day: the answer is cached)."""
	try:
		from browser_harness.auth import CloudAuthRequired

		from browse_dev.utils import get_browse_dev_version, get_install_source

		if (
			os.environ.get('BROWSE_DEV_NO_UPDATE_CHECK', '').strip().lower() in ('1', 'true', 'yes')
			or os.environ.get('CI', '').strip().lower() not in ('', '0', 'false')
			or isinstance(e, CloudAuthRequired)  # signing in fixes it
			or str(e).startswith('daemon-starting:')  # a retry fixes it
			or get_install_source() in ('editable', 'git')  # a checkout: pip install -U would replace it
		):
			return ''
		current = get_browse_dev_version()
		if (have := _key(current)) is None:
			return ''
		latest = _latest()
		if latest is None or (newer := _key(latest)) is None or newer <= have:
			return ''
		hint = f'browse-dev {latest} is out (you have {current}); if this error persists, upgrading may fix it: '
		return hint + upgrade_command() + (', then restart this MCP server' if mcp else '')
	except Exception:
		return ''


def upgrade_command() -> str:
	"""The command that upgrades this install, from how it was installed."""
	from browse_dev.utils import get_browse_dev_version

	prefix = Path(sys.prefix)
	if 'archive-v0' in prefix.parts:  # uvx's cached env: unpinned it resolves the newest on start, `==1.0.3` never moves
		return f'uvx browse-dev@latest (in an MCP config: browse-dev@latest, not browse-dev=={get_browse_dev_version()})'
	if (prefix / 'uv-receipt.toml').is_file():  # a uv tool env
		# not `uv tool upgrade`: it keeps the version pin `uv tool install browse-dev==1.0.2` wrote, and upgrades nothing
		return 'uv tool install browse-dev@latest'
	if (prefix / 'pipx_metadata.json').is_file():
		return 'pipx upgrade browse-dev'
	import importlib.util

	try:
		uv_venv = re.search(r'^uv\s*=', (prefix / 'pyvenv.cfg').read_text(encoding='utf-8'), re.M) is not None
	except OSError:
		uv_venv = False
	python = f'"{sys.executable}"' if ' ' in sys.executable else sys.executable  # C:\Program Files\...
	if uv_venv and importlib.util.find_spec('pip') is None:  # uv venv creates no pip
		return f'uv pip install --python {python} -U browse-dev'
	return f'{python} -m pip install -U browse-dev'


def _key(v: str) -> tuple[int, ...] | None:
	"""1.0.3rc1 < 1.0.3 < 1.0.10; None for 'unknown'."""
	m = re.match(r'(\d+)\.(\d+)(?:\.(\d+))?(?:(a|b|rc)(\d+))?', v)
	if not m:
		return None
	major, minor, patch, pre, n = m.groups()
	return (int(major), int(minor), int(patch or 0), {'a': 0, 'b': 1, 'rc': 2}.get(pre or '', 3), int(n or 0))


def _latest() -> str | None:
	"""PyPI's latest browse-dev, cached in the CLI's config dir; None offline."""
	from browse_dev.config import CONFIG

	cache = CONFIG.BROWSE_DEV_CONFIG_DIR / 'latest_version.json'
	try:
		cached = json.loads(cache.read_text(encoding='utf-8'))
		if time.time() - cached['checked_at'] < (CACHE_SECONDS if cached['latest'] else OFFLINE_CACHE_SECONDS):
			return cached['latest']
	except (OSError, ValueError, KeyError, TypeError):
		pass
	found: list[str] = []

	def fetch() -> None:
		import urllib.request

		try:
			with urllib.request.urlopen(PYPI_JSON, timeout=TIMEOUT_SECONDS) as r:
				found.append(str(json.loads(r.read())['info']['version']))
		except Exception:  # offline, blocked, or not PyPI's JSON: no line, and never a thread traceback on stderr
			pass

	thread = threading.Thread(target=fetch, daemon=True)  # urlopen's timeout does not cover a DNS lookup
	thread.start()
	thread.join(TIMEOUT_SECONDS)
	latest = found[0] if found else None
	try:
		cache.write_text(json.dumps({'latest': latest, 'checked_at': time.time()}), encoding='utf-8')
	except OSError:
		pass
	return latest
