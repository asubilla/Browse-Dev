from __future__ import annotations

import socket
import urllib.request

from browse_dev.liveview import BOUNDARY, LiveView


def _free_port() -> int:
	with socket.socket() as s:
		s.bind(('127.0.0.1', 0))
		return s.getsockname()[1]


def test_live_view_serves_page_and_latest_frame():
	view = LiveView(_free_port())
	try:
		url = view.start()
		page = urllib.request.urlopen(url, timeout=5).read()
		assert b'<img src="/stream"' in page

		view.publish(b'\xff\xd8first\xff\xd9')
		view.publish(b'\xff\xd8latest\xff\xd9')
		with urllib.request.urlopen(url + 'stream', timeout=5) as stream:
			assert stream.headers['Content-Type'] == f'multipart/x-mixed-replace; boundary={BOUNDARY}'
			chunk = stream.read(512)
		assert b'--frame' in chunk and b'latest' in chunk and b'first' not in chunk
		assert view.frame() == b'\xff\xd8latest\xff\xd9'
	finally:
		view.stop()


def test_frame_returns_none_when_nothing_published():
	view = LiveView(_free_port())
	assert view.frame(timeout=0.01) is None
