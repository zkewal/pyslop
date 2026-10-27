# 0001 — Aligned design

Status: accepted (2026-09-10). Later refinements live in `docs/decisions.md`.

## Scope
- Evidence-based rules only: structural checks. No wording or comment-text
  heuristics, no prose linting.
- `Any` is forbidden unless no alternative exists, and then needs
  `# SAFETY: <reason>`.
- Agent-first consumer (JSON, stable ids, fix hints); humans get the same output.

## Architecture
- Thin orchestrator over ruff (lint + format), ty (types), and ast-grep
  (custom rules). No own AST walker: each engine already does its job well,
  and a fourth parser is code nobody wants to maintain.
- Engine and CLI are one versioned package. The rule set is vendored into
  `tools/pyslop/` in each consumer repo, owned and edited there, so a team
  can tune messages and severities without forking pyslop.
- No pure-Python fallback engine on day one. A rule that needs scope or
  dataflow YAML cannot express goes to Fixit (LibCST); see `docs/decisions.md`.
- One merged finding schema:
  `{engine, rule, file, line, col, message, fix_hint, severity}`.
- Rule ids are kebab-case and namespaced `pyslop/<name>`; ruff and ty keep
  their native codes and the `engine` field disambiguates.

## Rules
Day-one custom rules, each an ast-grep YAML with a fixture test:
`swallowed-exception`, `require-safety-comment`, `no-blanket-ignore`,
`no-isinstance-ladder`, `no-dynamic-attr-on-literal`, `no-kwargs-passthrough`,
`no-dict-any`, `no-module-mocking`.

Skipped: `no-optional-as-error` (too many false positives) and
`single-impl-abc` (cross-file; backlog). Not ported from anti-slop: perf rules
(ruff PERF/C4 cover them), readable-spacing (ruff format covers it), and
Effect-specific rules.

## Engines
- ruff: curated select, pinned version, preview off, `ruff format` instead of
  black. The selected families are in `docs/config/ruff.md`.
- ty: pyslop's type checker, strict rules shipped, version pinned by pyslop.
  A consumer's own mypy is left untouched and runs as its own step. Known
  limits: ty is beta and has no plugin system, so Django and SQLAlchemy
  stubs do not work; pydantic and FastAPI do.

## Config
`[tool.pyslop]` holds exactly `rules` (severity overrides) and `exclude`.
ruff and ty are configured in their own sections. Any override that turns a
rule off for a path must carry a comment with a reason and an issue link,
or it is itself a finding.

## Autofix
`--fix` applies only safe ruff rewrites (isort, pyupgrade). Evidence rules are
never autofixed: the fix for slop is a decision, not a rewrite.

## Consumption
- A pre-commit hook plus a GitHub Actions step. No editor or agent hook on
  day one.
- `pyslop init` copies the rules, writes the config blocks, and adds the hook
  and CI step. The `install-pyslop` agent skill wraps `init` and reviews the
  diff.
- Distributed as git-tag versions installed with `uv tool run --from
  git+https://github.com/zkewal/pyslop@<tag> pyslop`. PyPI later.
- Python floor 3.12, for the toolkit and its `target-version`.

## Rollout
- Monorepo: one vendored rule copy at the repo root, one `[tool.pyslop]` per
  `pyproject.toml`.
- Adopt one rule per PR: fix every violation for that rule, merge, move on.
  Order: `require-safety-comment`, `swallowed-exception`, `no-blanket-ignore`,
  `no-dynamic-attr-on-literal`, `no-module-mocking`, `no-isinstance-ladder`,
  `no-kwargs-passthrough`, `no-dict-any`, then ANN401 / `Any` removal last.
