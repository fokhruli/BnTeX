# Executed UTF-8 decoder validation — 24 September 2026

This report covers issue #4's new TeX decoder and diagnostics, not a native shaper.
Source is proposed on `feat/pdftex-utf8`, based on PR #11 head
`0877465587bbc484efa02cf5bf8657ba90f868d4`. No merge or release was performed.

## Local execution

The exact new modules and tests were run with integration prerequisites mandatory.
The final local suite result was:

```text
BNTEX_REQUIRE_INTEGRATION=1 python -m pytest -q
137 passed in 28.02s
```

This local checkout consists of the original 41-test source-bundle baseline plus
**96 new decoder tests**. The live user inventory was restored with its Git blob
hash verified (`26061b4760c267bd89fe663dcee79486057d926b`). It is not a claim that
all 171 inherited live-branch tests were restored/run locally. Remote workflows
must test the complete proposed branch separately; do not infer their outcome.

Before edits the 41-test bundle baseline passed. With the earlier decoder revision
94 decoder tests passed independently; the final revision adds two paragraph
callback/input tests and is the one in the 137-test run above.

Environment: Python 3.13.5; pdfTeX 1.40.26 (TeX Live 2025/dev/Debian);
LaTeX2e 2024-11-01 patch level 2; expl3 2025-01-18. The negative-engine test uses
LuaHBTeX 1.18.0 before any document-class/font initialization. No Windows/macOS or
Overleaf browser execution is claimed.

The decoder compilations invoke the absolute engine path, set PATH to an empty
directory, require `\pdfshellescape=0`, use `-no-shell-escape -halt-on-error`,
and inspect the recorder file for absence of a word cache. The Python process
creates test inputs and checks outputs; it is not invoked by TeX.

## Coverage actually exercised

- All 256 single bytes and all 1920 valid two-byte sequences.
- Every possible second byte for E0, E1, ED, EF, F0, F1 and F4; every possible
  byte in three representative later-continuation positions.
- All rejection categories and first-error/start/EOF offsets; no partial decoded
  result survives failure, and a later successful call resets error state.
- Every scalar in U+0980..U+09FF as literal TeX input, including unassigned values
  at this encoding-only layer; all 261 user-inventory strings by both literal
  and exact hex transports with scalar, byte, length and offset equality.
- Nukta and split-vowel encoding distinctions; ZWJ, ZWNJ, BOM, supplementary
  scalars, noncharacters, empty input and NUL at the encoding layer.
- 384 deterministic random byte strings and 128 generated valid scalar strings.
- TeX command/active-token non-expansion, grouping, repeated module loading,
  paragraph callbacks, controlled paragraph-input rejection and coexistence with
  the unchanged cached `\bn` command.
- Acceptance at 4096 bytes and rejection at 4097 bytes through both transports.

Python's strict UTF-8 codec is the independent encoding reference. These tests do
not validate Bengali syllable formation, fonts, shaping rules or arbitrary text
layout. Invalid UTF-8 can be rejected before all bytes of its sequence arrive;
error positions follow the decoder's documented first-offending-byte convention.

## Stress-test and example fixes

An initial 16384-byte ceiling was too costly for the current sequence-building
implementation. The final ceiling is explicitly 4096 bytes per call and the tests
exercise that limit. A local hex-path timing probe (including engine launch and
text-result output) measured 0.232/0.246/0.460/1.248/4.670 seconds for
256/512/1024/2048/4096 ASCII bytes. These are single-run observations on this
container, not a speed guarantee or a linear-complexity claim.

The first example exposed xparse's non-long callback argument restriction when
success code contained `\par`. The final wrapper uses long arguments; success and
failure callbacks may contain paragraphs, while paragraph tokens in literal input
produce the controlled `non-literal` result. Dedicated tests cover both behaviors.

`examples/utf8-diagnostics.tex` compiled with pdfLaTeX and shell execution disabled.
Its one-page PDF was rendered with Poppler and visually inspected. It shows ASCII
scalar/offset/hex diagnostics and expected rejection, not Bengali font output.

A wheel built locally through `setuptools.build_meta.build_wheel` contains both
new modules byte-for-byte, and contains no .ttf/.otf files. This verifies resource
packaging in the local baseline, not a complete live-branch release audit. The
existing setuptools TOML-license deprecation warning was observed and is not
changed by this focused implementation.

## Human feedback

The maintainer's actual document-level acceptance of the earlier expanded-form
PDF is recorded in `reviews/2026-09-24-expanded-forms.md`, with the attachment hash.
No per-case approvals or invented reviewer comments were added to the old ledgers.

## Remaining boundaries

The decoder is deliberately a separately loadable developer module; `\bn` still
uses the existing cached backend. It preserves bytes delivered to its API, not
source characters discarded by TeX's mouth. It does not make arbitrary TeX input
safe or recover unbalanced source arguments that fail before the API is entered.
The resource ceiling is local to a call, not a sandbox for an entire TeX document.

Next: issue #5's typed fixed-font tables and independent shaping model, followed
by the TeX port/unseen-word gate in #6. No additional corpus mining or native
shaping was performed here. Remote CI results belong to actual PR run logs.
