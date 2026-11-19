"""0.x import paths and names 1.0 removed: each raises the removed error naming its 1.0 answer (MIGRATING.md).

Modules: a finder at the end of sys.meta_path, so it only sees paths no real module answers. Names in modules 1.0
kept (browse_dev.agent.views.AgentOutput, ...): the module's __getattr__ calls removed_name()."""

from __future__ import annotations

import re
import sys
from importlib.machinery import ModuleSpec, PathFinder
from opcode import opmap

_LLM = (
	'from browse_dev import ChatBrowseDev, ChatOpenAI, ChatAnthropic, ChatGoogle, or a Pydantic AI model string such as '
	"llm='openai:gpt-6-luna'."
)
CALL_MODEL = (
	'the agent calls the model itself. To call one directly use Pydantic AI: '
	'await pydantic_ai.Agent(llm.pydantic_model()).run(prompt) (output_type=YourModel for structured output).'
)
_LOOP = 'the 0.x loop internals are gone: the model writes Python cells, result.messages holds the transcript.'
_BROWSER = 'from browse_dev import Browser; pass options to Browser(...) (BrowserSession and BrowserProfile are gone).'
_IN_PYTHON = 'the agent drives the page with Python and raw CDP in its REPL; there is no DOM, Page or Element API.'
_EVENTS = (
	"each step logs one INFO line to logging.getLogger('browse_dev'); add a logging.Handler to stream progress, and "
	'read result.messages after the run.'
)
_MCP_CLIENT = 'call the MCP server from a plain @tools.action function.'
_MCP_SERVER = 'browse-dev --cli-mcp (browse-dev --mcp now serves the same browser_exec and browser_screenshot tools).'
_CODE_AGENT = 'from browse_dev import Agent: the 1.0 agent writes Python itself.'
_CLI = 'the browse-dev CLI pipes Python to browser-harness (browse-dev --help), and browse-dev --cli-mcp serves it over MCP.'
_USAGE = 'result.usage (tokens) and result.cost_usd.'
_LLM_ERROR = "result.error (run() returns status='error' for provider failures)."
_TELEMETRY = 'telemetry is internal; ANONYMIZED_TELEMETRY=false turns it off.'
_SKILLS = 'none (Cloud Skills were removed).'
_UTILS = 'none: it was a 0.x internal helper; copy what you need.'
_OBSERVABILITY = (
	"Pydantic AI's OpenTelemetry tracing: pydantic_ai.Agent.instrument_all() (or logfire.instrument_pydantic_ai()) "
	'traces every model request and tool call of every run.'
)


def _llm_modules() -> dict[str, str]:
	from browse_dev import _LLM_REMOVED

	providers = {
		'aws': 'ChatAWSBedrock',
		'azure': 'ChatAzureOpenAI',
		'cerebras': 'ChatCerebras',
		'deepseek': 'ChatDeepSeek',
		'groq': 'ChatGroq',
		'litellm': 'ChatLiteLLM',
		'mistral': 'ChatMistral',
		'oci_raw': 'ChatOCIRaw',
		'ollama': 'ChatOllama',
		'openrouter': 'ChatOpenRouter',
		'orcarouter': 'ChatOrcaRouter',
		'vercel': 'ChatVercel',
	}
	kept = {'openai': 'ChatOpenAI', 'anthropic': 'ChatAnthropic', 'google': 'ChatGoogle', 'browse_dev': 'ChatBrowseDev'}
	return {
		**{f'browse_dev.llm.{m}': _LLM_REMOVED[cls] for m, cls in providers.items()},
		**{f'browse_dev.llm.{m}': f'from browse_dev import {cls}.' for m, cls in kept.items()},
	}


# 0.x module (and everything under it) -> the 1.0 answer. Longest match wins. Built on first use: it reads browse_dev.
_MODULES: dict[str, str] = {}


