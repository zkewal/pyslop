# pyslop init

`pyslop init [path]` (default: current directory) adopts a repo in one command:

1. Copies the bundled rules to `tools/pyslop/rules/`. The copy belongs to the
   consumer repo from then on — edit messages, severities, or patterns freely.
2. Merges `[tool.pyslop]`, `[tool.ruff]` (curated set, see `config/ruff.md`),
   and `[tool.ty]` (strict, see `config/ty.md`) into `pyproject.toml`
   (created if missing). `[tool.mypy]` is never touched.
3. Adds a `pyslop` hook to `.pre-commit-config.yaml` (created if missing).
   The hook runs `pyslop check --no-ty` on staged files; ty stays a CI job.
4. Writes `.github/workflows/pyslop.yml`, pinning
   `uv tool run --from git+https://github.com/zkewal/pyslop@<rev> pyslop`,
   where `<rev>` is this repo's `git describe --tags`, else `main`.
   pyslop is private: the runner needs read access (a fine-grained PAT).

Existing keys are never overwritten: anything already present (a custom
`[tool.ruff]`, an existing hook or workflow) is reported and skipped, and
re-running `init` is a no-op.
