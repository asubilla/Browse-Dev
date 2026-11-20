"""Local browser profiles for the free-first fork: named user-data-dirs, no paid cloud profile needed.

The index lives in the Browse Dev config dir (BROWSE_DEV_CONFIG_DIR, else ~/.config/browse-dev) and maps a name to an
absolute directory. `browse-dev profile use NAME` prints the path to pass to Browser('chromium', user_data_dir=...).
Nothing here touches an account, a key or the network.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

INDEX = 'profiles.json'


def config_dir() -> Path:
	"""The fork's config dir, matching the CLI's BROWSE_DEV_CONFIG_DIR override."""
	return Path(os.environ.get('BROWSE_DEV_CONFIG_DIR') or (Path.home() / '.config' / 'browse-dev'))


def index_path() -> Path:
	return config_dir() / INDEX


def load() -> dict:
	path = index_path()
	if not path.exists():
		return {'profiles': {}, 'default': None}
	try:
		data = json.loads(path.read_text(encoding='utf-8'))
	except (OSError, ValueError):
		return {'profiles': {}, 'default': None}
	if not isinstance(data, dict) or not isinstance(data.get('profiles'), dict):
		return {'profiles': {}, 'default': None}
	return data


def save(data: dict) -> None:
	path = index_path()
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def list_profiles() -> list[str]:
	data = load()
	names = sorted(data['profiles'])
	default = data.get('default')
	return [f"{name}{' *' if name == default else ''}  {data['profiles'][name]['path']}" for name in names]


def add(name: str, source: str | None = None, copy: bool = False) -> str:
	if not name or not all(c.isalnum() or c in '-_' for c in name):
		raise ValueError('profile name: letters, digits, - and _ only')
	data = load()
	base = config_dir() / 'profiles'
	if source:
		src = Path(source).expanduser().resolve()
		if not src.is_dir():
			raise ValueError(f'not a directory: {src}')
		dest = base / name
		if copy:
			if dest.exists():
				raise ValueError(f'profile {name!r} already exists')
			shutil.copytree(src, dest)
		path = dest if copy else src
	else:
		path = base / name
		path.mkdir(parents=True, exist_ok=True)
	data['profiles'][name] = {'path': str(path), 'created': datetime.now(timezone.utc).isoformat()}
	if not data.get('default'):
		data['default'] = name
	save(data)
	return str(path)


def use(name: str) -> str:
	data = load()
	if name not in data['profiles']:
		raise ValueError(f'unknown profile {name!r}; known: {", ".join(sorted(data["profiles"])) or "(none)"}')
	data['default'] = name
	save(data)
	return data['profiles'][name]['path']


def remove(name: str) -> None:
	data = load()
	if name not in data['profiles']:
		raise ValueError(f'unknown profile {name!r}')
	del data['profiles'][name]
	if data.get('default') == name:
		data['default'] = next(iter(sorted(data['profiles'])), None)
	save(data)


HELP = """browse-dev profile - named local Chrome profiles (free, no cloud account)

  browse-dev profile list              list name, default marker and user-data-dir
  browse-dev profile save NAME [PATH]  register an existing Chrome user-data-dir, or create an empty one
  browse-dev profile save NAME PATH --copy   copy the directory instead of registering it in place
  browse-dev profile use NAME          set the default and print its path
  browse-dev profile remove NAME       forget a profile (files are left alone)

Use in code:  Browser('chromium', user_data_dir='<path printed by use>')
"""

HANDLERS = {'list': list_profiles, 'save': add, 'use': use, 'remove': remove}


def handle(args: list[str]) -> int:
	"""CLI entry point. Returns a process exit code."""
	if not args or args[0] in ('--help', '-h', 'help'):
		print(HELP)
		return 0
	action, rest = args[0], args[1:]
	handler = HANDLERS.get(action)
	if handler is None:
		print(f'Unknown profile action {action!r}\n\n{HELP}', file=__import__('sys').stderr)
		return 2
	try:
		if action == 'save':
			copy = '--copy' in rest
			words = [a for a in rest if a != '--copy']
			if not words or len(words) > 2:
				print('Usage: browse-dev profile save NAME [PATH] [--copy]', file=__import__('sys').stderr)
				return 2
			result = add(words[0], words[1] if len(words) == 2 else None, copy)
		else:
			if len(rest) != 1 and action != 'list':
				print(f'Usage: browse-dev profile {action} NAME', file=__import__('sys').stderr)
				return 2
			result = handler(rest[0]) if rest else handler()
	except ValueError as e:
		print(str(e), file=__import__('sys').stderr)
		return 1
	if isinstance(result, list):
		for line in result:
			print(line)
	elif result is not None:
		print(result)
	return 0
