# BnTeX — Bengali in pdfLaTeX

BnTeX lets you type Bengali directly in a **pdfLaTeX** document, mixed freely
with English, and get correctly shaped text: conjuncts, reph, vowel signs and
their positioning. The shaping runs inside pdfTeX itself, so there is no
XeLaTeX or LuaLaTeX, no shell escape, no external program and no per-document
preprocessing. It works on Overleaf with the default pdfLaTeX compiler.

**Status: alpha (0.2.0-alpha).** It renders the exact Noto Serif Bengali
Regular and Bold fonts bundled with the release, and nothing else yet. Please
report anything that renders wrongly (see [Reporting problems](#reporting-problems)).

```latex
\documentclass[12pt]{article}
\usepackage[synthetic-italic]{bntex}
\begin{document}
\section{বাংলা শিরোনাম}
বাংলা আমাদের মাতৃভাষা। This sentence mixes বাংলা and English.

\textbf{মোটা বাংলা লেখা} \textit{বাঁকানো লেখা} \underline{নিচে দাগ}
\end{document}
```

## Quick start

Download the release files from the
[Releases page](https://github.com/fokhruli/BnTeX/releases).

**Overleaf.** Download `bntex-overleaf-starter.zip`, choose *New Project →
Upload Project*, and select the ZIP. Keep the compiler set to pdfLaTeX and edit
`main.tex`. Leave the BnTeX files in the project's top folder; the package finds
them there and checks each against the checksum recorded for the release.

**TeX Live (local).** Unzip `bntex.tds.zip` into your personal TeX tree, the
folder printed by `kpsewhich -var-value TEXMFHOME` (usually `~/texmf`). Then
use `\usepackage{bntex}` in any document.

**MiKTeX.** Make a folder for your own packages (for example
`C:\Users\you\texmf`), unzip `bntex.tds.zip` into it, and register it once,
either in MiKTeX Console under *Settings → Directories* or with

```
initexmf --register-root=C:\Users\you\texmf
```

If the folder is already registered, refresh MiKTeX's file list after unzipping
with `initexmf --update-fndb`. Tested with MiKTeX 25.4.

**Any single project.** Copying the files from `bntex-overleaf-starter.zip`
into a document's folder also works, with MiKTeX and TeX Live alike.

## Using it

| Option or command | Effect |
| --- | --- |
| `\usepackage{bntex}` | Bengali text is detected and shaped automatically; no wrapper commands. |
| `[synthetic-italic]` | Lets `\textit`, `\emph`, `\itshape` and `\slshape` use a declared 0.18 slant. The fonts have no true italic, so without this option italic Bengali is an error. |
| `\textbf`, `\bfseries` | The real Noto Serif Bengali Bold face, with its own metrics and positioning. |
| `[no-word-cache]` | Turns off the word cache described below. |
| `\BnTeXAutoOff`, `\BnTeXAutoOn` | Stop or resume automatic Bengali handling within a group. |
| `\BnTeXCacheStats` | Prints word-cache hits and misses to the log. |
| `[cached]` | Selects the old prepared-word backend (`bntex-cached`) for legacy projects. |

Bengali works in ordinary text, headings and the table of contents, footnotes,
captions, tables, `\underline`, `ulem`'s `\uline`/`\sout`, colour and font
sizes. With `hyperref`, bookmarks and PDF metadata receive the original Unicode
text. In mathematics, write Bengali inside amsmath's `\text{...}`.

The PDF stores the original Unicode text for every word (`/ActualText`), so
search and copy-paste return the exact Bengali in viewers that read it (tested
with Poppler's `pdftotext`). Overleaf's preview and Firefox's built-in viewer
(PDF.js) ignore `/ActualText` and use each glyph's own Unicode text instead.
The letters come out right, but a vowel sign drawn to the left of its consonant
(ি, ে, ৈ and the left half of ো, ৌ) or a reph comes out where it is drawn, so
মোটা copies as েমাটা, and spaces may move. For exact text, download the PDF and
open it in a desktop viewer that reads `/ActualText`.

## Speed and the word cache

Shaping happens in TeX macros, so a first compile handles roughly 100–150
distinct words per second. BnTeX keeps every shaped word in `\jobname.bnc` next to the `.aux`
file, and later compiles reuse it, shaping only new words. The output is
identical with or without the cache, and deleting the file is always safe.

Measured on Overleaf (TeX Live 2026):

| Document | Without cache | Recompile with cache |
| --- | --- | --- |
| 2-page feature sample | 3.2 s | 0.5 s |
| 600 words of prose | 4.6 s | 0.5 s |
| 5,000 words of prose | 37.8 s | 2.5 s |

## Limitations

- Fonts: only the bundled Noto Serif Bengali Regular and Bold. No other Bengali
  font, no sans-serif or monospaced Bengali, and no true italic.
- Line breaks fall between words; Bengali words are never hyphenated.
- Bengali in `verbatim` or code listings is not supported.
- Copying from Overleaf's preview or Firefox gives Bengali letters in the order
  they are drawn, not typed (see above).
- pdfLaTeX only. For XeLaTeX or LuaLaTeX, use `fontspec`/`polyglossia` with an
  OpenType Bengali font; those engines shape Bengali natively.
- Tested with the standard classes and the packages listed above, not with every
  package combination or publisher class.
- Not yet on CTAN, so not yet installable through TeX Live's or MiKTeX's package
  managers.

## How it works

The release contains a precompiled description of the Bengali OpenType rules
(GSUB/GPOS) of the two fonts and an implementation of Indic shaping written in
expl3 and adapted from HarfBuzz's Bengali shaper. When pdfTeX meets Bengali
text, it decodes the UTF-8, applies the font's rules and places the glyphs from
the original TrueType fonts. The test suite compares its glyph output with
HarfBuzz 10.2.0 on a pinned corpus of Bengali forms and words. Details are in
[docs/NATIVE-TEX.md](docs/NATIVE-TEX.md) and
[docs/AUTOMATIC-AUTHORING.md](docs/AUTOMATIC-AUTHORING.md).

## Reporting problems

Open an issue with the *Rendering or preparation bug* template and include the
Bengali text, a screenshot of the wrong output and what you expected. The log line
starting `Package: bntex` gives the version.

## Development

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for building the font profiles,
the installable distribution and the test suite, and
[CONTRIBUTING.md](CONTRIBUTING.md) for the workflow.

## License

BnTeX's code and documentation are MIT licensed ([LICENSE](LICENSE)). The
shaping algorithm is adapted from HarfBuzz under its own notice
([THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)). The bundled Noto Serif
Bengali fonts and the data derived from them are under the SIL Open Font
License 1.1 ([licenses/OFL-1.1.txt](licenses/OFL-1.1.txt),
[licenses/FONT-NOTICES.md](licenses/FONT-NOTICES.md)).
