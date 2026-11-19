from typing import TYPE_CHECKING

from browse_dev.agent.service import Agent
from browse_dev.agent.views import AgentHistoryList

__all__ = ['Agent', 'AgentHistoryList']


if not TYPE_CHECKING:  # pyright would accept any name imported from here
	from browse_dev.legacy import removed_names

	__getattr__ = removed_names(__name__)  # a 0.x name raises the removed error naming its 1.0 answer
