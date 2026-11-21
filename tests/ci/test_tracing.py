"""Local run tracing: JSONL persistence, redaction, timeline HTML, OTLP/JSON payload and the REPL exec hook.

No provider, cloud or CDN is involved: the JSONL goes to a tmp_path config dir and all HTML is inline.
"""

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

import pytest

from browse_dev import tracing
from browse_dev.repl import Repl


@pytest.fixture
def trace_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	monkeypatch.setenv('BROWSE_DEV_CONFIG_DIR', str(tmp_path))
	monkeypatch.setenv('ANONYMIZED_TELEMETRY', 'true')  # these tests exercise local JSONL persistence
	monkeypatch.setattr(tracing, 'tracer', tracing.Tracer())
	return tmp_path


def test_trace_export_returns_spans_durations_and_totals(trace_env: Path) -> None:
	t = tracing.tracer
	tid = t.start_trace('run', service='unit')
	with t.span('step'):
		time.sleep(0.002)
	t.finish(tid)
	data = t.export(tid)
	assert data['trace_id'] == tid
	assert data['name'] == 'run'
	assert [s['name'] for s in data['spans']] == ['step']
	assert data['spans'][0]['end_ns'] >= data['spans'][0]['start_ns']
	assert data['spans'][0]['duration_ms'] >= 1
	assert data['totals']['spans'] == 1
	assert data['totals']['errors'] == 0
	assert data['totals']['duration_ms'] >= 1
	# export(None) falls back to the last trace
	assert t.export()['trace_id'] == tid
	# the span was persisted as JSONL
	lines = (trace_env / 'traces.jsonl').read_text(encoding='utf-8').splitlines()
	assert len(lines) == 1
	assert json.loads(lines[0])['name'] == 'step'


def test_trace_nested_spans_have_parent_id(trace_env: Path) -> None:
	t = tracing.tracer
	tid = t.start_trace('nested')
	with t.span('parent', trace_id=tid) as parent:
		with t.span('child') as child:
			pass
	with t.span('explicit', trace_id=tid, parent_id=parent.span_id):
		pass
	spans = {s['name']: s for s in t.export(tid)['spans']}
	assert spans['parent']['parent_id'] is None
	assert spans['child']['parent_id'] == parent.span_id == child.parent_id
	assert spans['explicit']['parent_id'] == parent.span_id


def test_trace_secret_attributes_redacted_in_jsonl_and_export(trace_env: Path) -> None:
	t = tracing.tracer
	tid = t.start_trace('redact', API_TOKEN='SENTINEL_TOP_SECRET')
	with t.span('step', trace_id=tid, password='SENTINEL_PASSWORD', api_key='SENTINEL_KEY', url='https://example.test'):
		pass
	t.finish(tid)
	data = t.export(tid)
	attrs = data['spans'][0]['attributes']
	assert attrs['password'] == '[redacted]'
	assert attrs['api_key'] == '[redacted]'
	assert attrs['url'] == 'https://example.test'
	raw = (trace_env / 'traces.jsonl').read_text(encoding='utf-8')
	for sentinel in ('SENTINEL_TOP_SECRET', 'SENTINEL_PASSWORD', 'SENTINEL_KEY'):
		assert sentinel not in raw
	assert raw.count('[redacted]') == 2
	assert json.loads(raw)['attributes'] == attrs


def test_trace_error_status_and_duration_on_exception(trace_env: Path) -> None:
	t = tracing.tracer
	tid = t.start_trace('boom')
	with pytest.raises(ValueError, match='nope'):
		with t.span('fails', trace_id=tid):
			raise ValueError('nope')
	data = t.export(tid)
	assert data['spans'][0]['status'] == 'error'
	assert data['totals']['errors'] == 1


