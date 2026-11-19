import logging
import os
import re
import sys
from typing import TYPE_CHECKING

_CONTROL = re.compile(r'[\x00-\x08\x0b-\x1f\x7f-\x9f]')  # C0 but tab and newline, DEL, C1


def printable(text: str) -> str:
	"""Text with control characters escaped (ESC as \\x1b): page and model text logged raw could rewrite the terminal
	(erase or fake log lines, set its title, write the clipboard over OSC 52)."""
	return _CONTROL.sub(lambda m: m[0].encode('unicode_escape').decode(), text)


class _PrintableFormatter(logging.Formatter):
	def format(self, record: logging.LogRecord) -> str:
		return printable(super().format(record))


def setup_logging(level: str | None = None) -> logging.Logger:
	"""One stderr handler on the 'browse_dev' logger. BROWSE_DEV_LOGGING_LEVEL=debug|info|warning|error."""
	level = (level or os.getenv('BROWSE_DEV_LOGGING_LEVEL', 'info')).lower()
	logger = logging.getLogger('browse_dev')
	if not logger.handlers:
		handler = logging.StreamHandler(sys.stderr)
		handler.setFormatter(_PrintableFormatter('%(levelname)-8s [%(name)s] %(message)s'))
		logger.addHandler(handler)
	logger.setLevel(getattr(logging, level.upper(), logging.INFO))
	logger.propagate = False
	if not isinstance(logging.getLevelName(level.upper()), int):  # 0.x 'result', or a typo: says so instead of INFO silently
		logger.warning(f'BROWSE_DEV_LOGGING_LEVEL={level!r} is not a level (debug, info, warning, error); using info.')
	for var in ('BROWSE_DEV_DEBUG_LOG_FILE', 'BROWSE_DEV_INFO_LOG_FILE'):  # 0.x wrote a log file there
		if os.getenv(var):
			logger.warning(
				f'{var} is set but browse-dev 1.0 does not read it: no log file is written. Add a logging.FileHandler '
				"to logging.getLogger('browse_dev') instead."
			)
	return logger


if not TYPE_CHECKING:  # pyright would accept any name imported from here
	from browse_dev.legacy import removed_names

	__getattr__ = removed_names(__name__)  # a 0.x name raises the removed error naming its 1.0 answer
