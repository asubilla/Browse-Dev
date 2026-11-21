"""Pure unit tests for browse_dev.selectors: fake CDP helpers, no real browser.

Test names all contain 'selector' so conftest.py's REMOVED_CLOUD_TESTS skip list does not catch them.
"""

import json

from browse_dev.selectors import Selector, click, fill, record, resolve, selector


class FakeHelpers:
	"""Tiny stand-in for browser_harness.helpers: canned CDP replies, records every method called.

	``replies`` maps a method name to a dict to return, an Exception to raise, or a callable of the
	CDP params. Anything not mapped gets a harmless default so a strategy fails instead of crashing.
	"""

	def __init__(self, replies: dict | None = None):
		self.replies = replies or {}
		self.calls: list[str] = []

	def cdp(self, method, **params):
		self.calls.append(method)
		reply = self.replies.get(method)
		if isinstance(reply, Exception):
			raise reply
		if callable(reply):
			return reply(**params)
		if reply is not None:
			return reply
		if method == 'DOM.getDocument':
			return {'root': {'nodeId': 1}}
		if method == 'DOM.describeNode':
			return {'node': {'backendNodeId': 4242}}
		return {}


def test_selector_resolve_uses_first_strategy_and_never_calls_the_second():
	h = FakeHelpers({'DOM.querySelector': {'nodeId': 7}, 'DOM.describeNode': {'node': {'backendNodeId': 99}}})
	r = resolve(Selector([('css', '#submit'), ('text', 'Submit')]), helpers=h)
	assert r == {'ok': True, 'strategy': 'css', 'value': '#submit', 'backend_node_id': 99}
	assert 'DOM.performSearch' not in h.calls  # the text strategy was never reached


def test_selector_resolve_falls_back_when_primary_raises():
	h = FakeHelpers(
		{
			'DOM.querySelector': RuntimeError('no such selector'),
			'DOM.performSearch': {'searchId': 's1', 'resultCount': 1},
			'DOM.getSearchResults': {'nodeIds': [12]},
			'DOM.describeNode': {'node': {'backendNodeId': 77}},
		}
	)
	r = resolve(Selector([('css', '.gone'), ('xpath', '//button')]), helpers=h)
	assert r['ok'] is True and r['strategy'] == 'xpath' and r['backend_node_id'] == 77
	assert 'DOM.querySelector' in h.calls and 'DOM.performSearch' in h.calls


def test_selector_resolve_all_strategies_fail_returns_structured_failure():
	h = FakeHelpers()  # querySelector finds nothing, performSearch finds nothing
	r = resolve(Selector([('css', '.missing'), ('xpath', '//missing')]), helpers=h)
	assert r['ok'] is False
	assert [entry['strategy'] for entry in r['tried']] == ['css', 'xpath']
	assert all('error' in entry for entry in r['tried'])
	assert isinstance(r['error'], str) and r['error']


def test_selector_click_does_not_act_when_resolution_fails():
	h = FakeHelpers({'DOM.querySelector': RuntimeError('nope')})
	r = click(Selector([('css', '.missing')]), helpers=h)
	assert r['ok'] is False and r['action'] == 'click' and r['performed'] is False
	assert 'Input.dispatchMouseEvent' not in h.calls and 'DOM.getBoxModel' not in h.calls


def test_selector_fill_does_not_act_when_resolution_fails():
	h = FakeHelpers({'DOM.querySelector': RuntimeError('nope')})
	r = fill(Selector([('css', '.missing')]), 'hello', helpers=h)
	assert r['ok'] is False and r['action'] == 'fill' and r['performed'] is False
	assert 'Input.insertText' not in h.calls and 'DOM.focus' not in h.calls


def test_selector_click_and_fill_act_after_a_successful_resolve():
	replies = {
		'DOM.querySelector': {'nodeId': 7},
		'DOM.getBoxModel': {'model': {'content': [10, 20, 20, 20, 20, 60, 10, 60]}},
	}
	sel = Selector([('css', '#name')])
	h = FakeHelpers(replies)
	c = click(sel, helpers=h)
	assert c['ok'] is True and c['action'] == 'click' and c['performed'] is True
	assert 'DOM.scrollIntoViewIfNeeded' in h.calls and h.calls.count('Input.dispatchMouseEvent') == 2

	h2 = FakeHelpers(replies)
	f = fill(sel, 'Ada', helpers=h2)
	assert f['ok'] is True and f['action'] == 'fill' and f['performed'] is True
	assert 'DOM.focus' in h2.calls and 'Input.insertText' in h2.calls


def test_selector_record_round_trips_through_json():
	sel = selector(css='#go', role='button', name='Go', description='submit button')
	resolution = {'ok': True, 'strategy': 'css', 'value': '#go', 'backend_node_id': 5}
	rec = record(sel, {'url': 'https://example.test', 'title': 'Example'}, resolution=resolution)
	assert json.loads(json.dumps(rec)) == rec
	assert rec['strategies'] and rec['where']['strategy'] == 'css'
	assert rec['page']['url'] == 'https://example.test' and rec['description'] == 'submit button'


def test_selector_constructor_orders_strategies_by_priority():
	sel = selector(css='#a', xpath='//a', role='button', name='Go', text='Go', axid=123)
	assert [kind for kind, _ in sel.strategies] == ['css', 'xpath', 'axid', 'role', 'text']
	assert ('role', 'button|Go') in sel.strategies
	assert ('axid', '123') in sel.strategies


def test_selector_role_strategy_matches_the_accessibility_tree():
	h = FakeHelpers(
		{
			'Accessibility.getFullAXTree': {
				'nodes': [{'role': {'value': 'button'}, 'name': {'value': 'Submit'}, 'backendDOMNodeId': 88}],
			}
		}
	)
	r = resolve(Selector([('role', 'button|submit')]), helpers=h)
	assert r['ok'] is True and r['backend_node_id'] == 88


def test_selector_axid_strategy_rejects_a_stale_node_id():
	h = FakeHelpers({'Accessibility.getPartialAXTree': {'nodes': []}})
	r = resolve(Selector([('axid', '999')]), helpers=h)
	assert r['ok'] is False and r['tried'][0]['strategy'] == 'axid'