def _modules() -> dict[str, str]:
	if not _MODULES:
		_MODULES.update(
			{
				'browse_dev.actor': _IN_PYTHON,
				'browse_dev.dom': _IN_PYTHON,
				'browse_dev.agent.message_manager': _LOOP,
				'browse_dev.agent.memory': 'none: every result stays in the conversation; long runs are compacted on their own.',
				'browse_dev.agent.playwright_script_generator': _LOOP,
				'browse_dev.agent.playwright_script_helpers': _LOOP,
				'browse_dev.agent.tests': '',
				'browse_dev.browser.tests': '',
				'browse_dev.browser.context': _BROWSER,
				'browse_dev.browser.types': _BROWSER,
				'browse_dev.browser.utils': _BROWSER,
				'browse_dev.browser.extensions': _BROWSER,
				'browse_dev.browser.dolphin_service': "Browser(cdp_url=...) attaches to another browser's CDP endpoint.",
				'browse_dev.code_use': _CODE_AGENT,
				'browse_dev.skill_cli': _CLI,
				'browse_dev.agent.variable_detector': _LOOP,
				'browse_dev.agent.cloud_events': _LOOP,
				'browse_dev.agent.prompts': 'Agent(extend_system_message=...) adds to the fixed system prompt.',
				'browse_dev.agent.system_prompts': 'Agent(extend_system_message=...) adds to the fixed system prompt.',
				'browse_dev.agent.gif': 'none (live_view=True shows a cloud browser live).',
				'browse_dev.beta': 'from browse_dev import Agent.',
				'browse_dev.browser.session': _BROWSER,
				'browse_dev.browser.session_manager': _BROWSER,
				'browse_dev.browser.profile': _BROWSER,
				'browse_dev.browser.views': _BROWSER,
				'browse_dev.browser.chrome': "Browser('chrome') (your open Chrome) or Browser('chromium') (a fresh one).",
				'browse_dev.browser.cloud': 'Browser() is a cloud browser (cloud_profile_id=, cloud_proxy_country_code=, cloud_timeout=).',
				'browse_dev.browser.events': _EVENTS,
				'browse_dev.browser.watchdog_base': _BROWSER,
				'browse_dev.browser.watchdogs': _BROWSER,
				**dict.fromkeys(  # 0.6.0 kept the watchdogs next to the session
					(
						f'browse_dev.browser.{w}_watchdog'
						for w in (
							'aboutblank',
							'crash',
							'default_action',
							'dom',
							'downloads',
							'local_browser',
							'permissions',
							'popups',
							'screenshot',
							'security',
							'storage_state',
						)
					),
					_BROWSER,
				),
				'browse_dev.browser.service': _BROWSER,  # 0.1.0
				'browse_dev.browser._cdp_timeout': _BROWSER,
				'browse_dev.browser.demo_mode': 'Agent(highlight_actions=True) marks each click and keypress on the page.',
				'browse_dev.browser.python_highlights': 'Agent(highlight_actions=True) marks each click and keypress on the page.',
				'browse_dev.browser.video_recorder': 'none (live_view=True shows a cloud browser live).',
				'browse_dev.controller': 'from browse_dev import Tools (Controller is the same class).',
				**dict.fromkeys(  # each 0.x submodule by name too: `from browse_dev.tools import registry` asks for it
					(
						'browse_dev.tools',
						*(f'browse_dev.tools.{m}' for m in ('registry', 'service', 'views', 'extraction', 'utils')),
					),
					'from browse_dev import Tools, ActionResult.',
				),
				'browse_dev.filesystem': 'Agent(workspace=...) is a plain directory the agent reads and writes.',
				'browse_dev.screenshots': 'the agent calls screenshot() in its REPL.',
				'browse_dev.init_cmd': 'none (browse-dev init templates were removed).',
				'browse_dev.cli_templates': 'none (browse-dev init templates were removed).',
				'browse_dev.integrations': 'none yet: the hosted-browser integrations come back on the new Browser later.',
				'browse_dev.llm': _LLM,
				**dict.fromkeys(
					(f'browse_dev.llm.{m}' for m in ('messages', 'base', 'views', 'schema', 'exceptions')), CALL_MODEL
				),
				'browse_dev.llm.models': "a Pydantic AI model string, e.g. llm='openai:gpt-6-luna'.",
				'browse_dev.llm.tests': '',
				**_llm_modules(),
				'browse_dev.mcp.client': _MCP_CLIENT,
				'browse_dev.mcp.controller': _MCP_CLIENT,
				'browse_dev.mcp.server': _MCP_SERVER,
				'browse_dev.observability': _OBSERVABILITY,
				'browse_dev.sandbox': '',
				'browse_dev.skills.service': _SKILLS,
				'browse_dev.skills.utils': _SKILLS,
				'browse_dev.skills.views': _SKILLS,
				'browse_dev.sync': 'none (cloud sync of local runs was removed).',
				'browse_dev.tokens': _USAGE,
			}
		)
	return _MODULES


