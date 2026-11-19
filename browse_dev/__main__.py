"""Run the Browse Dev CLI with ``python -m browse_dev``."""

import sys

from browse_dev.cli import main

if __name__ == '__main__':
	result = main()
	if result is not None:
		sys.exit(result)
