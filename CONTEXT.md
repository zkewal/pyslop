# pyslop — glossary

- **slop**: code that fakes certainty, discards type evidence, or dodges the type system. Not a style complaint.
- **evidence**: a concrete type or value the checker can verify. `Any`, `cast`, and `type: ignore` destroy evidence.
- **escape hatch**: `cast()`, `# type: ignore[...]`, `# ty: ignore[...]`, explicit `Any`. Allowed only with a SAFETY comment.
- **SAFETY comment**: `# SAFETY: <reason>` on the same or previous line as an escape hatch. The reason is mandatory.
- **engine**: one of the three tools pyslop drives: `ruff` (lint + format), `ty` (types), `ast-grep` (custom rules). pyslop has no engine of its own.
- **rule**: one ast-grep YAML file under the vendored rules directory, id `pyslop/<kebab-name>`, with a fixture test.
- **vendored rules**: the copy of the rule set living in a consumer repo at `tools/pyslop/`. Owned and edited by that repo.
- **finding**: one violation in the merged JSON output: `{engine, rule, file, line, col, message, fix_hint, severity}`.
- **deviation**: a config override that turns a rule off for a path. Must carry a reason and an issue link.
- **init**: `pyslop init`, the command that vendors rules and writes config blocks, pre-commit hook, and CI step into a consumer repo.
