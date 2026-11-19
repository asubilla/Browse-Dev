# CLAUDE.md

Guidance for coding agents working in this repository (AGENTS.md has the same content).

Browse Dev 1.0 is a browser agent on [Pydantic AI](https://ai.pydantic.dev). The model does not pick one action per
step from a DOM dump: it writes Python in one persistent REPL that has the
[browser-harness](https://github.com/browser-use/browser-harness) helpers and raw CDP. The 0.x public API (`Agent`,
`Browser`, `Tools`, `run()`, `final_result()`) is kept on top; MIGRATING.md lists every 0.x option and its 1.0 answer.

## Architecture

```
Agent(task, llm, browser).run()                  browse_dev/agent/service.py   0.x API, telemetry, lifecycle
  -> resolve_model(llm)                          browse_dev/llm/__init__.py    bu-fast gateway default, ChatOpenAI/Anthropic/Google, model strings
  -> Browser.start() -> env for the worker       browse_dev/browser/browser.py cloud (API v4, default) | 'chromium' (local.py) | 'chrome' (harness daemon) | cdp_url
  -> run(agent, task, Session)                   browse_dev/agent/loop.py      Pydantic AI loop: python tool, finish / finish_from_repl,
                                                                                image pruning, delivery guards, budgets, partial results
       python(code) -> Repl.call()               browse_dev/repl/session.py    parent side: spawns the worker, allowlisted env, redaction
                    -> worker process            browse_dev/repl/worker.py     runs cells; helpers, screenshot, checkpoint, type_secret
                       mode='ultrafast' adds bu  browse_dev/ax.py              accessibility-tree helpers (port of Browse Dev Pi ax.ts)
  <- AgentHistoryList                            browse_dev/agent/views.py     status, text/output, success, partial, usage, cost_usd, messages
```

- The system prompt is `browse_dev/agent/prompt.py`. It is evaluated; do not edit it casually.
- The REPL worker is a child process in its own process group: a cell timeout kills the tree and restarts it. Files
  and browser state survive, Python variables do not.
- Secrets (`sensitive_data`) are redacted from specific channels (listed in "Trust model" in MIGRATING.md), not sandboxed.
- `browse-dev` CLI and `--cli-mcp` (`browse_dev/cli.py`, `browse_dev/mcp/`) pipe Python to browser-harness.
- `browse_dev/skills/` ships the `browse-dev` agent skill and its installer.

## Development

```bash
uv sync --all-extras
uv run pytest tests/ci                 # no provider calls, no cloud; tests needing Chrome skip without it
uv run pytest tests/ci -m "not chrome" # what the Windows/macOS/Linux matrix runs
uv run ruff check && uv run ruff format
uv run pyright
```

## Rules

- Use `uv`, tabs, modern typing (`str | None`).
- Do not replace model names; users try models you do not know yet.
- Tests use a real REPL worker and a real headless Chrome (`tests/ci/conftest.py`), and a scripted `FunctionModel`
  instead of a provider. Never call paid APIs or create cloud browsers in tests; mock the cloud HTTP calls.
- One regression test per bug, failing before the fix.
- 0.x options 1.0 cannot honor raise a `TypeError` naming the option before any browser starts; keep MIGRATING.md in
  sync when you add or remove one.
- Never create example files to show off a feature.
