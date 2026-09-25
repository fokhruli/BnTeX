# BnTeX — Bengali in pdfLaTeX

**Private development alpha; not a CTAN/PyPI release.** Main now contains the
native implementation, document integration and the legacy cached backend.
Use topic branches based on current `main`; do not switch to an old bootstrap
branch for the current package.

| Interface | Editing contract |
| --- | --- |
| `bntex-native.sty` / `\bnNative{...}` | Install the supported font profile once. New Bengali words are shaped by pdfTeX itself; no per-document preprocessing or external shaper is invoked. |
| `bntex.sty` / `\bn{...}` | Legacy HarfBuzz-prepared word cache. New vocabulary or styles require preparation again. |
| Automatic wrapper-free input | Deferred under issue #15; no `autobengali` option is implemented. |

The native profile is experimental and limited to the exact static **Noto Serif
Bengali Regular**, medium upright, `bng2`/default system. It is not a generic
OpenType engine. Font files are local dependencies and are not included in Git,
source archives, wheels, or downloads.

## Native quick start

Install Python 3.10+, FontTools and a TeX distribution containing `pdflatex` and
`pltotf`. Tests additionally use the project test extras, Poppler and the pinned
HarfBuzz 10.2.0 reference environment. Supply your own installed static font.
The required font SHA-256 is
`32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef`.

```bash
python -m pip install -e '.[test]' 'fonttools==4.63.0'
python -m bntex.native compile \
  --font /path/to/NotoSerifBengali-Regular.ttf \
  --out build/native-profile.json
python -m bntex.tex_export \
  --profile build/native-profile.json \
  --font /path/to/NotoSerifBengali-Regular.ttf \
  --out build/native-installation
python -m bntex.native_project stage \
  --manifest examples/native-project/project.json \
  --installation build/native-installation --out build/native-document
cd build/native-document
latexmk -pdf main.tex
```

Outputs must be new. The example's `latexmkrc` disables shell execution. For
ordinary editing, change `.tex` files in the staged project and compile again;
new words do not require another export. Updating package/font/profile assets
requires a fresh matching installation. Do not mix files from different exports.

```latex
\usepackage{bntex-native}
\BnTeXNativeLoadProfile{bntex-native-profile.tex}
% In the document:
English text remains in the surrounding font.
\par\bnNative{বাংলা আমাদের মাতৃভাষা।}
```

Keep English, math and commands outside literal Bengali spans. Spaces permit
word-level wrapping; intraword hyphenation is not implemented. Each literal span
is limited to 4,096 UTF-8 bytes. Unsupported styles and malformed inputs are
errors, not silently approximated output.

For headings and PDF strings, use `bntex-native-integration` and its
`\BnTeXNativeDeclareText`, `\BnTeXNativeText`, and
`\BnTeXNativeRegularText` interfaces. Declarations preserve original text; they
are not a shaped-word dictionary. RegularText explicitly chooses regular upright
inside a normally bold heading. See [native integration](docs/NATIVE-INTEGRATION.md).
Optional `bntex-native-memo` reuses bounded glyph runs within one TeX process only;
new words still execute the shaper. It is not a persistent word cache.

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

**Pending:** actual Overleaf browser/second-user reproduction, scoped native
visual acceptance, interactive long-document performance, public naming and
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
