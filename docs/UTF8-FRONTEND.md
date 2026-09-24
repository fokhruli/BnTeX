# Native UTF-8 front end (issue #4)

**Implemented: Unicode decoding inside pdfTeX. Not implemented: native Bengali
shaping.** The current `bntex.sty` and `\bn` cached-rendering contract are unchanged.
Use this separately loadable module to develop the future native shaper; merely
loading it does not make uncached Bengali text typeset correctly.

## Quick diagnostic example

Make `bntex-utf8.sty` and `bntex-utf8.def` available to TeX (both are in
`tex/latex/bntex/`), then compile `examples/utf8-diagnostics.tex` with pdfLaTeX:

```bash
TEXINPUTS="$PWD/tex/latex/bntex:" \
  pdflatex -no-shell-escape -halt-on-error examples/utf8-diagnostics.tex
```

The example has no Bengali font or cache dependency. It writes decoded results to
the log and prints an ASCII diagnostic page, not shaped Bengali. In Overleaf these
two files can be uploaded alongside the example, with pdfLaTeX selected; that
browser workflow has not been executed in this milestone.

```latex
\usepackage{bntex-utf8}
\BnTeXDecodeUTFviii{ক্ষ}
  {\typeout{Scalars: \BnTeXUTFviiiScalars}
   \typeout{Offsets: \BnTeXUTFviiiOffsets}
   \typeout{Bytes: \BnTeXUTFviiiHex}}
  {\typeout{Error: \BnTeXUTFviiiError}}
```

Expected output:

```text
Scalars: 2453,2509,2487
Offsets: 0,3,6
Bytes: E0A695E0A78DE0A6B7
```

These are U+0995, U+09CD and U+09B7, in logical order. This example does not join
those letters or select any font glyphs.

## Contract and API

The implementation is an expl3 finite-state UTF-8 decoder following the byte
constraints of RFC 3629 section 4 [1]. It does not use a Python/Lua subprocess,
HarfBuzz, a font, a vocabulary cache, or network access during compilation.

The low-level entry points, available after `\input{bntex-utf8.def}`, are:

```latex
\bntex_utfviii_decode:nTF {literal tokens} {success code} {failure code}
\bntex_utfviii_decode_hex:nTF {ASCII hex} {success code} {failure code}
```

Both also provide `:nT` and `:nF` forms. Use them inside `\ExplSyntaxOn`. The
`bntex-utf8.sty` wrapper exports the corresponding commands
`\BnTeXDecodeUTFviii` and `\BnTeXDecodeUTFviiiHex`, each with three arguments.
`\BnTeXRequireUTFviii{literal}` instead emits a package error on failure; use
`-halt-on-error` when failure must stop a build.

| Result | Internal variable | Expandable wrapper |
| --- | --- | --- |
| Original octets as decimal integers | `\l_bntex_utfviii_bytes_seq` | none |
| Original octets as uppercase hex | `\l_bntex_utfviii_hex_tl` | `\BnTeXUTFviiiHex` |
| Unicode scalars, decimal | `\l_bntex_utfviii_scalars_seq` | `\BnTeXUTFviiiScalars` |
| Scalar start offsets, bytes | `\l_bntex_utfviii_offsets_seq` | `\BnTeXUTFviiiOffsets` |
| Scalar byte lengths | `\l_bntex_utfviii_lengths_seq` | `\BnTeXUTFviiiLengths` |
| Error code, empty on success | `\l_bntex_utfviii_error_str` | `\BnTeXUTFviiiError` |
| Offending byte/EOF offset | `\l_bntex_utfviii_error_offset_int` | `\BnTeXUTFviiiErrorOffset` |
| Start of failing sequence | `\l_bntex_utfviii_error_start_int` | `\BnTeXUTFviiiErrorStart` |

Wrappers for sequences expand to comma-separated decimal numbers. Offsets are
zero-based. Both error offsets are -1 on success. Results belong to the current
TeX group and are overwritten by the next call, including a failed call. Group
nested calls or copy their results; these are scratch results, not persistent
per-document storage. No global category-code changes are made. Loading the
module does not change `\bn` or the document's Latin fonts.

### The important source boundary

The literal API preserves the byte values of the tokens delivered **after TeX's
mouth has processed the source**. It cannot recover comments, collapsed spaces,
removed end-of-line whitespace, `^^` source transformations, or ignored source
characters. Its byte offsets are argument offsets, not original file offsets.

Ordinary letter, other-character and space tokens are accepted. High-byte active
tokens created by LaTeX UTF-8 input handling are read as data without expansion.
Control sequences, group tokens, math/alignment/parameter/super/subscript tokens,
and active ASCII characters are rejected as `non-literal`. A macro whose expansion
would be Bengali is deliberately not expanded. An outer macro may explicitly
pass an already-expanded, trusted token list; that expansion is the caller's job.

For an exact byte transport, including malformed UTF-8 or bytes TeX's mouth would
change, use the hex API. Hex must be contiguous, even-length ASCII hexadecimal;
uppercase and lowercase are accepted, spaces and a `0x` prefix are not. This API
is useful for testing and future safe data transport, not the normal authoring UI.

