# Contributor / coding-agent contract

Read README.md, docs/ARCHITECTURE.md, docs/NATIVE_SHAPER.md and docs/ROADMAP.md.

Do not claim a TeX-native shaper exists: v0.1 is an offline word cache. Do not
replace the native-glyph backend with screenshots, SVG paths, or PDF fragments.
Keep literal UTF-8 input and original logical-order ActualText. Reject unsupported
inputs and missing words, rather than printing unshaped approximations.

Font IDs are meaningful only within the exact SHA-256-identified font. Do not
normalize the original text before generating lookup keys. Do not equate
HarfBuzz clusters with safe line-break points. Keep all font files out of git.

The authoritative package source is tex/latex/bntex/bntex.sty; update its identical
wheel-resource copy at src/bntex/data/bntex.sty together (a test enforces equality).
Run PYTHONPATH=src python -m pytest -q. Integration tests must actually run before
claiming rendering support. Record skipped tests and untested platforms.

Never publish this repository, change visibility, upload to CTAN/PyPI, or enable
shell escape without a specific user request. CI must not use secrets on pull
requests. Do not make network calls while compiling a document.

## Experimental native-path addendum (issue #6)

The v0.1 cached contract above still applies to `bntex.sty` and `\bn`.
The separate `bntex-native.sty` / `\bnNative` implementation is now an opt-in,
fixed-profile native path. Read `docs/NATIVE-TEX.md` and its validation report
before changing it. Do not claim arbitrary-font or general-script support.

Keep each `bntex-native*.sty` / `.def` source identical to its wheel-resource copy.
The exporter may consume only a pinned font profile and font, never vocabulary.
Do not silently regenerate frozen glyph references. A new word must continue to
compile without a Python process, external shaper, network, or word cache.
Run `tests/test_native_tex.py` with integration and pinned-reference gates required.
The optional Linux chroot gate is a trusted capability test, not a security sandbox.
