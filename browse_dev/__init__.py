"""Browse Dev 1.0: a browser agent on Pydantic AI that writes Python against raw CDP.

from browse_dev import Agent
result = Agent('Find the top story on Hacker News').run_sync()
print(result.final_result())
"""

import os
from typing import TYPE_CHECKING

os.environ.setdefault('PYDANTIC_AI_NO_BANNER', '1')  # a library should not print an ad on every run

if os.environ.get('BROWSE_DEV_SETUP_LOGGING', 'true').lower() != 'false':
	from browse_dev.logging_config import setup_logging

	setup_logging()

from browse_dev.legacy import install as _install_0x_import_errors

_install_0x_import_errors()  # import browse_dev.dom (any 0.x module path) names its 1.0 answer

if TYPE_CHECKING:
	from browse_dev.agent import Agent, AgentHistoryList
	from browse_dev.browser import Browser
	from browse_dev.llm import ChatAnthropic, ChatBrowseDev, ChatGoogle, ChatOpenAI
	from browse_dev.telemetry.feedback import feedback
	from browse_dev.tools import ActionResult, Controller, Tools

_LAZY_IMPORTS = {
	'Agent': 'browse_dev.agent',
	'AgentHistoryList': 'browse_dev.agent',
	'Browser': 'browse_dev.browser',
	'Tools': 'browse_dev.tools',
	'Controller': 'browse_dev.tools',
	'ActionResult': 'browse_dev.tools',
	'ChatBrowseDev': 'browse_dev.llm',
	'ChatOpenAI': 'browse_dev.llm',
	'ChatAnthropic': 'browse_dev.llm',
	'ChatGoogle': 'browse_dev.llm',
	'feedback': 'browse_dev.telemetry.feedback',
}
_BEDROCK = "llm='bedrock:<model id>' (pip install 'pydantic-ai-slim[bedrock]'; AWS credentials and AWS_DEFAULT_REGION)."
_LLM_REMOVED = {  # each 0.x provider class -> its Pydantic AI model string, or ChatOpenAI for an OpenAI-compatible server
	'ChatAzureOpenAI': "llm='azure:<deployment>' with AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY and OPENAI_API_VERSION set.",
	'ChatAWSBedrock': _BEDROCK,
	'ChatAnthropicBedrock': _BEDROCK,
	'ChatDeepSeek': "llm='deepseek:deepseek-chat' with DEEPSEEK_API_KEY set.",
	'ChatGroq': "llm='groq:<model>' (pip install 'pydantic-ai-slim[groq]'; GROQ_API_KEY).",
	'ChatMistral': "llm='mistral:<model>' (pip install 'pydantic-ai-slim[mistral]'; MISTRAL_API_KEY).",
	'ChatOpenRouter': "llm='openrouter:<vendor>/<model>' with OPENROUTER_API_KEY set.",
	'ChatCerebras': "llm='cerebras:<model>' with CEREBRAS_API_KEY set.",
	'ChatVercel': "llm='vercel:<vendor>/<model>' with VERCEL_AI_GATEWAY_API_KEY set.",
	'ChatOllama': "ChatOpenAI('<model>', base_url='http://localhost:11434/v1', api_key='ollama').",
	**dict.fromkeys(
		('ChatLiteLLM', 'ChatOCIRaw', 'ChatOrcaRouter'), 'ChatOpenAI(model, base_url=...) for its OpenAI-compatible endpoint.'
	),
}
_REMOVED = {  # 0.x top-level names -> the 1.0 alternative
	'BrowserSession': 'Browser(...).',
	'BrowserProfile': 'pass options to Browser(...).',
	'BrowserConfig': 'pass options to Browser(...).',
	'BrowserContext': 'pass options to Browser(...).',
	'BrowserContextConfig': 'pass options to Browser(...).',
	'CodeAgent': 'Agent(...): the 1.0 agent writes Python itself.',
	'DomService': 'the agent reads pages with Python.',
	'SystemPrompt': 'Agent(extend_system_message=...).',
	'ActionModel': 'custom actions are plain functions: @tools.action(...).',
	'sandbox': '',
	'models': "a Pydantic AI model string, e.g. llm='openai:gpt-6-luna'.",
	**_LLM_REMOVED,
}


def __getattr__(name: str):
	if name in _LAZY_IMPORTS:
		from importlib import import_module

		attr = getattr(import_module(_LAZY_IMPORTS[name]), name)
		globals()[name] = attr
		return attr
	if name == '__version__':  # 'unknown' from a checkout that is not installed
		from browse_dev.utils import get_browse_dev_version

		return get_browse_dev_version()
	from browse_dev.legacy import removed_name

	# BrowserSession, ChatGroq; from browse_dev import dom (a 0.x module): the removed error naming the 1.0 answer
	raise removed_name(__name__, name, _REMOVED)


__all__ = [
	'Agent',
	'AgentHistoryList',
	'Browser',
	'Tools',
	'Controller',
	'ActionResult',
	'ChatBrowseDev',
	'ChatOpenAI',
	'ChatAnthropic',
	'ChatGoogle',
	'feedback',
]
