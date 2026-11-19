"""python -m browse_dev.mcp: the 0.x module form of `browse-dev --mcp`, with the same own Chromium (never the user's
Chrome) and quiet stdout."""

import sys

from browse_dev.cli import _run_mcp_server

if __name__ == '__main__':
	sys.exit(_run_mcp_server('python -m browse_dev.mcp'))
