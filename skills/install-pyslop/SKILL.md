---
name: install-pyslop
description: Adopt pyslop in a repo — run pyslop init, review the diff, run check, summarise findings.
---

## Adopt pyslop in a repo

The repo must have `uv` and a Python >= 3.12. pyslop itself is invoked
without installing anything:

```bash
uvx --from git+https://github.com/zkewal/pyslop@v0.1.6 pyslop init
```

Then follow these steps exactly:

1. **Run `pyslop init`** in the repo root. It vendors the rules to
   `tools/pyslop/rules/`, merges `[tool.pyslop]` / `[tool.ruff]` / `[tool.ty]`
   into `pyproject.toml` (never overwriting existing keys), and adds a
   pre-commit hook plus a CI workflow. Re-running is a no-op.
2. **Review the diff.** Run `git status` and `git diff`. Confirm no existing
   `[tool.ruff]`, `[tool.ty]`, `[tool.mypy]`, hook, or workflow was
   overwritten — `init` reports anything it skips. Summarise every file it
   added or changed.
3. **Run `pyslop check`** (text output for you, `--format json` if you are
   scripting fixes). Summarise the findings grouped by rule: how many, of
   which rules, in which files.
4. **Do not fix everything at once.** Adoption order is one rule per PR:
   SAFETY comments and swallowed exceptions first, `Any` removal last.
   For each finding either fix the code, add the required `# SAFETY: <reason>`
   justification, or record a reasoned deviation (reason + issue URL on the
   line above the override) and move on.
