# pyslop

Deterministic anti-slop toolkit for Python. Thin orchestrator over ruff, ty, and ast-grep with a vendored set of
evidence rules. Read `CONTEXT.md` for vocabulary and `docs/decisions.md` before changing architecture.

## Commands
- `uv sync` — install.
- `uv run pytest` — tests.
- `uv run ast-grep test -c rules/sgconfig.yml` — rule fixture tests.
- `uv run pyslop check <paths>` — run all engines, merged JSON with `--format json`.

## Conventions
- Python 3.12 floor. Ruff for lint and format, ty for types. This repo dogfoods its own rules.
- Every ast-grep rule ships with a fixture test. No rule without a test.
- Commit messages: Conventional Commits. No AI attribution trailers.

## Agent skills

### Issue tracker
GitHub issues on `zkewal/pyslop` via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels
Default five labels. See `docs/agents/triage-labels.md`.

### Domain docs
Single-context: `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.
