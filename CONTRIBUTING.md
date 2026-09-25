# Contributing to BnTeX

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

The cached frontend remains literal, not a general TeX parser. The native
frontend also rejects input macros and unsupported styles. Automatic Bengali
routing is deferred under #15. Check headings/PDF strings, scope restoration,
word boundaries and original text extraction whenever rendering is changed.

No font binaries, generated installation files, credentials or build trees may
be committed. Keep the original and third-party licenses intact. Public releases,
visibility changes and CTAN/PyPI uploads require separate authorization.
`docs/RELEASE-READINESS.json` records outstanding human/browser/performance and
distribution decisions; do not fill them in on another person's behalf.
