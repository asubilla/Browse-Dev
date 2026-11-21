"""Local, self-hosted run tracing (OpenTelemetry-style, standard library only).

A ``Tracer`` keeps spans in memory and appends each completed span as one JSON line to
``CONFIG.BROWSE_DEV_CONFIG_DIR / 'traces.jsonl'``. Nothing is sent over the network and there are no
third-party dependencies. ``write_timeline`` renders a standalone HTML timeline and ``export_otlp_json``
builds an OTLP/JSON payload that any collector can ingest.

Attribute keys containing key/token/password/secret are redacted on ingestion, so the in-memory
buffer, the JSONL file, the timeline and the OTLP payload all carry ``'[redacted]'`` instead.
Tracing is best-effort: a failure to write the JSONL file never breaks the run being traced.
"""

from __future__ import annotations

import contextvars
import html
import json
import re
import secrets
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from browse_dev.config import CONFIG

REDACTED = '[redacted]'
_SECRET_KEY = re.compile(r'key|token|password|secret', re.I)
_TRACES_FILE = 'traces.jsonl'
_OTLP_SERVICE_NAME = 'browse-dev'
_OTLP_SCOPE_NAME = 'browse_dev.tracing'
_OTLP_STATUS = {'ok': 1, 'error': 2}  # OTLP STATUS_CODE_OK / STATUS_CODE_ERROR (0 = UNSET)


def _jsonable(value: Any) -> Any:
	"""Keep attributes serializable even when a caller passes a Path, a tuple or an ad-hoc object."""
	if value is None or isinstance(value, (str, int, float, bool)):
		return value
	if isinstance(value, (list, tuple, set)):
		return [_jsonable(v) for v in value]
	if isinstance(value, Mapping):
		return {str(k): _jsonable(v) for k, v in value.items()}
	if isinstance(value, Path):
		return str(value)
	return str(value)


def redact_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
	"""Copy attributes, replacing obvious secret values and normalizing every value to json.dumps-able data."""
	return {
		str(k): (REDACTED if _SECRET_KEY.search(str(k)) else _jsonable(v))
		for k, v in (attributes or {}).items()
	}


@dataclass
class TraceSpan:
	"""One timed operation. ``start_ns``/``end_ns`` are ``time.time_ns()`` values (wall clock, Unix epoch)."""

	trace_id: str
	span_id: str
	parent_id: str | None = None
	name: str = ''
	start_ns: int = 0
	end_ns: int | None = None
	status: str = 'ok'  # 'ok' | 'error'
	attributes: dict[str, Any] = field(default_factory=dict)

	@property
	def duration_ms(self) -> float:
		return 0.0 if self.end_ns is None else (self.end_ns - self.start_ns) / 1_000_000

	def to_dict(self) -> dict[str, Any]:
		"""JSON-serializable view (attributes are redacted at ingestion, redacted again defensively here)."""
		return {
			'trace_id': self.trace_id,
			'span_id': self.span_id,
			'parent_id': self.parent_id,
			'name': self.name,
			'start_ns': self.start_ns,
			'end_ns': self.end_ns,
			'duration_ms': self.duration_ms,
			'status': self.status,
			'attributes': redact_attributes(self.attributes),
		}


