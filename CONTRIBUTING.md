# Contributing to BnTeX

Development home: `fokhruli/BnTeX` (private). Use topic branches and pull requests;
do not push development changes directly to main. Do not change visibility,
create releases or upload to CTAN/PyPI as part of ordinary development.

Read AGENTS.md, docs/ARCHITECTURE.md, docs/NATIVE_SHAPER.md and docs/PROFILE_AUDIT.md.
Install dependencies from README, then run:

```bash
BNTEX_REQUIRE_INTEGRATION=1 PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python tools/compare_reference.py --font /path/to/static-bengali.ttf
python tools/audit_release.py
```

A missing font/TeX prerequisite must fail the release gate, not silently skip the
rendering checks. Keep tests small and deterministic. Record actual tool versions,
font hashes and executed results; a CI definition is not a passing CI run.

## Review checklist

Add a failing regression test before fixing a bug. Preserve original Unicode,
font identity and text extraction. Keep both copies of bntex.sty identical. Never
commit font binaries, generated word caches, credentials or local build trees.
Do not claim native shaping from cached HarfBuzz output or structural font audits.

SourceError columns are 1-based Unicode scalar counts in decoded source, not byte
offsets or visual glyph positions. A caret is approximate for combining scripts.
The scanner remains deliberately literal; it is not a general TeX parser.

The next priority is a pinned, native-speaker-reviewed corpus (#3), followed by
the typed font-profile IR and Python shaping model (#5). The UTF-8 front end (#4)
can be developed independently. The final unseen-word gate belongs to #6.
