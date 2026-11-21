"""Self-healing selectors: try several locator strategies in order, fall back when one fails.

The public API (``Selector``, ``selector``, ``resolve``, ``click``, ``fill``, ``record``) has no
third-party imports at module load time: browser_harness's helpers are imported lazily, only when
no helper object was supplied. That keeps importing this module -- and its pure unit tests --
independent of a running browser. This is reliability code only: no fingerprinting, no page code
execution, no evasion.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# The only strategy kinds resolve() knows. Unknown kinds are skipped and recorded, never fatal.
KINDS = frozenset({'css', 'xpath', 'role', 'text', 'axid'})
# Priority used by the selector() convenience constructor: structural first, semantic/fuzzy last.
_PRIORITY = ('css', 'xpath', 'axid', 'role', 'text')
_WS = re.compile(r'\s+')

__all__ = ['KINDS', 'Selector', 'selector', 'resolve', 'click', 'fill', 'record']


@dataclass
class Selector:
	"""An ordered list of ``(kind, value)`` strategies and an optional human label.

	``kind`` is one of ``{'css', 'xpath', 'role', 'text', 'axid'}``. ``resolve`` stops at the first
	strategy that finds a node; a strategy that raises is recorded and the next one is tried.
	"""

	strategies: list[tuple[str, str]]
	description: str = ''

	def __post_init__(self) -> None:
		self.strategies = [(str(kind), str(value)) for kind, value in self.strategies]


def _role_value(role: str | None, name: str | None) -> str:
	"""Encode role + accessible name into one strategy value, ``'role|name'``."""
	if not role:
		return f'|{name}' if name else ''
	return f'{role}|{name}' if name else role


def _split_role(value: str) -> tuple[str, str]:
	role, sep, name = value.partition('|')
	return role, name if sep else ''


def selector(
	css: str | None = None,
	xpath: str | None = None,
	role: str | None = None,
	name: str | None = None,
	text: str | None = None,
	axid: str | int | None = None,
	*,
	description: str = '',
) -> Selector:
	"""Build a Selector with strategies in a sensible priority order.

	``css -> xpath -> axid -> role(+name) -> text``. Role and accessible name are combined into one
	``('role', 'role|name')`` strategy; ``name`` alone matches any role with that name.
	"""
	given: dict[str, str] = {}
	if css:
		given['css'] = css
	if xpath:
		given['xpath'] = xpath
	if axid is not None and str(axid) != '':
		given['axid'] = str(axid)
	if role or name:
		given['role'] = _role_value(role, name)
	if text:
		given['text'] = text
	return Selector([(kind, given[kind]) for kind in _PRIORITY if kind in given], description=description)


def _get_helpers(helpers: Any | None) -> Any:
	if helpers is not None:
		return helpers
	from browser_harness import helpers as bh  # lazy: importing this module needs no browser

	return bh


def _call(h: Any, method: str, timeout_ms: int, **params: Any) -> dict:
	"""One CDP call, bounded by ``timeout_ms`` (browser-harness takes seconds via ``_response_timeout``)."""
	return h.cdp(method, _response_timeout=max(0.001, timeout_ms / 1000), **params)


def _error(exc: BaseException) -> str:
	return f'{type(exc).__name__}: {exc}'[:300]


def _norm(value: Any) -> str:
	return _WS.sub(' ', str(value or '')).strip().lower()


def _ax_val(value: Any) -> str:
	return str(value.get('value') or '') if isinstance(value, dict) else str(value or '')


def _backend_of(h: Any, node_id: Any, timeout_ms: int) -> int | None:
	described = _call(h, 'DOM.describeNode', timeout_ms, nodeId=node_id)
	return (described.get('node') or {}).get('backendNodeId')


def _resolve_css(h: Any, value: str, timeout_ms: int) -> int | None:
	root = _call(h, 'DOM.getDocument', timeout_ms, depth=0).get('root') or {}
	node_id = _call(h, 'DOM.querySelector', timeout_ms, nodeId=root.get('nodeId'), selector=value).get('nodeId')
	if not node_id:
		ids = _call(h, 'DOM.querySelectorAll', timeout_ms, nodeId=root.get('nodeId'), selector=value).get('nodeIds') or []
		node_id = ids[0] if ids else None
	if not node_id:
		raise LookupError('CSS selector matched no node')
	return _backend_of(h, node_id, timeout_ms)


def _search(h: Any, query: str, timeout_ms: int) -> int | None:
	found = _call(h, 'DOM.performSearch', timeout_ms, query=query, includeStyleProperties=False)
	search_id = found.get('searchId')
	if not search_id or not found.get('resultCount'):
		raise LookupError('search matched no node')
	try:
		ids = _call(h, 'DOM.getSearchResults', timeout_ms, searchId=search_id, fromIndex=0, toIndex=1).get('nodeIds') or []
		if not ids:
			raise LookupError('search returned no node id')
		return _backend_of(h, ids[0], timeout_ms)
	finally:
		try:
			_call(h, 'DOM.discardSearchResults', timeout_ms, searchId=search_id)
		except Exception:
			pass


def _resolve_xpath(h: Any, value: str, timeout_ms: int) -> int | None:
	return _search(h, value, timeout_ms)


def _resolve_text(h: Any, value: str, timeout_ms: int) -> int | None:
	return _search(h, f'//*[contains(text(), {json.dumps(value)})]', timeout_ms)


def _resolve_role(h: Any, value: str, timeout_ms: int) -> int | None:
	want_role, want_name = _split_role(value)
	nodes = _call(h, 'Accessibility.getFullAXTree', timeout_ms).get('nodes') or []
	for node in nodes:
		if node.get('ignored'):
			continue
		role, name = _ax_val(node.get('role')), _ax_val(node.get('name'))
		if want_role and _norm(role) != _norm(want_role):
			continue
		if want_name and _norm(name) != _norm(want_name):
			continue
		backend = node.get('backendDOMNodeId')
		if backend is not None:
			return backend
	raise LookupError('no matching accessible node')


def _resolve_axid(h: Any, value: str, timeout_ms: int) -> int | None:
	try:
		backend = int(value)
	except (TypeError, ValueError):
		raise LookupError('invalid backend node id') from None
	nodes = _call(h, 'Accessibility.getPartialAXTree', timeout_ms, backendNodeId=backend).get('nodes') or []
	if any(node.get('backendDOMNodeId') == backend for node in nodes):
		return backend
	raise LookupError('backend node id is stale')


_RESOLVERS: dict[str, Callable[[Any, str, int], int | None]] = {
	'css': _resolve_css,
	'xpath': _resolve_xpath,
	'text': _resolve_text,
	'role': _resolve_role,
	'axid': _resolve_axid,
}


def resolve(sel: Selector, *, helpers: Any = None, timeout_ms: int = 2000) -> dict:
	"""Try each strategy in order; return the first node found, or a structured failure."""
	h = _get_helpers(helpers)
	tried: list[dict[str, str]] = []
	for kind, value in sel.strategies:
		if kind not in _RESOLVERS:
			tried.append({'strategy': kind, 'value': value, 'error': f'unsupported strategy {kind!r}'})
			continue
		try:
			backend = _RESOLVERS[kind](h, value, timeout_ms)
		except Exception as exc:
			tried.append({'strategy': kind, 'value': value, 'error': _error(exc)})
			continue
		return {'ok': True, 'strategy': kind, 'value': value, 'backend_node_id': backend}
	return {'ok': False, 'tried': tried, 'error': tried[-1]['error'] if tried else 'no strategies to try'}


def click(sel: Selector, *, helpers: Any = None, timeout_ms: int = 2000) -> dict:
	"""Resolve, then click the node's center with real mouse events. Never acts on a failed resolve."""
	found = resolve(sel, helpers=helpers, timeout_ms=timeout_ms)
	out = {**found, 'action': 'click', 'performed': False}
	if not found['ok']:
		return out
	try:
		h = _get_helpers(helpers)
		backend = found['backend_node_id']
		if backend is None:
			raise LookupError('resolution returned no backend node id')
		_call(h, 'DOM.scrollIntoViewIfNeeded', timeout_ms, backendNodeId=backend)
		quad = (_call(h, 'DOM.getBoxModel', timeout_ms, backendNodeId=backend).get('model') or {}).get('content') or []
		if len(quad) < 8:
			raise LookupError('no box model for the node')
		x = sum(float(quad[i]) for i in (0, 2, 4, 6)) / 4
		y = sum(float(quad[i]) for i in (1, 3, 5, 7)) / 4
		_call(h, 'Input.dispatchMouseEvent', timeout_ms, type='mousePressed', x=x, y=y, button='left', clickCount=1)
		_call(h, 'Input.dispatchMouseEvent', timeout_ms, type='mouseReleased', x=x, y=y, button='left', clickCount=1)
	except Exception as exc:
		return {**out, 'error': _error(exc)}
	return {**out, 'performed': True}


