# browse_dev.skills

The `browse-dev` agent skill and its installer, behind the `browse-dev skill` command:

- `browse-dev/SKILL.md`: the skill. It is the `SKILL.md` of the pinned browser-harness release under the Browse Dev
  name; `scripts/sync_browser_harness_skill.py` regenerates it and the repo copy in `skills/browse-dev/` from the
  installed harness. Bump the pin, `uv sync`, rerun the script.
- `browse_dev.py`: the renaming (name, description, OpenClaw install metadata).
- `install.py`: `browse-dev skill show` prints the skill. `browse-dev skill install` writes it to `~/.agents` and to
  each supported agent you have installed; `--target NAME` picks one, `--path DIR` a custom location.

The other skills (`cloud`, `open-source`, `qa`, `remote-browser`, `x402`) live in the repo's `skills/` directory.
