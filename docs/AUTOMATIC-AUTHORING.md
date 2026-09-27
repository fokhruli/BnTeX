# Automatic Bengali input and standard authoring styles

Private development feature for issues #15 and #25, built on main `dbeab3c`.
The maintainer has explicitly activated wrapper-free input and formatting now;
this supersedes the earlier deferral. No publication is authorized.

## User interface

After installing the audited font family once:

```latex
\documentclass{article}
\usepackage[synthetic-italic]{bntex-auto}
\BnTeXNativeLoadProfile{bntex-native-profile.tex}
\begin{document}
This is বাংলা text. বাংলা আমাদের মাতৃভাষা।
\textbf{মোটা বাংলা লেখা}
\textit{ঘোষিত কৃত্রিম বাঁকানো লেখা}
\emph{গুরুত্বপূর্ণ লেখা}
\underline{নিচে দাগ দেওয়া লেখা}
\section{বাংলা শিরোনাম}
\end{document}
```

No `\bn` or `\bnNative` wrapper is required in ordinary text. The explicit
native command remains an optional diagnostic interface, not the authoring
requirement. Load `bntex-auto` to enable routing; legacy packages do not enable
it merely by being installed. `\BnTeXAutoOff` and `\BnTeXAutoOn` are scoped.
Turning automatic handling off does not provide a different renderer for raw
Bengali; explicit native commands remain available inside that scope.

## One-time installation, not document preprocessing

```sh
python -m pip install -e '.[test]' 'fonttools==4.63.0'
python -m bntex.authoring_export \
  --regular-font /path/to/NotoSerifBengali-Regular.ttf \
  --bold-font /path/to/NotoSerifBengali-Bold.ttf \
  --out build/authoring-installation
python -m bntex.native_project stage \
  --manifest examples/automatic-authoring/project.json \
  --installation build/authoring-installation --out build/authoring-document
cd build/authoring-document
pdflatex -no-shell-escape -halt-on-error main.tex
```

All output directories must be new. Repeat ordinary pdfLaTeX compilation after
editing text; never regenerate vocabulary. Python and font tools run only to
build/update the font installation or execute development tests. The native
runtime calls no Python, Lua, network, or external shaping helper. Never replace
individual files inside an old installation: export a matching complete unit.
Font files and generated installations remain local and are not source artifacts.

## True bold versus synthetic italic

The supported regular and bold binaries have these SHA-256 identities:

- Regular: `32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef`
- Bold: `96cc17640329810e2ac1b53d61ec4f429ba9bf729d4f37623a296581d79a5133`
- Bold typed profile: `e3a798be7b57bb363c041cb7252a97c2c565c59215db868e837c069ed117b0f8`

`\textbf`/`\bfseries` select the actual bold outlines, metrics, and positioning
rules. Nothing is thickened, double-printed, or shaped with regular metrics.
The compiler proves shared glyph mappings, substitution structure, and filtering;
it then emits a strictly checked bold metrics/GPOS delta. Additional explicit
bold kerning pairs are retained. Unexpected structural differences fail export.
This is support for two exact binaries, not arbitrary fonts in that family.

This installed family has no true italic face. With no option, italic/slanted
requests fail explicitly. The `synthetic-italic` package option deliberately
allows `\textit`, `\itshape`, `\slshape`, and `\emph` to use a 0.18 horizontal
shear around the baseline. Bold italic is the same declared shear of real bold.
The advance remains unchanged; visible overhang is possible. This is not a
font-designed italic face. `\BnTeXSyntheticItalicOff` and `On` are scoped controls.
The document and source both disclose the approximation. Nested emphasis returns
to upright according to normal LaTeX behavior.

## Input boundaries and LaTeX behavior

The package registers Bengali codepoints through the existing LaTeX UTF-8
interface. A mapped initial character collects connected Bengali byte sequences
before calling the existing shaper. It does not shape disconnected characters.
Dependent vowels, virama, nukta, danda, ZWJ and ZWNJ are included. Original byte
encodings are preserved; working normalization never replaces PDF logical text.

Scanning does not expand unrelated macros. It stops at ordinary spaces, Latin,
commands, braces and math boundaries; it returns unrelated inspected UTF-8 bytes
to normal LaTeX. A continuous automatic run is limited to 4,096 bytes. The current
shaper's existing syllable/node/operation limits still apply. Whitespace ends a
run; a complete unwrapped paragraph is not subject to one total span limit.
Raw math Bengali is an error: use `\text{বাংলা}` with amsmath. No intra-word
hyphenation or new syllable-breaking rule is introduced.

Protected moving arguments keep their original characters in auxiliary files.
Hyperref's PDF-string path emits original Unicode scalars rather than executing
the typesetter. Either hyperref load order is covered. Latin font selection is
not changed. Bengali remains the supported serif family even in a surrounding
Latin sans/monospace context: no Bengali sans/monospace face is claimed.

## Executed support matrix and limits

| Context | Scope |
|---|---|
| Ordinary Bengali/English, including direct adjacency | Covered by exact run and boundary tests |
| Real bold, regular/bold nesting | Separate face rules, geometry and cache identity tested |
| Italic/emphasis | Only explicitly enabled synthetic slant; no true italic claim |
| Standard `\underline` | Supported as an unbreakable LaTeX underline box |
| `ulem` `\uline` and `\sout` with `normalem` | Selected mixed/effect and multiline specimens tested |
| Color, size, superscripts/subscripts | Current rendering state inherited; selected commands tested |
| Headings/contents and Unicode metadata/bookmarks | Actual PDF objects and multiple passes tested |
| Tables, captions, footnotes and math text | Included in the source specimen; individual checks retained |
| ASCII verbatim and URLs; Bengali labels and input filenames | Boundary regression specimens tested |
| Bengali verbatim/code and non-ASCII URL display | Not certified; this is not a general verbatim Unicode-font package |
| Arbitrary package combinations, fonts and publisher classes | Not certified |
| Actual Overleaf browser / independent person | Separate pending acceptance, not inferred from local tests |

Optional `bntex-native-memo` keys glyph runs by exact original bytes and the full
font identity. Size, color and declared slant are applied at rendering time, so
none requires re-shaping on a cache hit. Loading the memo module is not required.

## Validation and review

Run the full repository with both mandatory gates:

```sh
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 python -m pytest -q
```

The new tests use actual pdfTeX with shell disabled, verify runtime inputs and
immutable assets, and compare all frozen regular forms and the complete bold
conjunct/vowel matrix against the exact reference. Final executed counts belong
to the PR/validation record, not an inferred sum of historical subsets.

The earlier three-page regular specimen was accepted by the maintainer; its
exact scope and identity are recorded in `reviews/native-document-dbeab3c.json`.
That approval does not cover the new bold/slanted output or every corpus case.
The new example needs a new scoped visual review. No release-readiness gate is
silently completed, and the older 90-second performance target remains open.

For real browser acceptance, use the existing `native_project pack` command on
your locally generated project, select pdfLaTeX, retain the no-shell guard, and
record compiler/version and a new-word edit with its log/PDF. The downloadable
source archive contains no fonts and is not a ready-to-compile font installation.
See OVERLEAF-NATIVE.md for the manual record; do not fabricate it from CI.
