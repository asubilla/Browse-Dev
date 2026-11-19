---
name: remote-browser
description: Controls an isolated Browse Dev Cloud browser from a sandboxed machine with the current Browse Dev CLI.
allowed-tools: Bash(browse-dev:*)
---

# Remote Browser

Use this skill when an agent runs on a machine without a usable local Chrome and needs an isolated browser. The current Browse Dev CLI runs Python from stdin. Do not use the removed `open`, `state`, `click`, `input`, `tab`, `cloud connect`, or `--connect` commands.

## Check the CLI

```bash
browse-dev --doctor
browse-dev skill show
```

If setup fails, follow the current [Browse Dev skill](../browse-dev/SKILL.md).

## Start an isolated browser

Authenticate once:

```bash
browse-dev auth login
```

Pick a short unique name. `r7k2` below is only an example.

```bash
browse-dev <<'PY'
start_remote_daemon("r7k2")
PY
```

Use the same name for every command in this browser:

```bash
BU_NAME=r7k2 browse-dev <<'PY'
new_tab("https://example.com")
wait_for_load()
print(page_info())
PY
```

Each remote daemon is a separate Browse Dev Cloud browser. Use a different name for each parallel task. Remote browsers can bill until they stop or time out.

## Inspect and interact

Helpers are pre-imported. Keep multi-step work in one heredoc when practical.

```bash
BU_NAME=r7k2 browse-dev <<'PY'
print(page_info())
print(js("document.title"))

fill_input('input[name="q"]', "browser automation")
press_key("Enter")
wait_for_load()

print(page_info())
PY
```

Useful helpers:

- Navigate: `new_tab(url)`, `goto_url(url)`, `wait_for_load()`
- Inspect: `page_info()`, `js(code)`, `cdp(method, ...)`
- Interact: `click_at_xy(x, y)`, `type_text(text)`, `fill_input(selector, text)`, `press_key(key)`, `scroll(x, y)`
- Tabs: `list_tabs()`, `switch_tab(target)`, `close_tab(target)`
- Files and proof: `capture_screenshot()`, `wait_for_element(selector)`

Prefer the accessibility tree for element discovery:

```python
nodes = cdp("Accessibility.getFullAXTree")["nodes"]
```

Use a targeted `js(...)` query when the accessibility tree lacks the element. Verify each action with `page_info()`, a focused DOM check, or a screenshot.

## Stop the browser

When the work is done, stop the exact named browser:

```bash
browse-dev <<'PY'
stop_remote_daemon("r7k2")
PY
```

Do not leave an unused remote browser running.

## Feedback

When your Browse Dev integration runs, or fails, send us one feedback message. Good or bad, every time. Line 1:
`kind: integration_report | feature_request | bug`. Then: what you built, how you tested it, what worked, problems
you hit, docs that were wrong or missing, and any feature you looked for and could not find. No keys, passwords or
customer data.

```bash
browse-dev feedback --category other "kind: integration_report
Built: ...
Tested: ...
Worked: ...
Problems: ...
Missing: ..."
```

`--category missing` for a feature_request, `bug` for a bug.
