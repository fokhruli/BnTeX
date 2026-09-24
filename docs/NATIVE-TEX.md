# Native Bengali in pdfLaTeX — experimental fixed-profile path

## What is implemented

`bntex-native.sty` shapes Bengali inside **unmodified pdfTeX**. It consumes the
issue-4 UTF-8 decoder's scalar/byte mapping, applies the fixed Bengali grammar,
font-dependent reordering, GSUB and GPOS, and emits native embedded TrueType
font glyphs. There is no word dictionary, prepared-word lookup, Python invocation,
Lua invocation, network request or external shaper during compilation.

This is an **opt-in experimental path**, not a CTAN release or a generic OpenType
engine. The existing `bntex.sty` and `\bn` retain their cached contract. Use the
separate `\bnNative` command for the native implementation. Do not mix independently
generated cached and native font-bank directories: identical font-bank names can
have different prepared coverage and checksums.

The font-installation step uses Python, FontTools and `pltotf`. It receives only
an exact compiled profile and the matching font — never a document, corpus or
word list. It writes reusable ASCII rule tables and all three 256-slot font banks.
The final document needs only pdfLaTeX, the installation assets and ordinary LaTeX.

## Install once, then edit without preparation

On `feat/fixed-font-model` plus this change, install the project's Python/test
requirements and a TeX distribution. Supply your own installed font; no font
binaries or generated font profiles are redistributed with this source.

```bash
python -m pip install -e '.[test]' 'fonttools==4.63.0'

python -m bntex.native compile \
  --font /path/to/NotoSerifBengali-Regular.ttf \
  --out build/native-profile.json

python -m bntex.tex_export \
  --profile build/native-profile.json \
  --font /path/to/NotoSerifBengali-Regular.ttf \
  --out build/native-installation

cp examples/native-tex.tex build/native-installation/main.tex
cd build/native-installation
pdflatex -no-shell-escape -halt-on-error main.tex
```

Choose fresh output paths. The compiler/exporter refuses to overwrite existing
work. After installation, change the Bengali text in `main.tex` and run **only**
pdfLaTeX again. There is no cache-generation or missing-word discovery pass.
Changing the font, profile ABI or package implementation requires a matching new
installation; changing the document's vocabulary does not.

The generated directory contains the local original font, `.tfm`/`.enc` banks,
`bntex-native*.sty`/`.def`, `bntex-utf8.def`, the loader `bntex-native-profile.tex`,
and a provenance JSON. Do not selectively omit assets. The JSON is an installation
record and is not read by pdfTeX. A project-local Overleaf import should upload the
user-generated installation and select pdfLaTeX; browser validation remains separate.

## Document API

```latex
\documentclass[12pt]{article}
\usepackage{bntex-native}
\BnTeXNativeLoadProfile{bntex-native-profile.tex}
\begin{document}
English remains in the surrounding Latin font.
\par
\bnNative{শিক্ষকসম্মেলনের আলোচনায় নতুন প্রযুক্তি এসেছে।}
\end{document}
```

`\bnNative` accepts literal UTF-8 text and ordinary spaces. It shapes each word
independently, makes an unbreakable word box, and inserts stretchable interword
glue. It inherits point size and color. Only regular upright text is supported:
bold/italic requests fail explicitly instead of silently substituting regular.
Keep math and English outside the command. Headings, bookmarks, captions, Beamer,
TikZ, bibliography-generated text and global script switching are not certified.

The developer API `\BnTeXNativeShape{literal}` computes a complete glyph run without
rendering. `\BnTeXNativeShapeHex{hex}` accepts exact byte transport. `\BnTeXNativeDump`
prints seven integer fields per glyph:

```
gid | UTF-8-byte-cluster | x-advance | y-advance | x-offset | y-offset | flags
```

`\BnTeXNativeTraceOn` and `\BnTeXNativeTraceOff` enable/disable stage snapshots.
Snapshots show glyph IDs, clusters, ordering positions, feature masks and syllable
IDs; final positioned fields are available through the dump. These are developer
interfaces, not a stable public ABI. Inspect the implementation before using
internal arrays directly. Calls are sequential and the last run's state is global;
reentrant shaping is rejected. A fatal input error stops compilation.

## Profile identity and scope

| Property | Required value |
|---|---|
| Font | Exact static Noto Serif Bengali Regular |
| Font SHA-256 | `32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef` |
| Typed profile SHA-256 | `f6294540099a3b6f622f2cdd9e863050390f75fd0576495d5a2316903f8cfb42` |
| Selected system | `bng2` / default language, horizontal LTR |
| Font units per em | 1000 |
| Glyphs / banks | 640 / 3 |
| Layout lookup records | 59 GSUB, 6 GPOS |
| Native installation ABI | 1 |

The exporter serializes every required record from this closed profile. It emits
single/multiple substitutions, ordered ligatures, nested chaining-coverage rules,
lookup filtering, pair glyph/class adjustments and mark-to-base/mark attachments.
Dynamic conjoining-position and reph queries are computed from font rules, not
from a shaped example corpus. A DFA is compiled from the finite Bengali grammar;
it is not a trie of words. Only this exact font/profile is accepted.

