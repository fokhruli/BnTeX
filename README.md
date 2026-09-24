# BnTeX

Experimental Bengali typesetting for pdfLaTeX.

This private repository is the development home for BnTeX. The initial implementation, documentation, tests, and staged native-shaper roadmap are introduced through a pull request rather than pushed directly to `main`.

The first backend prepares Unicode Bengali text with HarfBuzz, then renders native font glyphs with pdfLaTeX and shell execution disabled. A preprocessing-free TeX-native Bengali shaper is a separate development milestone, not a completed capability.

Font binaries, credentials, and generated build directories must not be committed. No CTAN or PyPI release is implied by this repository.
