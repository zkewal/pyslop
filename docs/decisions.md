# Decisions and backlog

Design record: `~/Desktop/ho-repos/research-notes/python-anti-slop-toolkit-2026-09-07.md` (aligned design section).

## Decided
- Thin orchestrator over ruff, ty, ast-grep. No own AST walker.
- Rules are ast-grep YAML only. No pure-Python rule engine on day one.
- Type checker is ty. A consumer's mypy is untouched and runs as its own step.
- No baseline file. Existing violations are handled with per-path deviations carrying an issue link, removed one rule per PR.
- Autofix only for safe ruff rewrites. Never evidence rules.
- Private repo, git-tag versions, installed via `uv tool run --from git+https://github.com/zkewal/pyslop@<tag> pyslop`.
- Adoption correctness (v0.1.1): engines fail closed — an ast-grep crash,
  an empty/malformed payload (including rc 1 with `[]`), or ty
  diagnostics that do not parse are exit 2, never a silent green.
  Consumer ty config (`ty.toml` / `[tool.ty]`) is honored via ty's own
  `--project` discovery; with no consumer config only `--error all` is
  added and the floor comes natively from `requires-python` — no config
  file is ever forced, no PEP440 parsing in the runner. Engine deps are
  `==` pinned (tool installs ignore `uv.lock`, so only metadata pins
  reproduce). `[tool.pyslop] exclude` is single-matcher gitignore via
  pathspec (`!` reincludes; bad globs are loud and exclude nothing).
  Generated hook/workflow pins come from the installed pyslop release,
  never the consumer's git tags; generated `[tool.ty.rules]` carries no
  floor. Strict defaults are preserved because the bundled `[environment]`
  holds nothing but `python-version`, and `--error all` escalates every
  rule including post-pin additions.

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