# names 0.x had in modules 1.0 kept -> the 1.0 answer (a name not listed is a plain AttributeError)
_AGENT_VIEWS = {
	**dict.fromkeys(('AgentOutput', 'AgentBrain'), 'the model writes Python cells; result.messages holds them.'),
	'AgentState': 'the result run() returns (AgentHistoryList): status, text, output, steps, usage, messages.',
	'AgentHistory': 'AgentHistoryList, the result run() returns; per-step detail is result.messages.',
	**dict.fromkeys(('AgentStepInfo', 'StepMetadata'), 'result.number_of_steps(), result.usage and result.messages.'),
	'AgentSettings': 'pass options to Agent(...).',
	'AgentError': "result.error (run() returns status='error' instead of raising).",
	'AgentStructuredOutput': 'Agent(output_model_schema=...); result.output holds the parsed value.',
	**dict.fromkeys(('JudgementResult', 'SimpleJudgeResult'), 'result.judgement (browse_dev.agent.judge.Judgement).'),
	**dict.fromkeys(('ModelPricingCatalog', 'Pricing', 'TokenDetails', 'TokenUsage'), _USAGE),
	'REQUIRED_LLM_API_ENV_VARS': "each model takes api_key=... or reads its provider's environment variable.",
	**dict.fromkeys(
		(
			'ActionLoopDetector',
			'DetectedVariable',
			'MessageCompactionSettings',
			'PageFingerprint',
			'PlanItem',
			'RerunSummaryAction',
			'ToolCallingMethod',
			'AgentOnlyAction',
			'AskHumanAgentAction',
			'ClickElementControllerHistoryItem',
			'InputTextControllerHistoryItem',
			'Output',
			'VariableMetadata',
			'compute_action_hash',
		),
		_LOOP,
	),
}
_NAMES: dict[str, dict[str, str]] = {
	'browse_dev.agent': {'BetaAgentError': ''},
	'browse_dev.agent.service': {
		'AgentHookFunc': _EVENTS,
		'AgentService': 'from browse_dev import Agent.',  # 0.1.0
		'SKIP_LLM_API_KEY_VERIFICATION': 'none: a free request checks the key and model before the browser starts.',
		**dict.fromkeys(('Context', 'log_response'), _LOOP),
	},
	'browse_dev.agent.views': _AGENT_VIEWS,
	'browse_dev.agent.judge': dict.fromkeys(('JudgementResult', 'SimpleJudgeResult'), 'result.judgement (Judgement).'),
	'browse_dev.browser': {
		'BrowserSession': 'Browser(...).',
		**dict.fromkeys(
			('BrowserProfile', 'BrowserConfig', 'BrowserContext', 'BrowserContextConfig'), 'pass options to Browser(...).'
		),
		'ProxySettings': "Browser(cloud_proxy_country_code='us') on cloud browsers; Browser('chromium') has no proxy yet.",
	},
	'browse_dev.config': dict.fromkeys(
		(
			'AgentEntry',
			'BrowserProfileEntry',
			'DBStyleConfigJSON',
			'DBStyleEntry',
			'FlatEnvConfig',
			'LLMEntry',
			'OldConfig',
			'create_default_config',
			'get_default_llm',
			'get_default_profile',
			'load_and_migrate_config',
			'load_browse_dev_config',
		),
		'Agent(...) and Browser(...) arguments; 1.0 reads no config.json (browse-dev --mcp keeps its domain limits).',
	),
	'browse_dev.exceptions': {'LLMException': _LLM_ERROR},
	'browse_dev.llm': {
		**dict.fromkeys(
			(
				'AssistantMessage',
				'BaseMessage',
				'ContentImage',
				'ContentRefusal',
				'ContentText',
				'SystemMessage',
				'UserMessage',
			),
			CALL_MODEL,
		),
		'BaseChatModel': (
			'ChatBrowseDev, ChatOpenAI, ChatAnthropic, ChatGoogle, a Pydantic AI model string or a pydantic_ai.models.Model.'
		),
	},
	'browse_dev.logging_config': dict.fromkeys(
		('FIFOHandler', 'addLoggingLevel', 'setup_log_pipes'),
		"logging.getLogger('browse_dev') and BROWSE_DEV_LOGGING_LEVEL=debug|info|warning|error.",
	),
	'browse_dev.mcp': {
		'BrowseDevServer': _MCP_SERVER,
		**dict.fromkeys(('MCPClient', 'MCPToolWrapper'), _MCP_CLIENT),
	},
	'browse_dev.skills': dict.fromkeys(('MissingCookieException', 'SkillService'), _SKILLS),
	'browse_dev.cli': dict.fromkeys(
		(
			'auth',
			'BROWSER_LOGO',
			'BrowseDevApp',
			'CHROME_PROFILES_DIR',
			'get_default_config',
			'get_llm',
			'init',
			'INIT_TEMPLATES',
			'install',
			'load_user_config',
			'MAX_HISTORY_LENGTH',
			'RichLogHandler',
			'run_auth_command',
			'run_main_interface',
			'run_prompt_mode',
			'save_user_config',
			'setup_readline_history',
			'TEXTUAL_BORDER_STYLES',
			'textual_interface',
			'update_config_with_click_args',
			'USER_CONFIG_DIR',
			'USER_CONFIG_FILE',
			'USER_DATA_DIR',
		),
		_CLI,
	),
	**dict.fromkeys(
		('browse_dev.telemetry', 'browse_dev.telemetry.views'),
		dict.fromkeys(
			(
				'MCPClientTelemetryEvent',
				'MCPServerTelemetryEvent',
				'CLITelemetryEvent',
				'ControllerRegisteredFunctionsTelemetryEvent',
				'RegisteredFunction',
				'AgentEndTelemetryEvent',
				'AgentRunTelemetryEvent',
				'AgentStepErrorTelemetryEvent',
				'AgentStepTelemetryEvent',
			),
			_TELEMETRY,
		),
	),
	'browse_dev.telemetry.service': {'xdg_cache_home': _TELEMETRY},
	'browse_dev.utils': {
		**dict.fromkeys(
			(
				'SignalHandler',
				'GLOBAL_RETRY_SEMAPHORES',
				'GLOBAL_RETRY_SEMAPHORE_LOCK',
				'MULTIPROCESS_SEMAPHORES',
				'MULTIPROCESS_SEMAPHORE_DIR',
				'MULTIPROCESS_SEMAPHORE_LOCK',
				'retry',
				'BROWSE_DEV_CONFIG_DIR',
				'handle_llm_error',
				'URL_NEGATION_PATTERN',
				'URL_PATTERN',
				'check_env_variables',
				'check_latest_browse_dev_version',
				'collect_sensitive_data_values',
				'create_task_with_error_handling',
				'get_git_info',
				'has_url_negation',
				'is_new_tab_page',
				'is_placeholder_url',
				'is_unsafe_pattern',
				'match_url_with_domain_pattern',
				'merge_dicts',
				'redact_sensitive_string',
				'sanitize_surrogates',
				'sanitize_url_candidate',
				'time_execution_async',
				'time_execution_sync',
			),
			_UTILS,
		),
		'LLMException': _LLM_ERROR,
	},
}
# 0.1.x-0.5.x: from browse_dev.browser.browser import ...
_NAMES['browse_dev.browser.browser'] = {**_NAMES['browse_dev.browser'], 'IN_DOCKER': _UTILS}


