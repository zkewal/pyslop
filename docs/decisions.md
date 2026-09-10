# Decisions and backlog

Design record: `~/Desktop/ho-repos/research-notes/python-anti-slop-toolkit-2026-09-07.md` (aligned design section).

## Decided
- Thin orchestrator over ruff, ty, ast-grep. No own AST walker.
- Rules are ast-grep YAML only. No pure-Python rule engine on day one.
- Type checker is ty. A consumer's mypy is untouched and runs as its own step.
- No baseline file. Existing violations are handled with per-path deviations carrying an issue link, removed one rule per PR.
- Autofix only for safe ruff rewrites. Never evidence rules.
- Private repo, git-tag versions, installed via `uv tool run --from git+https://github.com/zkewal/pyslop@<tag> pyslop`.

## When you hit a rule ast-grep YAML cannot express
If a rule needs scope resolution or dataflow (e.g. "is this name ever re-raised anywhere in the function"),
do NOT write an ad-hoc `ast` script. Add Fixit (LibCST) as the second rule engine:
`uv add fixit`, put rules under `rules/fixit/`, register in `[tool.fixit]`, and have the runner
call `fixit lint` and map its output into the merged finding schema. Record the first such rule here.

## Backlog (deliberately not now)
- Baseline file keyed by rule + file + content hash.
- `single-impl-abc` cross-file rule (needs Fixit or a whole-repo pass).
- Claude Code PostToolUse hook: ruff + ast-grep only, must finish under 2s on a handful of files.
- Public PyPI publish.
