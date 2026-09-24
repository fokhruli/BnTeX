# BnTeX — Bengali text in pdfLaTeX

**0.1.0a2 — private development alpha, not a CTAN release.**

BnTeX accepts literal Unicode Bengali and renders native embedded TrueType glyphs
in pdfLaTeX, not screenshots or outlined words. Shaping currently happens offline
with HarfBuzz; the final document compiles with shell execution disabled.

**New words still require preparation.** A TeX-native Bengali shaper is the next
major milestone, not an implemented feature. The new `profile` command audits
font lookup dependencies; it does not generate an executable font profile.

## Start from the review branch

```bash
git clone https://github.com/fokhruli/BnTeX.git
cd BnTeX
git switch feat/bootstrap-profile-audit
```

The code is proposed to `main` through a pull request. Keep development on topic
branches. The old `tools/publish_private.sh` is a historical first-publication
helper; do not run it against this existing repository.

## Setup and demonstration

Example Debian/Ubuntu setup (font paths are distribution-dependent):

```bash
sudo apt-get update
sudo apt-get install python3-venv libharfbuzz0b fonts-noto-core \
  texlive-latex-extra texlive-fonts-recommended texlive-luatex poppler-utils
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m bntex doctor

python -m bntex prepare \
  --source examples/main.tex \
  --font regular=/usr/share/fonts/truetype/noto/NotoSerifBengali-Regular.ttf \
  --font bold=/usr/share/fonts/truetype/noto/NotoSerifBengali-Bold.ttf \
  --out build/demo
python -m bntex verify build/demo
(cd build/demo && pdflatex -no-shell-escape -halt-on-error main.tex)
(cd build/demo && pdflatex -no-shell-escape -halt-on-error main.tex)
```

Python 3.10+, FontTools, a shared HarfBuzz library, `pltotf`, and static Bengali
TTFs are required for preparation. Final compilation uses pdfLaTeX plus prepared
assets only. No font binaries are included. WSL is a possible Linux development
route; native Windows/macOS and Overleaf browser import have not been validated.

```latex
\documentclass{article}
\usepackage{bntex}
\BnTeXLoadCache{bntex-cache.tex}
\begin{document}
English retains the document font.
\bn{বাংলা আমাদের মাতৃভাষা।}
\textbf{\bn{বাংলা ভাষায় গবেষণা।}}
\end{document}
```

This example must be prepared before compilation. Keep TeX/math outside Bengali
spans: `\bn{এখানে} \(x_t\) \bn{অবস্থা নির্দেশ করে।}`. Use separate spans for separate
paragraphs. New punctuation/spelling/Unicode representations also create new cache
keys. Edit the original source, not the replaceable generated build directory.

## Implemented and unsupported

| Area | Contract |
|---|---|
| Input | Literal `\bn{...}` / `\bn[style]{...}`; source-located errors |
| Fonts | Local static TrueType-outline fonts passing the prototype checks |
| Rendering | HarfBuzz-prepared native glyphs, positioning and font banks |
| Styles | Regular, outer bold, explicit prepared aliases; inherited size/color |
| Layout | Normal interword glue; no break inside a word |
| PDF text | Original Unicode ActualText; Poppler extraction tested |
| Font audit | Transitive GSUB/GPOS references, extensions, flags/GDEF, wire formats |
| Not implemented | TeX-native shaping, bare/global Bengali, nested TeX in spans |
| Not implemented | Arbitrary fonts, variable/CFF fonts, hyphenation, automatic fallback |
| Not guaranteed | Publisher classes, all PDF viewers, bookmarks, tagged PDF/PDF-UA |

Automatic italic/slanted styles fail rather than inventing a Bengali face. Prepare
bold for headings. The sample uses explicit English bookmark fallbacks.

## Development and validation

```bash
BNTEX_REQUIRE_INTEGRATION=1 PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m bntex profile --font /path/to/static-bengali.ttf > profile.json
PYTHONPATH=src python tools/compare_reference.py --font /path/to/static-bengali.ttf
python tools/audit_release.py
```

The local bootstrap run passed **74 tests**, including rendering and extraction.
The 26-word geometry comparison passed with maximum advance difference 0.00009 pt.
Both comparison paths use HarfBuzz: this validates backend geometry, not an
independent shaping algorithm. Remote CI status belongs to the PR checks, not this
local test statement. See [validation](docs/BOOTSTRAP-VALIDATION.md).

## Project map and next work

`tex/latex/bntex/bntex.sty` is the renderer; its wheel-resource copy must match.
`src/bntex/` contains the scanner, HarfBuzz adapter, build/verify CLI and audit.
`tests/` includes synthetic layout graphs and real-font integration checks.
`examples/main.tex` and `docs/diagrams/architecture.tex` are editable PDF sources;
compiled PDFs and generated assets are not tracked.

Start with the [development plan](BNTEX_DEVELOPMENT_PLAN.md),
[architecture](docs/ARCHITECTURE.md), [native-shaper design](docs/NATIVE_SHAPER.md),
[profile audit](docs/PROFILE_AUDIT.md), [roadmap](docs/ROADMAP.md),
[learning guide](docs/LEARNING.md), [Overleaf workflow](docs/OVERLEAF.md), and
[CTAN checklist](docs/CTAN.md). Read [CONTRIBUTING](CONTRIBUTING.md) and AGENTS.md
before changing code.

The next priority is a pinned, human-reviewed corpus (#3), then the typed profile
IR/Python shaping model (#5), alongside the UTF-8 front end (#4). The final native
gate (#6) requires unseen words to compile after Python and word caches are removed.

## License

Original code/documentation: MIT, see LICENSE. Dependencies/fonts retain their own
licenses. `fsType=0` is a technical filter, not a legal determination of font
redistribution rights. No font files, credentials, CTAN/PyPI publication or
repository visibility change are included in this work. Primary references are
in [REFERENCES](docs/REFERENCES.md).
