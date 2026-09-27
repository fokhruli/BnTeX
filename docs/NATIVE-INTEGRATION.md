# Native document integration: issue #7

This guide documents the explicit-command integration path introduced by PR #14
and #16; its measured examples retain that scope. Current ordinary authoring
uses `bntex-auto`, without Bengali-specific wrappers. See
[AUTOMATIC-AUTHORING.md](AUTOMATIC-AUTHORING.md) for automatic routing, audited
real bold and explicitly enabled synthetic slant. Issues #15 and #25 are active,
not deferred. Neither interface implies a public release or Overleaf certification.

## Authoring interfaces

For the explicit-only interface shown here, body text uses `\bnNative{...}`.
That wrapper is optional when using `bntex-auto`. The integration package
adds a declaration for text that will travel through headings, auxiliary files,
or PDF strings. It stores ORIGINAL TEXT, not prepared glyphs or a word cache.
Each typesetting use still reaches the native shaper (or optional process-local
memoization). Body words do not have to be declared.

```latex
\usepackage{bntex-native-integration}
\usepackage{bntex-native-memo} % Optional; omit to shape every occurrence.
\BnTeXNativeLoadProfile{bntex-native-profile.tex}
\usepackage[unicode=true,pdfencoding=unicode]{hyperref}
\BnTeXNativeDeclareText{intro}{ভূমিকা ও গবেষণা}
\BnTeXNativeDeclareText{title}{বাংলায় গবেষণা-নথির উদাহরণ}
\hypersetup{pdftitle={\BnTeXNativeText{title}}}

% In the document:
\section{\BnTeXNativeRegularText{intro}}
\bnNative{এখানে আগে ব্যবহার করা হয়নি এমন নতুন শব্দও লেখা যাবে।}
```

`\BnTeXNativeText{key}` inherits the supported size/weight/shape. It does not
silently replace bold or italic. `\BnTeXNativeRegularText{key}` explicitly selects
medium upright Bengali locally; use it when the document class normally makes
headings bold. Surrounding Latin styling is restored afterward. This is NOT
Bengali bold support by itself; the separate authoring family supplies real bold.
Keys are 1--64 ASCII letters/digits/hyphens, starting with
a letter. Duplicate/unknown keys and input macros are errors.

Declaration validates literal UTF-8, not arbitrary linguistic correctness. The
native shaper checks its supported domain when text is typeset. Declare in the
preamble before use. With hyperref, the hook substitutes a scalar-derived list
of `\unichar` commands in PDF-string conversion. Both package loading orders are
tested. Original nukta encodings and ZWJ/ZWNJ are preserved: the typeset working
sequence is not reused as the logical bookmark/metadata string. Tests inspect
actual PDF outlines and metadata using pypdf, not only the `.out` source.

A bare `\bnNative` inside a PDF string remains outside this interface. Do not
remove the declarations and assume that hyperref can expand the shaping engine.
No tagged-PDF structure, PDF/UA compliance, or all-viewer search behavior is implied.

## Optional bounded in-memory reuse

The first 200-token repeated-text probe took about 21 seconds without reuse, so
`bntex-native-memo.sty` is an opt-in optimization. It stores only successful
positioned glyph runs in font units, keyed by exact ORIGINAL UTF-8 bytes plus
full font identity when the style module is loaded. It does not store rendered
boxes, point sizes, colors, normalized spellings or persistent files. The original
regular-only loader supports one profile; the authoring exporter installs the
separately audited regular/bold pair. Current size, color and any explicitly
requested slant are applied by the renderer on every use.

Controls: `\BnTeXNativeMemoOn`, `\BnTeXNativeMemoOff`,
`\BnTeXNativeMemoClear`, `\BnTeXNativeMemoLimit{1..256}`, and
`\BnTeXNativeMemoStats`. Loading the optional package enables it. Turning it off
clears stored entries. The limit is at most 256 entries and 8192 stored glyphs;
a run exceeding 128 glyphs is shaped but not stored. Reaching a limit clears the
bounded cache instead of allowing unbounded growth. The next new word is shaped
normally. No memo file is written or read across TeX processes.

The cache stores the final seven-field glyph projection and original text,
not full intermediate syllable/ligature state. Developer `\BnTeXNativeShape`
continues to execute the complete shaper. Tracing bypasses reuse. A glyph dump
after rendering is valid, but private intermediate arrays must not be inspected
after a memo hit. Stats count memo lookups, not calls made while reuse is off.

The tiny word-dispatch hook added to `bntex-native.sty` retains the original
shape/render operation when the optional memo package is not loaded. Neither
`bntex.sty` nor the old cached `\bn` command is modified.

## Reproduce the multi-file project

