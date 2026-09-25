# Private release-readiness work

This is a review checkpoint, not a release or an upload authorization. The
original cached backend and the experimental fixed-profile native path coexist.
The package-name, font/profile distribution policy, browser reproduction,
independent user, native visual review and long-document interaction target
remain separately recorded in `RELEASE-READINESS.json`.

## Mechanical preflight

Use a clean tracked checkout. The new preflight rejects unsupported artifacts,
renamed font signatures, symlinks, missing documentation/licenses, dirty tracked
sources and mismatched authoritative/wheel TeX resources. It reads only tracked
regular files, so adjacent local secrets/build directories are not archived.
This is a basic source check, not comprehensive security or legal analysis.

```
mkdir -p build/manual
pdflatex -no-shell-escape -halt-on-error -interaction=nonstopmode \
  -output-directory=build/manual docs/manual/bntex-manual.tex
pdflatex -no-shell-escape -halt-on-error -interaction=nonstopmode \
  -output-directory=build/manual docs/manual/bntex-manual.tex
python tools/release_preflight.py --out build/source-review.json \
  --manual-pdf build/manual/bntex-manual.pdf \
  --archive build/bntex-source-review.zip
```

The ZIP contains complete tracked sources plus the generated manual PDF and its
source under `bntex-source-review/`. It is a **private developer review archive**,
not a CTAN-ready distribution: public naming, directory/dependency decisions,
font rights and private-reference cleanup still require review. No automatic
publication command exists. Fonts in the user-owned installation are not included.

`python tools/release_preflight.py --out build/readiness.json --require-ready`
returns 1 while gates are blocked/pending (2 on a mechanical/schema error).
Ordinary mechanical review mode can return 0 despite pending human gates; its
report lists those gates explicitly. A `passed` entry requires an evidence field,
but JSON does not authenticate that evidence. A maintainer must verify it.

## Source and wheel packaging

The updated source manifest includes `.def` modules, authoritative TeX sources,
tests, corpus fixtures, tools, documentation and examples, plus both licenses.
The Python wheel continues to package `.sty` and `.def` runtime resources.
The dry-run workflow builds source/wheel distributions, checks resource identity,
compiles the manual and audits the full clean tree. It uploads no package/font
artifacts and does not create releases. Dry-run packages are not publication.

## Actual browser and second-user checks

No Overleaf integration was available to this implementation session. No browser
success or independent person is claimed. Use the staged native-project example,
its no-shell `latexmkrc`, the guide in `OVERLEAF-NATIVE.md`, and a new Overleaf
project with pdfLaTeX selected. Record TeX Live version, source revision, log,
PDF and installation identity, then add a word only after import and recompile.
Verify headings/bookmarks and copy/paste. Do not regenerate vocabulary.

A second person must install from the complete source-review archive rather than
from a developer working tree. The agent running another local directory does
not count as a second person. Their actual name/date/evidence belongs in a new
review record, not a fabricated update to old per-case ledgers.

## Primary guidance

CTAN requires an informative README, license, complete clean archive, readable
PDF documentation and its source. Handwritten package files are valid source;
`.dtx` is not universally mandatory. These are packaging requirements, not an
acceptance guarantee: https://ctan.org/help/upload-pkg

Overleaf's compiler and TeX Live selections are project-specific settings:
https://docs.overleaf.com/getting-started/recompiling-your-project/selecting-a-tex-live-version-and-latex-compiler

The original roadmap remains design provenance. Current supported interfaces
and unresolved gates are in README.md and the native documentation. Automatic
wrapper-free input remains deferred; no public release is scheduled or authorized.