# Every public method and attribute of the 0.x BrowserSession, BrowserContext and Browser (0.1 to 0.13, from the tags)
# that 1.0's Browser does not have: each raises the removed error (browser.py REMOVED_METHODS names the common ones)
BROWSER_MEMBERS = frozenset(
	(
		'RECONNECT_WAIT_TIMEOUT',
		'add_highlights',
		'agent_current_page',
		'agent_focus',
		'agent_focus_target_id',
		'apply_session_overrides_to_profile',
		'attach_all_watchdogs',
		'auto_download_pdfs',
		'browser',
		'browser_context',
		'browser_pid',
		'cached_state',
		'cdp_client_for_frame',
		'cdp_client_for_node',
		'cdp_client_for_target',
		'cleanup_httpx_clients',
		'clear_cookies',
		'close_current_tab',
		'close_page',
		'cloud_browser',
		'connect',
		'context',
		'cookies',
		'copy_old_config_names_to_new',
		'create_new_tab',
		'current_page',
		'current_session_id',
		'current_target_id',
		'demo_mode',
		'detect_display_configuration',
		'downloaded_files',
		'execute_javascript',
		'find_file_input_near_element',
		'find_file_upload_element_by_index',
		'find_frame_target',
		'get_agent_current_page',
		'get_all_frames',
		'get_args',
		'get_browser_state_with_recovery',
		'get_current_page_title',
		'get_current_page_url',
		'get_current_target_info',
		'get_dom_element_at_coordinates',
		'get_dom_element_by_index',
		'get_element_by_index',
		'get_element_coordinates',
		'get_focused_target',
		'get_index_by_class',
		'get_index_by_id',
		'get_locate_element',
		'get_locate_element_by_css_selector',
		'get_locate_element_by_text',
		'get_locate_element_by_xpath',
		'get_minimal_state_summary',
		'get_most_recently_opened_target_id',
		'get_or_create_cdp_session',
		'get_page_info',
		'get_page_structure',
		'get_page_targets',
		'get_pages',
		'get_playwright_browser',
		'get_scroll_info',
		'get_selector_index',
		'get_selector_map',
		'get_session',
		'get_state',
		'get_state_as_text',
		'get_state_summary',
		'get_state_summary_with_fallback',
		'get_tabs_info',
		'get_target_id_from_session_id',
		'get_target_id_from_tab_id',
		'get_target_id_from_url',
		'go_back',
		'go_forward',
		'highlight_coordinate_click',
		'highlight_interaction_element',
		'human_current_page',
		'initialized',
		'is_cdp_connected',
		'is_connected',
		'is_file_input',
		'is_file_input_by_index',
		'is_file_uploader',
		'is_local',
		'is_reconnecting',
		'kwargs_for_connect',
		'kwargs_for_launch',
		'kwargs_for_launch_persistent_context',
		'kwargs_for_new_context',
		'llm_screenshot_size',
		'load_cookies_from_file',
		'load_storage_state',
		'logger',
		'must_get_current_page',
		'new_context',
		'new_tab',
		'on_AgentFocusChangedEvent',
		'on_BrowserStartEvent',
		'on_BrowserStopEvent',
		'on_CloseTabEvent',
		'on_FileDownloadedEvent',
		'on_NavigateToUrlEvent',
		'on_SwitchTabEvent',
		'on_TabClosedEvent',
		'on_TabCreatedEvent',
		'optimize_large_domain_lists',
		'playwright',
		'prepare_user_data_dir',
		'reconnect',
		'refresh',
		'refresh_page',
		'remove_highlights',
		'reset',
		'reset_context',
		'save_cookies',
		'save_storage_state',
		'screenshot_element',
		'send_demo_mode_log',
		'session_manager',
		'set_auto_download_pdfs',
		'set_browser_ownership',
		'set_extra_headers',
		'set_viewport_size',
		'setup_browser_via_browser_pid',
		'setup_browser_via_cdp_url',
		'setup_browser_via_passed_objects',
		'setup_browser_via_wss_url',
		'setup_new_browser_context',
		'setup_playwright',
		'switch_to_tab',
		'tabs',
		'update_cached_selector_map',
		'validate_highlight_elements_conflict',
		'validate_proxy_settings',
		'wait_for_element',
		'wait_if_captcha_solving',
		'warn_deterministic_rendering_weirdness',
		'warn_storage_state_user_data_dir_conflict',
		'warn_user_data_dir_non_default_version',
		'wss_url',
	)
)