The decoder does not normalize: precomposed/decomposed nukta strings, split vowel
encodings, ZWJ, ZWNJ and U+FEFF remain distinct exactly as delivered. Empty input,
NUL, unassigned scalars and noncharacters are valid at this **encoding** layer [1].
The renderer/shaper must apply its own supported-input policy; for example the
current HarfBuzz adapter rejects empty/NUL runs. Valid Unicode does not imply
font coverage, valid Bengali orthography, or a legal line break.

### Failure semantics

| Error code | Meaning |
| --- | --- |
| `stray-continuation` | A continuation byte appeared where a lead was required |
| `overlong` | C0/C1 or an E0/F0 continuation range would permit an overlong encoding |
| `bad-continuation` | A required continuation is outside 80..BF |
| `surrogate` | ED followed by A0..BF would encode a surrogate |
| `out-of-range` | F4 followed by 90..BF, or lead F5..F7, exceeds U+10FFFF |
| `invalid-lead` | F8..FF is not a permitted lead |
| `truncated` | Input ended while more continuation bytes were required |
| `non-literal` | TeX syntax rather than an accepted literal token |
| `hex-syntax` | Invalid/odd ASCII hex transport |
| `input-too-long` | The documented byte/hex limit was exceeded |

The first decoding error wins. For truncation the error offset is the byte count
(EOF), and the sequence start points to its lead. Transport validation precedes
UTF-8 validation. For hex-syntax errors, the offset is the offending byte-pair
index, not a TeX source character column. A size error uses -1 for both offsets.

Failure clears **all** decoded scalars, offsets and lengths: a valid prefix must
never look like successfully decoded complete input. Complete original byte/hex
outputs remain available after a UTF-8 error. Transport/size failures instead clear
byte/hex outputs too, since no complete accepted byte argument was constructed.
No replacement characters are inserted and invalid suffixes are not discarded.
Diagnostics generated by this module use fixed ASCII codes and numeric offsets;
TeX itself may also display its normal source-line error context.

## Resource ceiling

Each call accepts at most **4096 bytes** (or 8192 hex digits), enforced before
building the decoder's sequences. This is a word/run-level prototype ceiling,
not a paragraph limit imposed by UTF-8. No input is truncated to fit. Split larger
text at a higher, explicitly designed layout layer. Do not raise this constant
without profiling: the current expl3 sequence construction is not claimed to be
linear-time and repeated appends become expensive on long runs. An initial
16384-byte ceiling was reduced after local stress testing exposed excessive cost.

The fixed limit bounds this module's work; it cannot bound memory already consumed
while TeX tokenizes an arbitrarily large source argument. The test harness also
sets a 60-second timeout per engine invocation. A future streaming front end and
compact table storage should be measured separately before paragraph integration.

## Validation and distribution

Run the actual TeX integration tests:

```bash
BNTEX_REQUIRE_INTEGRATION=1 PYTHONPATH=src \
  python -m pytest -q tests/test_utf8_frontend.py
```

The Python harness uses Python's strict UTF-8 codec as an independent encoding
reference. It calls the absolute pdfLaTeX executable with shell execution disabled
and an otherwise empty PATH, and verifies the recorded input list has no word
cache. It checks all 256 single octets, all 1920 valid two-byte sequences, all 256
second-byte values for seven constrained/representative lead bytes, all 256 values
in three later-tail contexts, exact error offsets, truncation lengths, the entire
Bengali block, the 261 supplied inventory strings by both APIs, canonical/join
control preservation, deterministic fuzz cases, TeX-token non-expansion, scope,
resource boundaries, a wrong-engine diagnostic and renderer coexistence.

This is systematic finite testing, not exhaustive testing of every Unicode string.
The full inherited repository suite and both reference oracles must still pass on
the PR. See `UTF8-VALIDATION.md` for executed local evidence; remote status must be
read from the actual workflow runs.

The authoritative modules live under `tex/latex/bntex/`; their identical copies in
`src/bntex/data/` are wheel resources. Package metadata now includes `data/*.def`.
The existing `prepare` command does not automatically copy these optional modules
into a cached build directory; install them in TeX's search path or copy the pair
explicitly. They are not yet wired into `\bn` and cannot remove preparation alone.

## Next dependency

Proceed to issue #5's typed fixed-font tables and independent shaping model. The
model will consume these original scalars/byte offsets, create separate working
normalization state, and eventually emit the existing positioned glyph-run IR.
Do not feed a font glyph ID into this UTF-8 decoder or infer a glyph from a scalar
without the required Bengali shaping stages. Issue #6 remains the later
unseen-word/no-cache gate.

## Primary references

1. RFC 3629, UTF-8, sections 3-4: https://www.rfc-editor.org/rfc/rfc3629.html
2. LaTeX Project, public token-analysis API:
   https://github.com/latex3/latex3/blob/main/l3kernel/l3tl-analysis.dtx
3. LaTeX Project, public string mapping API:
   https://github.com/latex3/latex3/blob/main/l3kernel/l3str.dtx
4. Project contract: `NATIVE_SHAPER.md` section C and issue #4.

This is original BnTeX code using the public expl3 interfaces; no kernel
implementation or font data is copied into the module.