For this legacy explicit example, use a fresh current checkout and the documented exact
font (SHA-256 `32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef`).
The source distribution includes no font binaries. Install normal TeX tools,
Poppler and the project's test extras for validation.

```bash
python -m pip install -e '.[test]' 'fonttools==4.63.0'
python -m bntex.native compile --font /path/to/NotoSerifBengali-Regular.ttf \
  --out build/native-profile.json
python -m bntex.tex_export --profile build/native-profile.json \
  --font /path/to/NotoSerifBengali-Regular.ttf --out build/native-installation
python -m bntex.native_project stage \
  --manifest examples/native-project/project.json \
  --installation build/native-installation --out build/native-document
python -m bntex.native_project run --project build/native-document \
  --passes 3 --timeout 60
```

All output directories/files must be new. `run` uses fixed pass tags, so a second
invocation in that directory refuses to overwrite its logs; for ordinary editing
run `pdflatex -no-shell-escape -halt-on-error main.tex` directly in the staged
project, or stage a fresh validation directory. The stage command does not execute
TeX or infer `\input` dependencies: `project.json` lists every source explicitly.
Same basenames in different declared subdirectories are supported. Symlinks,
traversal, case collisions, undeclared main documents and asset-name collisions
are rejected. `latexmkrc` is an explicitly permitted trusted build configuration.

`verify` checks installed assets and reports source changes without prohibiting
editing. It is not a source parser, authentication system or malicious-TeX sandbox.
Keep one authoritative editable source copy; staging never overwrites an existing
project or pulls edits back into the repository automatically.

```bash
python -m bntex.native_project verify --project build/native-document
# On your own machine: includes YOUR installed font, not a distributed font copy.
python -m bntex.native_project pack --project build/native-document \
  --out build/native-document-upload.zip
```

The packer includes only declared sources and verified installed assets, not logs,
PDF outputs or arbitrary adjacent files. It preserves root `main.tex` and source
subdirectories. See OVERLEAF-NATIVE.md for the still-unperformed browser gate.

## Context support matrix

The tests assert these specific constructions, not general class compatibility:

| Context | Evidence / boundary |
| --- | --- |
| Explicit mixed English/Bengali body | Passed; English remains outside Bengali spans |
| article sections + TOC | Passed with explicit regular declared heading text |
| report/book chapters + TOC | Passed with the same explicit regular-text policy |
| Actual PDF outlines and title/author | Original Unicode verified with pypdf |
| Footnotes, table cells, captions/LOF | Individual compile/extraction checks passed |
| amsmath `\text` and text in subscripts | Passed; not a Bengali math alphabet |
| TikZ node | One explicitly tested regular-text node passed |
| Beamer frame | One explicit regular-font frame/title passed; not all themes |
| BibTeX-generated title | Passed using declared regular text in a protected title |
| Regular sizes/colors with memo hits | Glyph fields, dimensions, color operators and extraction checked |
| Unrequested bold/italic | Expected rejection, not fallback |
| Automatic script detection | Separate implemented `bntex-auto` path; see AUTOMATIC-AUTHORING.md |
| Additional fonts, arbitrary publishers, tagged PDF | Not certified |
| Overleaf browser / second-user reproduction | Not performed |

The 3-page example uses fictional table values and a fictional bibliography entry.
They are typography fixtures, not substantive research claims.

## Performance and acceptance

`tools/native_benchmark.py` measures 1/10/100 requested pages at 200 tokens/page,
with two fresh TeX processes per successful case. Second passes have auxiliary
files present, not a persistent word cache. Distinct workloads are deterministic
synthetic four-syllable strings, NOT mined or dictionary-approved words. Repeated
workloads cycle through twenty ordinary words. Actual page counts and extraction
are checked; timeouts have no completed-page claim.

```bash
PYTHONPATH=src python tools/native_benchmark.py \
  --installation build/native-installation --out build/benchmark \
  --timeout 45 --passes 2
# Explicitly extend the budget for the 100-page repeated case:
PYTHONPATH=src python tools/native_benchmark.py \
  --installation build/native-installation --out build/benchmark-extended \
  --pages 100 --workloads repeated --modes memo --timeout 180 --passes 2
```

GNU time supplies per-child peak RSS and CPU times; the wall timer includes process
startup. Compiler logs provide TeX memory/string/control-sequence counters. When a
process group times out it is reaped and missing resource totals remain null.
The harness checks asset hashes after each case and removes copied font assets
from benchmark output directories. Use the measured JSON/report; do not extrapolate
from repeated text to distinct vocabulary. These are shared-host measurements,
not controlled hardware performance guarantees.

Issue #7 remains open for actual Overleaf testing, second-user reproduction and
further distinct-text optimization. Issue #15 now has the separate implemented
automatic-authoring path; historical explicit-only results do not certify that
new path in every context. This guide does not authorize a public release or
CTAN submission.
