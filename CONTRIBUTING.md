# Contributing to BnTeX

> **Installed-distribution candidate:** the public `\usepackage{bntex}` now selects automatic input and the prebuilt default profile. The project-local compiler/staging commands below are maintainer/developer workflows, not ordinary author setup. The legacy cached entry is `bntex-cached` or `bntex[cached]`. See [docs/distribution/README.md](docs/distribution/README.md) for the current installation boundary and remaining restricted-read/Overleaf acceptance.

Use a branch based on current main and a PR with an exact supported scope.
Read AGENTS.md and the current README before historical design snapshots.

Required native correctness checks use the documented pinned environment:

```
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 python -m pytest -q
python tools/audit_release.py
```

Retain original Unicode, fixed font identity and frozen glyph runs. Every TeX
source/resource pair must stay identical. A skipped integration/reference test
is not passing typography evidence. Record complete CI separately from local
subsets. Keep benchmark input/budget identities and failures visible.

The cached frontend remains literal, not a general TeX parser. Explicit native
spans also reject input macros and unsupported styles. Current `bntex-auto`
authoring instead routes connected Bengali without language wrappers, while
leaving surrounding LaTeX commands alone. See `docs/AUTOMATIC-AUTHORING.md` for
issues #15/#25, real-bold support and opt-in synthetic slant. Check moving/PDF
arguments, scope restoration, command/word boundaries and original text extraction
whenever routing or rendering changes. Historical deferrals are not current tasks.

No font binaries, generated installation files, credentials or build trees may
be committed. Keep the original and third-party licenses intact. Public releases,
visibility changes and CTAN/PyPI uploads require separate authorization.
`docs/RELEASE-READINESS.json` records outstanding human/browser/performance and
distribution decisions; do not fill them in on another person's behalf.
