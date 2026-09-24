# Primary references and reading map

Sources selected for the original development plan on 23 September 2026. Versioned
manuals are snapshots, not claims that no newer version exists. Links may redirect.

**R1 — pdfTeX user manual.** Font maps, TrueType embedding, encodings and PDF primitives.
https://texdoc.org/serve/pdftex-a.pdf/0

**R2 — Microsoft Bengali shaping model.** Syllable analysis, dynamic font properties,
reordering and substitutions/positioning.
https://learn.microsoft.com/en-us/typography/script-development/bengali

**R3 — Unicode Bengali and normalization.**
https://www.unicode.org/versions/Unicode17.0.0/core-spec/chapter-12/
https://www.unicode.org/reports/tr15/

**R4 — HarfBuzz clusters and buffer API.**
https://harfbuzz.github.io/working-with-harfbuzz-clusters.html
https://harfbuzz.github.io/harfbuzz-hb-buffer.html

**R5 — HarfBuzz introduction and font API.**
https://harfbuzz.github.io/what-is-harfbuzz.html
https://harfbuzz.github.io/harfbuzz-hb-font.html

**R6 — BangTeX, CTAN.** Existing Bengali/Assamese classes and fonts.
https://ctan.org/pkg/bangtex

**R7 — mkbangtex, CTAN.** Phonetic Roman-script preprocessing for BangTeX.
https://ctan.org/pkg/mkbangtex

**R8 — bangla, CTAN.** Inspect its actual manual for engine requirements.
https://ctan.org/pkg/bangla

**R9 — latexbangla, CTAN.** Inspect source/manual before comparing compatibility.
https://ctan.org/pkg/latexbangla

**R10 — Overleaf compiler and TeX Live settings.**
https://docs.overleaf.com/getting-started/recompiling-your-project/selecting-a-tex-live-version-and-latex-compiler

**R11 — LaTeX package author guide and expl3 documentation.**
https://www.latex-project.org/help/documentation/clsguide.pdf
https://www.latex-project.org/help/documentation/
Use `texdoc clsguide` and `texdoc interface3` in the selected installation.

**R12 — l3build testing and packaging.** https://ctan.org/pkg/l3build

**R13 — FontTools.** https://fonttools.readthedocs.io/en/latest/ttLib/index.html

**R14 — Unicode line breaking.** https://www.unicode.org/reports/tr14/

**R15 — CTAN upload guidance.** https://ctan.org/help/upload-pkg

**R16 — TDS guidelines.** https://ctan.org/TDS-guidelines

**R17 — OFL FAQ and LPPL.** Read each font/dependency's actual license; these are
references rather than individualized legal advice.
https://openfontlicense.org/ofl-faq/
https://www.latex-project.org/lppl/lppl-1-3c/

**R18 — GitHub CLI repository creation.** Historical first-publication helper.
https://cli.github.com/manual/gh_repo_create

## OpenType layout specifications used by the audit

https://learn.microsoft.com/en-us/typography/opentype/spec/chapter2
https://learn.microsoft.com/en-us/typography/opentype/spec/gsub
https://learn.microsoft.com/en-us/typography/opentype/spec/gpos
https://learn.microsoft.com/en-us/typography/opentype/spec/gdef

## Evidence boundaries

References establish the underlying format/specifications and prior art. BnTeX's
implementation and test outcomes are our own engineering work. A structural audit
is not a native shaper or a full font validator. This snapshot does not claim CTAN
acceptance, native shaping, Overleaf browser certification or comprehensive
accessibility. Repository/CI actions are reported from their actual results.