# 0.x browse_dev.llm built model instances on attribute access: llm.openai_gpt_4o, llm.google_gemini_2_5_flash, ...
_LLM_INSTANCE = re.compile(r'(openai|azure|google|anthropic|mistral|cerebras|bu)_\w+|codestral|pixtral_large|get_llm_by_name')
_LLM_INSTANCE_ANSWER = {
	'openai': "ChatOpenAI('<model>'), e.g. ChatOpenAI('gpt-4o') for openai_gpt_4o.",
	'azure': "llm='azure:<deployment>' with AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY and OPENAI_API_VERSION set.",
	'google': "ChatGoogle('<model>'), e.g. ChatGoogle('gemini-2.5-flash') for google_gemini_2_5_flash.",
	'anthropic': "ChatAnthropic('<model>'), e.g. ChatAnthropic('claude-sonnet-4-0') for anthropic_claude_sonnet_4_0.",
	'cerebras': "llm='cerebras:<model>' with CEREBRAS_API_KEY set.",
	'bu': "ChatBrowseDev('bu-fast') (the 0.x bu-1-0 / bu-2-0 / bu-latest need browse-dev<1.0).",
}


def removed_name(module: str, name: str, names: dict[str, str] | None = None) -> ImportError | AttributeError:
	"""For a module's __getattr__: the removed error for a 0.x name (in _NAMES or names), else the plain AttributeError.
	An ImportError only for a from-import, where an AttributeError reads as a bare "cannot import name". Elsewhere an
	AttributeError with the same text: hasattr() and getattr(module, name, default) catch only that, and feature
	detection of a 0.x name (getattr(browse_dev, 'BrowserSession', None)) raised instead of taking its fallback."""
	error = _removed_name(module, name, names)
	if isinstance(error, ImportError) and not _from_import():
		return AttributeError(str(error), name=name, obj=sys.modules.get(module))
	return error


