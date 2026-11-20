"""Free local live view: CDP screencast frames served as an MJPEG stream on 127.0.0.1.

No cloud browser, account or extra service: `start_live_view()` in a cell starts `Page.startScreencast` on the attached
tab and an HTTP server on localhost; open http://127.0.0.1:8765/ in any browser to watch. `stop_live_view()` cleans up.

Only the latest frame is kept, so a slow viewer never grows memory. The stream is a local diagnostic view of a page
the agent already controls; it is not a recording or a remote-access service.
"""

from __future__ import annotations

import base64
import io
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BOUNDARY = 'frame'
PAGE = b"""<!doctype html><html><head><title>Browse Dev live view</title>
<style>body{margin:0;background:#111;display:grid;place-items:center;height:100vh}img{max-width:100%;max-height:100vh}</style>
</head><body><img src="/stream" alt="live screencast"></body></html>"""


class LiveView:
	"""A tiny MJPEG endpoint fed by screencast frames. Safe to construct without a browser in tests."""

	def __init__(self, port: int = 8765):
		self.port = port
		self._frames: deque[bytes] = deque(maxlen=1)
		self._wake = threading.Condition()
		self._server: ThreadingHTTPServer | None = None
		self._thread: threading.Thread | None = None
		self._running = False

	def publish(self, frame: bytes) -> None:
		with self._wake:
			self._frames.append(frame)
			self._wake.notify_all()

	def frame(self, timeout: float = 5.0) -> bytes | None:
		with self._wake:
			if not self._frames:
				self._wake.wait(timeout)
			return self._frames[0] if self._frames else None

	def start(self) -> str:
		if self._running:
			return self.url
		view = self

		class Handler(BaseHTTPRequestHandler):
			def log_message(self, *args):
				pass

			def do_GET(self):
				if self.path.split('?', 1)[0] not in ('/', '/stream'):
					self.send_error(404)
					return
				if self.path.startswith('/stream'):
					self.send_response(200)
					self.send_header('Content-Type', f'multipart/x-mixed-replace; boundary={BOUNDARY}')
					self.send_header('Cache-Control', 'no-store')
					self.end_headers()
					while view._running:
						data = view.frame()
						if data is None:
							continue
						self.wfile.write(f'--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(data)}\r\n\r\n'.encode())
						self.wfile.write(data + b'\r\n')
						self.wfile.flush()
				else:
					self.send_response(200)
					self.send_header('Content-Type', 'text/html; charset=utf-8')
					self.send_header('Content-Length', str(len(PAGE)))
					self.end_headers()
					self.wfile.write(PAGE)

		self._server = ThreadingHTTPServer(('127.0.0.1', self.port), Handler)
		self._server.daemon_threads = True
		self._running = True
		self._thread = threading.Thread(target=self._server.serve_forever, name='browse-dev-live-view', daemon=True)
		self._thread.start()
		return self.url

	@property
	def url(self) -> str:
		return 'http://127.0.0.1' + ':' + str(self.port) + '/'

	def stop(self) -> None:
		self._running = False
		with self._wake:
			self._wake.notify_all()
		if self._server:
			self._server.shutdown()
			self._server.server_close()
			self._server = None
		self._thread = None


_current: LiveView | None = None
_screencast_thread: threading.Thread | None = None


def start_live_view(port: int = 8765, quality: int = 60) -> str:
	"""Start the local live view for the attached tab. Returns the URL to open."""
	from browser_harness import helpers

	global _current, _screencast_thread
	if _current:
		stop_live_view()
	view = LiveView(port)
	url = view.start()
	_current = view
	helpers.cdp('Page.enable')
	helpers.cdp('Page.startScreencast', format='jpeg', quality=quality, everyNthFrame=2)

	def pump():
		while _current is view:
			for event in helpers.drain_events():
				if event.get('method') != 'Page.screencastFrame':
					continue
				params = event.get('params') or {}
				try:
					view.publish(base64.b64decode(params['data']))
					helpers.cdp('Page.screencastFrameAck', sessionId=params.get('sessionId', ''))
				except (KeyError, ValueError):
					continue

	_screencast_thread = threading.Thread(target=pump, name='browse-dev-screencast', daemon=True)
	_screencast_thread.start()
	return url


def stop_live_view() -> None:
	"""Stop the screencast and the local server (safe to call when nothing is running)."""
	from browser_harness import helpers

	global _current, _screencast_thread
	if _current is None:
		return
	view, _current = _current, None
	try:
		helpers.cdp('Page.stopScreencast')
	except RuntimeError:
		pass
	view.stop()
	_screencast_thread = None


def install() -> None:
	"""Make the helpers available to REPL cells, like page_info()."""
	from browser_harness import helpers

	helpers.start_live_view = start_live_view
	helpers.stop_live_view = stop_live_view
