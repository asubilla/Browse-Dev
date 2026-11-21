"""Unit tests for the free human handoff: a fake helpers module, no browser and no network."""

from __future__ import annotations

import asyncio
import json
import sys
import types

import pytest

import browse_dev.handoff as handoff
from browse_dev.mcp.cli_mcp import CLIMCPServer


class FakeHelpers(types.ModuleType):
	"""Stands in for browser_harness.helpers: records injected JS and serves a scripted outcome."""

	def __init__(self):
		super().__init__('browser_harness.helpers')
		self.state: dict | None = None
		self.injected: list[str] = []
		self.cdp_calls: list[tuple[str, dict]] = []
		self.cleanups: list[str] = []
		self.polls = 0

	def cdp(self, method: str, **params):
		self.cdp_calls.append((method, params))
		expression = str(params.get('expression', ''))
		if 'browse-dev-handoff:inject' in expression:
			self.injected.append(expression)
		return {'result': {'result': {'type': 'boolean', 'value': True}}}

	def js(self, expression: str, *args, **kwargs):
		if 'browse-dev-handoff:cleanup' in expression:
			self.cleanups.append(expression)
			self.state = None  # the component removes the global too
			return True
		if 'browse-dev-handoff:poll' in expression:
			self.polls += 1
			return dict(self.state) if self.state else None
		return None


class FakeTime:
	def __init__(self):
		self.now = 0.0

	def monotonic(self) -> float:
		return self.now

	def sleep(self, seconds: float) -> None:
		self.now += seconds


@pytest.fixture
def fake(monkeypatch):
	helpers = FakeHelpers()
	package = types.ModuleType('browser_harness')
	package.helpers = helpers
	monkeypatch.setitem(sys.modules, 'browser_harness', package)
	monkeypatch.setattr(handoff, 'time', FakeTime())
	return helpers


def test_handoff_continue_returns_outcome_and_cleans_up(fake):
	fake.state = {'outcome': 'continued'}
	result = handoff.handoff('Please log in', timeout_seconds=10)
	assert result == {'outcome': 'continued', 'note': None}
	assert len(fake.injected) == 1
	assert 'data-browse-dev-handoff' in fake.injected[0]
	assert 'Please log in' in fake.injected[0]
	assert fake.polls == 1
	assert len(fake.cleanups) == 1
	# the agent only injects JS: it never dispatches keystrokes into a password/OTP field
	assert [method for method, _ in fake.cdp_calls] == ['Runtime.evaluate']


def test_handoff_timeout_returns_note_and_cleans_up(fake):
	fake.state = None
	result = handoff.handoff('waiting', timeout_seconds=1.0)
	assert result['outcome'] == 'timeout'
	assert '1 seconds' in result['note']
	assert fake.polls == 4  # 0, 0.25, 0.5, 0.75 then the deadline at 1.0
	assert len(fake.cleanups) == 1


def test_handoff_cancelled_returns_note_and_cleans_up(fake):
	fake.state = {'outcome': 'cancelled', 'note': 'not now'}
	result = handoff.handoff('?', timeout_seconds=5)
	assert result == {'outcome': 'cancelled', 'note': 'not now'}
	assert len(fake.cleanups) == 1


def test_handoff_page_error_is_closed_without_a_traceback(fake, monkeypatch):
	def boom(method, **params):
		raise RuntimeError('Target closed')

	monkeypatch.setattr(fake, 'cdp', boom)
	result = handoff.handoff('x')
	assert result == {'outcome': 'closed', 'note': 'could not show handoff card: Target closed'}
	assert len(fake.cleanups) == 1  # cleanup is always attempted, even on the error path


def test_handoff_cancel_removes_the_overlay(fake):
	fake.state = {'outcome': 'continued'}
	assert handoff.handoff_cancel() == {'outcome': 'cancelled', 'note': None}
	assert len(fake.cleanups) == 1
	assert fake.state is None


def test_handoff_install_registers_cell_helpers(fake):
	from browser_harness import helpers

	handoff.install()
	assert helpers.handoff is handoff.handoff
	assert helpers.handoff_cancel is handoff.handoff_cancel


def test_handoff_mcp_tool_definition_asks_the_human(monkeypatch):
	server = CLIMCPServer()
	tool = next(t for t in server._tool_definitions() if t.name == 'browser_handoff')
	description = tool.description.lower()
	assert all(word in description for word in ('login', '2fa', 'captcha', 'payment', 'never solve'))
	assert tool.input_schema['required'] == ['message']
	assert 'timeout_seconds' in tool.input_schema['properties']


def test_handoff_mcp_handler_returns_text_json(monkeypatch):
	server = CLIMCPServer()
	monkeypatch.setattr(server, '_handoff', lambda message, timeout: {'outcome': 'continued', 'note': 'done'})
	result = asyncio.run(server._call_tool('browser_handoff', {'message': 'do it', 'timeout_seconds': 30}))
	assert not result.is_error
	assert json.loads(result.content[0].text) == {'outcome': 'continued', 'note': 'done'}