The initial scalar domain includes the Bengali letters, the documented dependent
vowels/signs/nukta/virama, Bengali and ASCII digits, dotted circle, join controls,
and the punctuation explicitly listed in `tex_export.py`. It does **not** include
arbitrary Latin words, emoji or all characters using the Bengali script block.
The native path intentionally does not advertise the broader optional broken-run
mode of the Python development model. Isolated sign/fragment probes receive a
dotted circle as required by the tested policy; broken runs mixed with surrounding
text, repeated signs/nukta, consecutive join controls and noncanonical multiple
vowels are explicit errors. Ordinary SPACE is a separator, not a consonant base:
`SPACE + vowel sign` is rejected by the low-level whole-run interface.

## Runtime design

Stable integer node IDs retain contextual-target and ligature-component identity
while a separate order array changes during insertion, deletion and reordering.
The interpreter stores glyph ID, original scalar, byte cluster, script class,
ordering position, syllable, feature mask, ligation flags, advances/offsets,
attachment parent and component ownership. Numeric call arguments are evaluated
before entering a callee's scratch-variable group; this prevents aliasing when a
caller passes expressions involving the same scratch registers.

The stages are: decode original input; normalize a separate working sequence;
longest-prefix DFA syllables; initial font-dependent ordering; ordered/masked
GSUB; final ordering; GPOS and attachment resolution; default-ignorable handling;
cluster flags; positioned native glyph output. The original input is never
replaced with its normalized form. Word `/ActualText` uses original logical-order
UTF-16BE, including original nukta encodings and join controls.

Substitutions are not unconditional character replacements. Contexts retain
backtrack/lookahead, filtering and ordered actions. Stable target IDs survive
nested substitutions. Component ownership prevents unrelated attached marks from
being combined incorrectly. Cluster flags are recomputed when ordering/ligation
merges clusters. A cluster boundary is not used as permission to break a word.

The renderer uses the existing glyph-bank convention `bank=floor(gid/256)` and
`slot=gid mod 256`, and the same explicit positioning equations as the cached
backend. Natural TFM rounding does not control shaped word advances. Point
conversion is performed at runtime; word height/depth follow positioned bounds.

## Bounds and trust

The existing decoder enforces 4096 input bytes per call; `\bnNative` also validates
the entire literal span before splitting it. A syllable is limited to 64 working
scalars. Node/glyph storage is capped at 8192 entries, contextual recursion at 32,
lookup work at 2,000,000 charged operations, and trace output at 200,000 node cells.
These finite limits do not imply book-length performance or a sandbox for arbitrary
TeX. Long-document timing and memory still need separate profiling.

The literal API sees the input after TeX's mouth: comments, repeated-space folding,
`^^` processing and ignored source characters cannot be reconstructed. Exact byte
transport is available through the hexadecimal API. User input macros are not
expanded by the decoder.

Installation SHA-256 records and loader MD5 checks detect accidental asset drift.
The loader and `.def` files are trusted executable TeX, not authenticated/signed
data or a security boundary against a coordinated rewrite. Do not run arbitrary
TeX as a privileged user. The optional chroot test below accepts only trusted
installations and is not advertised as an untrusted-input security sandbox.

## Testing and the unseen-word gate

```bash
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 \
  python -m pytest -q tests/test_native_tex.py
```

Provide the pinned HarfBuzz 10.2.0 reference environment for the mandatory live
comparisons. Frozen inventory tests execute without invoking HarfBuzz; they read
unchanged repository glyph fixtures. In a different reference environment, those
live comparisons explicitly skip unless the mandatory-oracle switch requests an
error. A precompiled exact JSON may be supplied through `BNTEX_NATIVE_PROFILE_JSON`;
its bytes must match the same profile hash. This is not a vocabulary input.

Every ordinary test engine runs with shell execution disabled, an empty executable
search path, and a `.fls` audit excluding Python/corpus/cache input. The stronger
optional Linux gate copies only the installed assets, observed LaTeX dependencies,
pdfTeX and its shared libraries into a temporary root, then introduces new text:

```bash
# Requires CAP_SYS_CHROOT; use only with your own trusted generated installation.
PYTHONPATH=src python tools/native_chroot_gate.py \
  --installation build/native-installation \
  --font /path/to/NotoSerifBengali-Regular.ttf \
  --out build/native-isolation-proof
```

The reference runs outside that root only after pdfTeX exits. The test preserves
only a PDF and an evidence JSON in the result directory; the temporary root,
including its font copies, is removed. See `NATIVE-TEX-VALIDATION.md` for executed
results, not just the existence of this test script.

## Attribution and remaining work

The script/lookup algorithms adapt the issue-5 model and HarfBuzz 10.2.0's open
Indic implementation. Independent execution is not a claim of inventing a new
shaping algorithm. Preserve `THIRD-PARTY-NOTICES.md` with any distribution.
Primary specifications: [Bengali shaping](https://learn.microsoft.com/en-us/typography/script-development/bengali),
[OpenType layout](https://learn.microsoft.com/en-us/typography/opentype/spec/chapter2),
and [HarfBuzz 10.2.0 Indic source](https://github.com/harfbuzz/harfbuzz/blob/10.2.0/src/hb-ot-shaper-indic.cc).

Next work is real-document/Overleaf validation, performance profiling, moving
arguments/PDF strings and additional reviewed font styles — not another word cache.
Poppler extraction is tested; complete tagged-PDF accessibility and all-reader
behavior are not. New native-output typography review remains distinct from the
maintainer's earlier review of the matching HarfBuzz reference forms.
