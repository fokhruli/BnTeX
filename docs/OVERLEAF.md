# Overleaf with pdfLaTeX

## Current cached workflow

Edit the original UTF-8 .tex locally using literal `\bn{...}` spans. Prepare with
the CLI and your locally installed static Bengali fonts, then verify the generated
build. Make a ZIP locally of the complete generated directory and import it into
Overleaf. Select the correct main file and the pdfLaTeX compiler [R10].

The prepared project contains the source, bntex.sty, word cache, exact local font
copy and .tfm/.enc banks. Keep all required assets together. The manifest is useful
for verification/debugging but not read by pdfLaTeX. Python, HarfBuzz and pltotf are
not called during final compilation.

This repository does not distribute font files. Use a locally installed font you
are permitted to use/upload. Do not treat a font embedding flag as redistribution
permission. Regenerate examples yourself; the compiled PDF is not a reusable font
package.

## Editing boundary

Reordering already-cached words, changing supported font size/style or editing
surrounding English normally requires no new shaping. New vocabulary, punctuation,
spelling/Unicode representation, font or style requires preparation again. An
uncached word is an error, not a fallback to unshaped characters.

Maintain one authoritative source. Generated builds are replaceable: do not edit
your only copy inside build/demo. Before regenerating locally, download/synchronize
any Overleaf source changes. A future explicit project manifest should make this
safer without pretending to expand arbitrary TeX.

## Validation boundary

The local example passed with `pdflatex -no-shell-escape`; the Overleaf browser
workflow has NOT yet been run. Issue #7 tracks a clean-room import and records the
actual TeX Live version and result. Do not call the package Overleaf-certified
until that test passes. Do not assume arbitrary Python/shared-library helpers or
unrestricted shell execution are available in Overleaf.

Publisher rules are separate: accepting pdfLaTeX does not imply accepting custom
fonts, font maps, generated assets or experimental packages.

## Troubleshooting

| Error | Action |
|---|---|
| Cache not found | Upload the complete prepared project and use its cache path |
| Prepared asset missing/changed | Rebuild and replace dependent assets together |
| Uncached Bengali word | Prepare the edited authoritative source again |
| Bold style not prepared | Supply a real bold font when preparing headings/textbf |
| Automatic italic/slanted profile missing | Use upright or an explicit prepared style |
| Cannot load TFM | Include all generated font metrics |
| Font lacks a glyph | Correct the font/input; do not substitute approximations |
| Incorrect bookmark | Use an explicit texorpdfstring fallback in this version |

NATIVE_SHAPER.md describes the future font-profile implementation that removes
per-document vocabulary preparation. A larger word cache is not that feature.