def test_trace_write_timeline_html_escaped_and_summary(trace_env: Path) -> None:
	t = tracing.tracer
	tid = t.start_trace('<run & "name">')
	with t.span('<step>', trace_id=tid, url='https://x.test/?a=1&b=2'):
		pass
	with t.span('failed', trace_id=tid) as s:
		s.status = 'error'
	t.finish(tid)
	out = trace_env / 'timeline.html'
	assert t.write_timeline(tid, out) == out
	doc = out.read_text(encoding='utf-8')
	assert doc.lower().startswith('<!doctype html>')
	assert '&lt;run &amp; &quot;name&quot;&gt;' in doc
	assert '&lt;step&gt;' in doc
	assert 'a=1&amp;b=2' in doc
	assert 'Spans: 2' in doc
	assert 'Errors: 1' in doc
	assert 'class="bar error"' in doc
	assert '<script' not in doc.lower()
	assert '<link' not in doc.lower()


def test_trace_export_otlp_json_shape(trace_env: Path) -> None:
	t = tracing.tracer
	tid = t.start_trace('otlp')
	with t.span('parent', trace_id=tid) as parent:
		with t.span('child'):
			pass
	t.finish(tid)
	payload = t.export_otlp_json(tid)
	rss = payload['resourceSpans']
	assert len(rss) == 1
	scopes = rss[0]['scopeSpans']
	assert len(scopes) == 1
	spans = scopes[0]['spans']
	assert len(spans) == 2
	for s in spans:
		assert re.fullmatch(r'[0-9a-f]{32}', s['traceId'])
		assert re.fullmatch(r'[0-9a-f]{16}', s['spanId'])
		assert int(s['startTimeUnixNano']) > 0
		assert int(s['endTimeUnixNano']) >= int(s['startTimeUnixNano'])
		assert s['status']['code'] in (1, 2)
	assert spans[1]['parentSpanId'] == parent.span_id
	assert rss[0]['resource']['attributes'][0]['value']['stringValue'] == 'browse-dev'
	json.dumps(payload)  # the payload is JSON-serializable as-is


def test_trace_repl_call_hook_records_exec_span(monkeypatch: pytest.MonkeyPatch) -> None:
	class FakeSpan:
		def __init__(self, name: str, attributes: dict[str, Any]):
			self.name, self.attributes, self.status = name, attributes, 'ok'

		def __enter__(self) -> 'FakeSpan':
			return self

		def __exit__(self, *exc: object) -> bool:
			return False

	class FakeTracer:
		def __init__(self) -> None:
			self.recorded: list[tuple[FakeSpan, dict[str, Any]]] = []

		def span(self, name: str, **kw: Any) -> FakeSpan:
			sp = FakeSpan(name, {k: v for k, v in kw.items() if k not in ('trace_id', 'parent_id')})
			self.recorded.append((sp, kw))
			return sp

	fake = FakeTracer()
	monkeypatch.setattr(tracing, 'tracer', fake)
	repl = object.__new__(Repl)
	repl._lock_loop = None
	repl.reattach = None
	repl.after_cell = None
	repl.secrets = []

	async def fake_call(op: str, code: str, timeout: float) -> dict[str, Any]:
		if op != 'exec':
			return {'value': 'ok'}
		return {'output': 'fine', 'error': ''} if code == 'good' else {'error': 'boom', 'error_type': 'ValueError'}

	repl._call = fake_call  # type: ignore[method-assign]

	result = asyncio.run(repl.call('exec', 'good', 1.0))
	assert result['output'] == 'fine'
	assert len(fake.recorded) == 1
	sp, kw = fake.recorded[0]
	assert sp.name == 'repl.exec'
	assert sp.attributes == {'op': 'exec', 'code_length': 4}
	assert kw.get('trace_id') is None

	assert asyncio.run(repl.call('exec', 'bad', 1.0))['error'] == 'boom'
	assert fake.recorded[1][0].status == 'error'

	asyncio.run(repl.call('other', 'x', 1.0))
	assert len(fake.recorded) == 2  # no span for non-exec ops
