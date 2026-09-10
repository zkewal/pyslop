# pyslop

Deterministic anti-slop for Python. A thin runner over [ruff](https://docs.astral.sh/ruff/), [ty](https://docs.astral.sh/ty/),
and [ast-grep](https://ast-grep.github.io/) plus a vendored set of evidence rules, in the spirit of
[dmmulroy/anti-slop](https://github.com/dmmulroy/anti-slop).

Slop is code that fakes certainty or throws away type evidence: `Any`, bare `cast`, unjustified `type: ignore`,
`except` blocks that swallow, `isinstance` ladders instead of boundary parsing. pyslop makes each of those an error
unless it carries a `# SAFETY: <reason>` comment.

Status: pre-alpha.
