# BnTeX — Bengali in pdfLaTeX

**Private development alpha; not a CTAN/PyPI release.** Main now contains the
native implementation, document integration and the legacy cached backend.
Use topic branches based on current `main`; do not switch to an old bootstrap
branch for the current package.

| Interface | Editing contract |
| --- | --- |
| `bntex-native.sty` / `\bnNative{...}` | Install the supported font profile once. New Bengali words are shaped by pdfTeX itself; no per-document preprocessing or external shaper is invoked. |
| `bntex-cached.sty` or `bntex` with `[cached]` / `\bn{...}` | Legacy HarfBuzz-prepared word cache. New vocabulary or styles require preparation again. |
| `bntex.sty` (installed distribution) | Automatic input plus default-profile loading. No author-side generation. |
| `bntex-auto.sty` (developer interface) | Automatic connected-script routing; ordinary Bengali needs no wrappers. Real bold and opt-in synthetic slant use the audited family installation. |

The native profiles are experimental and limited to the exact static **Noto Serif
Bengali Regular and Bold**, `bng2`/default system. It is not a generic
OpenType engine. Font files are local dependencies and are not included in Git,
source archives, wheels, or downloads.

## Installed-package target (distribution candidate)

The public `bntex.sty` now selects automatic input and the bundled default profile:

```latex
\documentclass[12pt]{article}
\usepackage[synthetic-italic]{bntex}
\begin{document}
বাংলা আমাদের মাতৃভাষা। This sentence mixes বাংলা and English.
\textbf{মোটা বাংলা লেখা} \underline{নিচে দাগ দেওয়া লেখা}
\end{document}
```

The complete package must first be installed by a TeX distribution. Authors do
not run Python or load a profile explicitly. The maintainer-only distribution
builder supplies precompiled runtime data and audited Regular/Bold assets.
This source repository itself is not a complete font installation or a CTAN
release. Read `docs/distribution/README.md` and the installation manual source.
Default TeX Live root relocation is tested. Restrictive `openin_any=p` is
engine-dependent and separately probed; actual Overleaf, independent acceptance
and release approval remain unresolved.

**Migration:** `\usepackage[cached]{bntex}` or `bntex-cached` explicitly selects
the old prepared-word backend. Old flat prepared projects keep an explicitly
labelled local shim; an old project-local `bntex.sty` shadows the installed one.
The native release must never silently select cached shaping.

## Developer-only automatic authoring quick start

The following builds a private development installation. It is **not** an
end-user requirement for the installable distribution.


The maintainer has activated issues #15/#25. Load `bntex-auto` and write ordinary
Bengali mixed with English; no per-passage wrapper is required. Bold is a real
font face. Italic/emphasis is **synthetic slant only with an explicit option**;
without consent it fails rather than pretending that a true italic face exists.

```bash
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

Python/font tools perform the one-time installation. After editing document
text, run only pdfLaTeX again. New words require no preparation. Outputs must be
new; updating the package requires a new complete matching installation.

```latex
\usepackage[synthetic-italic]{bntex-auto}
\BnTeXNativeLoadProfile{bntex-native-profile.tex}
% In the document:
This is বাংলা text. বাংলা আমাদের মাতৃভাষা।
\textbf{মোটা বাংলা লেখা}
\textit{ঘোষিত কৃত্রিম বাঁকানো লেখা}
\underline{নিচে দাগ দেওয়া লেখা}
\section{বাংলা শিরোনাম}
```

Read [automatic authoring](docs/AUTOMATIC-AUTHORING.md) for exact font hashes,
style semantics, boundaries, original Unicode, and the tested support matrix.
Standard LaTeX commands are not placed inside Bengali-specific wrappers.
The supported Bengali family remains serif; arbitrary fonts, true italic,
small caps, Bengali verbatim, and every package combination are not claimed.

## Existing explicit and cached interfaces

The regular-only `bntex.tex_export` installation and `bntex-native`/`\bnNative`
interface remain available without automatic routing. Its literal spans require
English/commands/math outside the argument; 4,096 bytes per explicit span.
The new automatic mode bounds each connected run instead, stopping at spaces.
No intraword hyphenation is added. `bntex-native-integration` retains original-text
declarations for explicit moving/PDF arguments. Automatic mode supports direct
literal headings and hyperref strings instead.

`bntex-native-memo` optionally reuses bounded positioned glyph runs inside one
TeX process. Full font identity separates regular/bold; new words always execute
the shaper. The legacy cached `bntex`/`\bn` contract still requires vocabulary
preparation and is not used by automatic authoring.

## Validation and known limits

The native path has differential tests, frozen glyph references, real-document
context tests and a physically Python-free unseen-word capability test. Read
revision-specific reports for executed results; historical design documents and
local reconstructed-checkout counts are not current full-repository CI results.

```bash
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 python -m pytest -q
python tools/native_performance.py \
  --installation current=build/native-installation \
  --out build/performance --pages 1 10 100 \
  --modes repeated distinct --memo off --passes 2 --timeout 90
```

First-glyph and guarded two-glyph dispatch indexes accelerate native lookup work.
They preserve original lookup order and blocking/filtering semantics. Repeated
and distinct vocabulary must be measured separately. Long mostly distinct text
remains slow relative to the former 90-second target; an extended timeout is not
an optimization. Synthetic tokens are not representative book prose.

**Pending:** actual Overleaf browser/second-user reproduction, review of new automatic/bold/slanted
output, interactive long-document performance, public naming and
font/profile distribution review. No all-font, all-viewer, tagged-PDF/PDF-UA,
Windows/macOS or universal publisher-class compatibility is claimed. The
repository remains private and publication requires a separate decision.

## Documentation and release preparation

- [Developer manual source](docs/manual/bntex-manual.tex): installation, authoring,
  troubleshooting, tests and release boundaries. It compiles with ordinary
  pdfLaTeX without a Bengali font installation.
- [Native engine](docs/NATIVE-TEX.md), [integration](docs/NATIVE-INTEGRATION.md),
  [dispatch optimization](docs/NATIVE-DISPATCH-PERFORMANCE.md).
- [Release readiness](docs/RELEASE-READINESS.md) and its machine-readable gates.
- [Historical cached workflow](docs/OVERLEAF.md) and [original roadmap](docs/ROADMAP-ORIGINAL.md):
  retained for design provenance; current interfaces are described above.

The original code uses the repository [LICENSE](LICENSE); adapted shaping
algorithms retain [third-party notices](THIRD-PARTY-NOTICES.md). Independent
execution is not a claim of algorithmic novelty. Font licenses remain separate.
`tools/release_preflight.py` builds only a private source-review archive. It does
not upload, approve rights, or certify a public release.