def fill(sel: Selector, text: str, *, helpers: Any = None, timeout_ms: int = 2000) -> dict:
	"""Resolve, then focus the node and insert text. Never acts on a failed resolve."""
	found = resolve(sel, helpers=helpers, timeout_ms=timeout_ms)
	out = {**found, 'action': 'fill', 'performed': False}
	if not found['ok']:
		return out
	try:
		h = _get_helpers(helpers)
		backend = found['backend_node_id']
		if backend is None:
			raise LookupError('resolution returned no backend node id')
		_call(h, 'DOM.scrollIntoViewIfNeeded', timeout_ms, backendNodeId=backend)
		_call(h, 'DOM.focus', timeout_ms, backendNodeId=backend)
		_call(h, 'Input.insertText', timeout_ms, text=text)
	except Exception as exc:
		return {**out, 'error': _error(exc)}
	return {**out, 'performed': True}


def record(sel: Selector, page_info: dict, *, resolution: dict | None = None) -> dict:
	"""A JSON-serializable record for reports/replay: strategies, where it resolved, page context."""
	return {
		'description': sel.description,
		'strategies': [{'kind': kind, 'value': value} for kind, value in sel.strategies],
		'where': resolution if resolution is not None else page_info.get('resolution'),
		'page': {'url': page_info.get('url', ''), 'title': page_info.get('title', '')},
	}


def install() -> None:
	"""Expose self-healing selectors in REPL cells, like the handoff and human helpers."""
	from browser_harness import helpers

	for name in ('selector', 'resolve', 'click', 'fill', 'record'):
		setattr(helpers, name, globals()[name])
