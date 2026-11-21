"""Free human handoff: pause while a person handles login, 2FA, a captcha or a payment.

`handoff("Please log in to ...")` shows a small fixed-position card in the currently attached tab with the
message and a Continue / Cancel button. The agent's cell blocks while the human acts in that same real browser;
it never reads or solves a challenge and never types into a password, OTP or captcha field. When the human clicks
a button, the overlay is removed and a short `{'outcome': ..., 'note': ...}` is returned so the cell can carry on.

No network, account or extra service: the card is inline CSS/JS injected with CDP into a page the agent already
controls. CDP/page failures become a one-line 'closed' outcome, never a raw traceback shown to the model.
"""

from __future__ import annotations

import json
import time
from typing import Any

_MARKER = 'data-browse-dev-handoff'
_GLOBAL = 'window.__browseDevHandoff'
_POLL_SECONDS = 0.25

# Sentinel comments let tests tell the three injected snippets apart without a real browser.
_POLL_JS = """/* browse-dev-handoff:poll */
(() => {
  const s = window.__browseDevHandoff;
  if (!s) return null;
  return {outcome: s.outcome, note: s.note == null ? null : s.note};
})()"""

_CLEANUP_JS = """/* browse-dev-handoff:cleanup */
(() => {
  document.querySelectorAll('[data-browse-dev-handoff]').forEach(el => el.remove());
  delete window.__browseDevHandoff;
  return true;
})()"""


def _inject_js(message: str) -> str:
	"""JS that mounts the card. The message is a JSON string literal shown via textContent (no HTML, no XSS)."""
	return f"""/* browse-dev-handoff:inject */
(() => {{
  const previous = document.querySelector('[{_MARKER}]');
  if (previous) previous.remove();
  const card = document.createElement('div');
  card.setAttribute('{_MARKER}', '1');
  card.style.cssText = (
    'position:fixed;top:24px;right:24px;z-index:2147483647;max-width:360px;'
    'background:#fff;color:#111;border:2px solid #2563eb;border-radius:12px;'
    'box-shadow:0 10px 30px rgba(0,0,0,.3);padding:18px 20px;'
    'font:14px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif'
  );
  const title = document.createElement('div');
  title.textContent = 'Human handoff';
  title.style.cssText = 'font-weight:700;color:#2563eb;margin-bottom:8px;font-size:15px';
  const body = document.createElement('div');
  body.textContent = {json.dumps(message)};
  body.style.cssText = 'white-space:pre-wrap;margin-bottom:12px';
  const note = document.createElement('input');
  note.type = 'text';
  note.placeholder = 'Optional note';
  note.setAttribute('aria-label', 'Optional note');
  note.style.cssText = 'width:100%;box-sizing:border-box;padding:6px 8px;margin-bottom:12px;border:1px solid #ccc;border-radius:6px';
  const row = document.createElement('div');
  row.style.cssText = 'display:flex;gap:8px;justify-content:flex-end';
  const make = (label, outcome, bg) => {{
    const b = document.createElement('button');
    b.textContent = label;
    b.style.cssText = 'cursor:pointer;border:0;border-radius:6px;padding:8px 14px;font-weight:600;color:#fff;background:' + bg;
    b.onclick = () => {{
      const value = note.value.trim();
      {_GLOBAL} = {{outcome: outcome}};
      if (value) {_GLOBAL}.note = value;
    }};
    return b;
  }};
  row.appendChild(make('Cancel', 'cancelled', '#6b7280'));
  row.appendChild(make('Continue', 'continued', '#2563eb'));
  card.appendChild(title);
  card.appendChild(body);
  card.appendChild(note);
  card.appendChild(row);
  document.body.appendChild(card);
  return true;
}})()"""


def _short(e: BaseException) -> str:
	"""One short line for the model: no traceback, no page contents."""
	text = ' '.join(str(e).split())
	return (text or type(e).__name__)[:200]


def handoff(message: str, timeout_seconds: float = 600) -> dict[str, Any]:
	"""Ask the human to act in the browser, then wait. Returns {'outcome', 'note'}.

	outcome is 'continued' or 'cancelled' when a button was clicked, 'timeout' when no one clicked in time, or
	'closed' when the page vanished (navigation, closed tab). The overlay and the window global are always removed.
	"""
	from browser_harness import helpers

	outcome, note = 'closed', None
	try:
		try:
			helpers.cdp('Runtime.evaluate', expression=_inject_js(message), returnByValue=True)
		except Exception as e:
			return {'outcome': 'closed', 'note': f'could not show handoff card: {_short(e)}'}
		try:
			limit = max(0.0, float(timeout_seconds))
		except (TypeError, ValueError):
			limit = 600.0
		deadline = time.monotonic() + limit
		while time.monotonic() < deadline:
			try:
				state = helpers.js(_POLL_JS)
			except Exception as e:
				return {'outcome': 'closed', 'note': f'handoff lost the page: {_short(e)}'}
			if isinstance(state, dict) and state.get('outcome') in ('continued', 'cancelled'):
				outcome = str(state['outcome'])
				raw = state.get('note')
				note = str(raw) if raw else None
				break
			time.sleep(_POLL_SECONDS)
		else:
			outcome = 'timeout'
			note = f'no Continue or Cancel within {limit:g} seconds'
		return {'outcome': outcome, 'note': note}
	finally:
		try:
			helpers.js(_CLEANUP_JS)
		except Exception:
			pass  # cleanup is best-effort; a page that is gone cannot hold a card anyway


def handoff_cancel() -> dict[str, Any]:
	"""Remove any active handoff overlay immediately, e.g. from another cell. Returns the same shape as handoff()."""
	from browser_harness import helpers

	try:
		helpers.js(_CLEANUP_JS)
		return {'outcome': 'cancelled', 'note': None}
	except Exception as e:
		return {'outcome': 'closed', 'note': f'could not cancel handoff: {_short(e)}'}


def install() -> None:
	"""Make handoff() / handoff_cancel() available to REPL cells, like liveview's install()."""
	from browser_harness import helpers

	helpers.handoff = handoff
	helpers.handoff_cancel = handoff_cancel
