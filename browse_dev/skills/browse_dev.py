"""Browse Dev skill alias for Browser Harness"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

# Skill description agents see before deciding to open the skill. Name the hosted-browse dev case so
# agents writing agent code (browse-dev library, Playwright, Puppeteer, CDP) open it too.
SKILL_DESCRIPTION = (
	'Direct browser control via CDP for web interaction: automation, scraping, testing, screenshots, and site/app work. '
	'Also covers hosted cloud browsers for AI agents: the browse-dev Python library (Browser()), '
	'Playwright, Puppeteer or any CDP client.'
)

# Browse Dev-only frontmatter added while generating both checked-in SKILL.md copies.
# Keep this as the source of truth; scripts/sync_browser_harness_skill.py verifies the outputs.
OPENCLAW_METADATA_LINES = (
	'metadata:',
	'  {',
	'    "openclaw":',
	'      {',
	'        "requires": { "bins": ["browse-dev"] },',
	'        "install":',
	'          [',
	'            {',
	'              "id": "uv",',
	'              "kind": "uv",',
	'              "package": "browse-dev",',
	'              "bins": ["browse-dev"],',
	'              "label": "Install Browse Dev CLI (uv)",',
	'            },',
	'          ],',
	'      },',
	'  }',
)
# The Browse Dev-only Feedback section, added before Gotchas while generating both SKILL.md copies. It replaces a
# Feedback section the harness skill has: that one sends without the browse-dev CLI.
FEEDBACK_SECTION = """## Feedback

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

`--category missing` for a feature_request, `--category bug` for a bug. Integrations on the Cloud API or SDK (Agents
API, cloud browsers without this CLI) send it to the Cloud instead:

```bash
curl -s -X POST https://api.browser-use.com/api/v4/feedback \\
  -H "X-Browser-Use-API-Key: $BROWSE_DEV_API_KEY" -H "Content-Type: application/json" \\
  -d '{"message":"kind: integration_report\\nBuilt: ...\\nTested: ...\\nWorked: ...\\nProblems: ...\\nMissing: ..."}'
```
"""
_HARNESS_FEEDBACK = re.compile(r'\n## Feedback\n.*?(?=\n## |\Z)', re.DOTALL)

HARNESS_INSTALL_LINK = 'read https://github.com/browser-use/browser-harness/blob/main/install.md'  # the sentence's period follows
SETUP_HELP = 'run `browse-dev --doctor` and follow its output and the error message'


def as_browse_dev_skill(text: str) -> str:
	"""Expose the Browser Harness skill under the Browse Dev skill identity."""
	if not text.startswith('---\n'):
		return text

	try:
		_, frontmatter, body = text.split('---\n', 2)
	except ValueError:
		return text

	lines = []
	saw_name = False
	saw_description = False
	for line in frontmatter.splitlines():
		if line.startswith('name:'):
			lines.append('name: browse-dev')
			saw_name = True
		elif line.startswith('description:'):
			lines.append(f'description: "{SKILL_DESCRIPTION}"')
			saw_description = True
		else:
			lines.append(line)

	if not saw_name:
		lines.insert(0, 'name: browse-dev')
	if not saw_description:
		lines.insert(1, f'description: "{SKILL_DESCRIPTION}"')
	if not any(line.startswith('homepage:') for line in lines):
		lines.append('homepage: https://browser-use.com')
	if not any(line.startswith('metadata:') for line in lines):
		lines.extend(OPENCLAW_METADATA_LINES)

	body = body.replace('# browser-harness', '# Browse Dev', 1).replace('# Browser Harness', '# Browse Dev', 1)
	# browser-harness's install.md installs and runs `browser-harness`, which `uv tool install browse-dev` does not provide
	body = body.replace(HARNESS_INSTALL_LINK, SETUP_HELP)
	# Rebrand every mention except repo URLs (github.com/browser-use/browser-harness/...)
	body = re.sub(r'(?<!/)browser-harness', 'browse-dev', body)
	body = body.replace('Browser Harness', 'Browse Dev')
	body = _HARNESS_FEEDBACK.sub('', body)
	if '\n## Gotchas\n' in body:
		body = body.replace('\n## Gotchas\n', f'\n{FEEDBACK_SECTION}\n## Gotchas\n', 1)
	else:
		body = f'{body.rstrip()}\n\n{FEEDBACK_SECTION}'
	frontmatter_text = '\n'.join(lines)
	return f'---\n{frontmatter_text}\n---\n{body}'


def skill_text() -> str:
	"""Return the canonical Browse Dev skill."""
	skill_path = Path(__file__).resolve().parent / 'browse-dev' / 'SKILL.md'
	if skill_path.exists():
		return skill_path.read_text(encoding='utf-8')

	try:
		text = resources.files('browser_harness').joinpath('SKILL.md').read_text(encoding='utf-8')
	except ModuleNotFoundError as exc:
		raise RuntimeError(
			'The Browse Dev skill relies on the browser-harness package. Install browse-dev again: uv tool install --force browse-dev'
		) from exc
	return as_browse_dev_skill(text)