def _removed_name(module: str, name: str, names: dict[str, str] | None) -> ImportError | AttributeError:
	if name in (names := {**_NAMES.get(module, {}), **(names or {})}):
		from browse_dev.exceptions import removed  # here: this module is imported from modules exceptions imports

		return ImportError(removed(f'{module}.{name}', names[name]), name=module)
	if module == 'browse_dev.llm' and _LLM_INSTANCE.fullmatch(name):
		from browse_dev.exceptions import removed

		answer = _LLM_INSTANCE_ANSWER.get(name.split('_')[0], "llm='mistral:<model>' (pip install 'pydantic-ai-slim[mistral]').")
		if name == 'get_llm_by_name':
			answer = (
				"ChatOpenAI / ChatAnthropic / ChatGoogle / ChatBrowseDev, or a Pydantic AI model string: llm='openai:gpt-4o'."
			)
		return ImportError(removed(f'{module}.{name}', answer), name=module)
	if not name.startswith('_') and (message := _removed_submodule(module, name)):
		return ModuleNotFoundError(message, name=f'{module}.{name}')
	return AttributeError(f'module {module!r} has no attribute {name!r}')


def _from_import() -> bool:
	"""Whether the module attribute being looked up is read by a from-import: `from package import name` (importlib's
	_handle_fromlist asks hasattr(package, name)) or `from module import name` (the IMPORT_FROM instruction)."""
	frame = sys._getframe(1)
	# past removed_name and the module's __getattr__: the frame before them read the attribute
	while frame is not None and frame.f_code.co_name in ('removed_name', '__getattr__'):
		if not frame.f_globals.get('__name__', '').startswith('browse_dev'):
			break
		frame = frame.f_back
	if frame is None:
		return False
	if frame.f_code.co_name == '_handle_fromlist' and frame.f_globals.get('__name__') == 'importlib._bootstrap':
		return True
	return frame.f_lasti >= 0 and frame.f_code.co_code[frame.f_lasti] == _IMPORT_FROM


_IMPORT_FROM = opmap['IMPORT_FROM']


def _removed_submodule(package: str, name: str) -> str | None:
	"""`from browse_dev.browser import session`: from-import asks the package's __getattr__ before it imports the
	submodule, and swallows the finder's ModuleNotFoundError for a missing one ("cannot import name 'session'"). A
	real 1.0 module under a 0.x prefix (browse_dev.tools) is None: the import system loads it."""
	fullname = f'{package}.{name}'
	if fullname not in _modules():  # a 0.x module itself, not a name under one (from browse_dev.llm import NotAThing)
		return None
	if PathFinder.find_spec(fullname, getattr(sys.modules.get(package), '__path__', None) or []) is not None:
		return None
	return removed_module(fullname)


def removed_names(module: str):
	"""A module's __getattr__ that raises removed_name()."""

	def __getattr__(name: str):
		raise removed_name(module, name)

	return __getattr__


def removed_module(fullname: str) -> str | None:
	"""The removed error for a 0.x module path, or None for a path 0.x did not have."""
	from browse_dev.exceptions import removed

	modules = _modules()
	parts = fullname.split('.')
	for i in range(len(parts), 1, -1):
		if (prefix := '.'.join(parts[:i])) in modules:
			return removed(fullname, modules[prefix])
	return None


class Removed0xModules:
	"""Last on sys.meta_path: a browse_dev.* path no real module answered. A 0.x path raises ModuleNotFoundError (an
	ImportError, so `except ImportError` fallbacks still work) naming its 1.0 answer; any other path is left to Python."""

	@classmethod
	def find_spec(cls, fullname: str, path: object = None, target: object = None) -> ModuleSpec | None:
		if fullname.startswith('browse_dev.') and (message := removed_module(fullname)):
			raise ModuleNotFoundError(message, name=fullname)
		return None


def install() -> None:
	if Removed0xModules not in sys.meta_path:
		sys.meta_path.append(Removed0xModules)  # type: ignore[arg-type]  # a finder class with find_spec, like PathFinder