class Tracer:
	"""Records spans in memory and persists them as JSONL. Sync methods are safe to call from an async loop:
	a span is a plain object and contextvars keep nesting (and the implicit trace) local to each task."""

	def __init__(self) -> None:
		self._traces: dict[str, dict[str, Any]] = {}
		self._spans: dict[str, list[TraceSpan]] = {}
		self._written: set[str] = set()
		self._last_trace_id: str | None = None
		self._current_trace: contextvars.ContextVar[str | None] = contextvars.ContextVar('browse_dev_trace', default=None)
		self._current_span: contextvars.ContextVar[str | None] = contextvars.ContextVar('browse_dev_span', default=None)

	def start_trace(self, name: str, **attributes: Any) -> str:
		"""Open a run and return its trace_id. It becomes the implicit parent trace for later ``span()`` calls."""
		trace_id = secrets.token_hex(16)
		self._traces[trace_id] = {
			'name': name,
			'attributes': redact_attributes(attributes),
			'start_ns': time.time_ns(),
			'finished': False,
		}
		self._spans[trace_id] = []
		self._last_trace_id = trace_id
		self._current_trace.set(trace_id)
		self._current_span.set(None)
		return trace_id

	def finish(self, trace_id: str) -> None:
		"""Mark a run done and flush any spans that were still buffered."""
		record = self._traces.get(trace_id)
		if record is not None:
			record['finished'] = True
			record['end_ns'] = time.time_ns()
		self.flush(trace_id)

	@contextmanager
	def span(
		self,
		name: str,
		*,
		trace_id: str | None = None,
		parent_id: str | None = None,
		**attributes: Any,
	) -> Iterator[TraceSpan]:
		"""Time an operation. Yields the ``TraceSpan`` so a caller can set ``status = 'error'`` before exit.

		An omitted ``trace_id`` uses the active trace (or opens a default one); an omitted ``parent_id`` uses the
		innermost active span, so plain nested ``with`` blocks form a parent/child chain. An exception sets error.
		"""
		tid = trace_id or self._current_trace.get()
		if tid is None:
			tid = self.start_trace(name)
		pid = parent_id if parent_id is not None else self._current_span.get()
		span = TraceSpan(
			trace_id=tid,
			span_id=secrets.token_hex(8),
			parent_id=pid,
			name=name,
			start_ns=time.time_ns(),
			attributes=redact_attributes(attributes),
		)
		self._spans.setdefault(tid, []).append(span)  # buffered immediately: export works before the span ends/flushes
		token_trace = self._current_trace.set(tid)
		token_span = self._current_span.set(span.span_id)
		try:
			yield span
		except BaseException:
			span.status = 'error'
			span.end_ns = time.time_ns()
			self._persist(span)
			raise
		else:
			span.end_ns = span.end_ns or time.time_ns()
			self._persist(span)
		finally:
			self._current_span.reset(token_span)
			self._current_trace.reset(token_trace)

	def _resolve_trace(self, trace_id: str | None) -> str | None:
		if trace_id is not None:
			return trace_id
		return self._current_trace.get() or self._last_trace_id

	def export(self, trace_id: str | None = None) -> dict[str, Any]:
		"""JSON-serializable run summary: ``{trace_id, name, spans: [...], totals: {...}}``.

		``totals`` has both short (``spans``, ``duration_ms``, ``errors``) and explicit
		(``total_spans``, ``total_duration_ms``, ``error_count``) names so callers can use either.
		"""
		tid = self._resolve_trace(trace_id)
		record = self._traces.get(tid or '', {})
		spans = [s.to_dict() for s in self._spans.get(tid, [])]
		duration = round(sum(s['duration_ms'] for s in spans), 3)
		errors = sum(1 for s in spans if s['status'] == 'error')
		return {
			'trace_id': tid,
			'name': record.get('name', ''),
			'spans': spans,
			'totals': {
				'spans': len(spans),
				'total_spans': len(spans),
				'duration_ms': duration,
				'total_duration_ms': duration,
				'errors': errors,
				'error_count': errors,
			},
		}

	def _persist(self, span: TraceSpan, path: Path | None = None) -> bool:
		if span.span_id in self._written:
			return False
		import os

		if os.environ.get('ANONYMIZED_TELEMETRY', 'true').strip().lower()[:1] in ('f', 'n', '0'):
			return True  # privacy: opting out of telemetry keeps traces in memory only, no file
		try:
			path = path or CONFIG.BROWSE_DEV_CONFIG_DIR / _TRACES_FILE
			with path.open('a', encoding='utf-8') as f:
				f.write(json.dumps(span.to_dict(), default=str) + '\n')
		except OSError:
			return False  # never break the run because tracing could not write
		self._written.add(span.span_id)
		return True

	def flush(self, trace_id: str | None = None) -> Path | None:
		"""Append any spans not yet on disk; returns the JSONL path when something was written."""
		ids = [trace_id] if trace_id is not None else list(self._spans)
		path = CONFIG.BROWSE_DEV_CONFIG_DIR / _TRACES_FILE
		wrote = False
		for tid in ids:
			for span in self._spans.get(tid, []):
				wrote = self._persist(span, path) or wrote
		return path if wrote else None

	def write_timeline(self, trace_id: str, path: str | Path) -> Path:
		"""Write a self-contained HTML timeline (inline CSS, no scripts/CDN); return the file path."""
		data = self.export(trace_id)
		spans = data['spans']
		starts = [s['start_ns'] for s in spans]
		ends = [s['end_ns'] or s['start_ns'] for s in spans]
		t0 = min(starts, default=0)
		t1 = max(ends, default=t0)
		span_ns = max(t1 - t0, 1)
		rows: list[str] = []
		for s in spans:
			end = s['end_ns'] or s['start_ns']
			left = max((s['start_ns'] - t0) / span_ns * 100, 0.0)
			width = max((end - s['start_ns']) / span_ns * 100, 0.5)
			attrs = html.escape(json.dumps(s['attributes'], sort_keys=True, default=str))
			rows.append(
				'<div class="row">'
				f'<div class="label">{html.escape(s["name"])}</div>'
				'<div class="track">'
				f'<div class="bar {html.escape(s["status"])}" style="left:{left:.2f}%;width:{width:.2f}%">'
				f'{html.escape(str(s["duration_ms"]))} ms</div>'
				'</div>'
				f'<div class="meta">{html.escape(s["status"])} · {attrs}</div>'
				'</div>'
			)
		totals = data['totals']
		summary = (
			f'Spans: {totals["spans"]} · Duration: {html.escape(str(totals["duration_ms"]))} ms · '
			f'Errors: {totals["errors"]}'
		)
		title = html.escape(f'{data["name"] or "run"} — {data["trace_id"] or ""}')
		body = '\n'.join(rows) or '<p class="empty">No spans recorded.</p>'
		doc = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body{{font:14px/1.5 system-ui,sans-serif;margin:2rem;color:#222;background:#fff}}
h1{{font-size:1.2rem}} .summary{{color:#555}}
.row{{display:grid;grid-template-columns:12rem 1fr;gap:.25rem 1rem;margin:.5rem 0}}
.label{{overflow-wrap:anywhere;font-weight:600}} .track{{position:relative;height:1.4rem;background:#f0f0f0}}
.bar{{position:absolute;top:0;bottom:0;background:#2d7ff9;color:#fff;font-size:.75rem;padding:0 .3rem;overflow:hidden;white-space:nowrap}}
.bar.error{{background:#c62828}} .meta{{grid-column:2;color:#666;font-size:.75rem;overflow-wrap:anywhere}}
.empty{{color:#888}}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="summary">{summary}</p>
{body}
</body>
</html>
'''
		out = Path(path)
		out.parent.mkdir(parents=True, exist_ok=True)
		out.write_text(doc, encoding='utf-8')
		return out

	def export_otlp_json(self, trace_id: str) -> dict[str, Any]:
		"""OTLP/JSON-shaped payload (hex ids, UnixNano times); no exporter dependency, no network call."""
		data = self.export(trace_id)
		spans: list[dict[str, Any]] = []
		for s in data['spans']:
			attrs = [
				{'key': k, 'value': _otlp_value(v)}
				for k, v in s['attributes'].items()
			]
			spans.append(
				{
					'traceId': s['trace_id'],
					'spanId': s['span_id'],
					**({'parentSpanId': s['parent_id']} if s['parent_id'] else {}),
					'name': s['name'],
					'kind': 1,  # SPAN_KIND_INTERNAL
					'startTimeUnixNano': str(s['start_ns']),
					'endTimeUnixNano': str(s['end_ns'] or s['start_ns']),
					'status': {'code': _OTLP_STATUS.get(s['status'], 0)},
					'attributes': attrs,
				}
			)
		return {
			'resourceSpans': [
				{
					'resource': {
						'attributes': [{'key': 'service.name', 'value': {'stringValue': _OTLP_SERVICE_NAME}}]
					},
					'scopeSpans': [{'scope': {'name': _OTLP_SCOPE_NAME}, 'spans': spans}],
				}
			]
		}


def _otlp_value(value: Any) -> dict[str, Any]:
	if isinstance(value, bool):
		return {'boolValue': value}
	if isinstance(value, int):
		return {'intValue': str(value)}  # OTLP JSON encodes int64 as a decimal string
	if isinstance(value, float):
		return {'doubleValue': value}
	if isinstance(value, list):
		return {'arrayValue': {'values': [_otlp_value(v) for v in value]}}
	return {'stringValue': str(value)}


# Module-level instance used by the REPL hook and the CLI; wrappers delegate to it so monkeypatching `tracer`
# (e.g. in tests) is enough to observe or replace all tracing calls.
tracer = Tracer()


def start_trace(name: str, **attributes: Any) -> str:
	return tracer.start_trace(name, **attributes)


def finish(trace_id: str) -> None:
	tracer.finish(trace_id)


@contextmanager
def span(name: str, *, trace_id: str | None = None, parent_id: str | None = None, **attributes: Any) -> Iterator[TraceSpan]:
	with tracer.span(name, trace_id=trace_id, parent_id=parent_id, **attributes) as s:
		yield s


def export(trace_id: str | None = None) -> dict[str, Any]:
	return tracer.export(trace_id)


def flush(trace_id: str | None = None) -> Path | None:
	return tracer.flush(trace_id)


def write_timeline(trace_id: str, path: str | Path) -> Path:
	return tracer.write_timeline(trace_id, path)


def export_otlp_json(trace_id: str) -> dict[str, Any]:
	return tracer.export_otlp_json(trace_id)
