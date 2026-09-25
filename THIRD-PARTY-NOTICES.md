# Third-party implementation references and notices

## HarfBuzz Indic shaping

The Bengali-only grammar, phase ordering, reordering, glyph provenance, filtering,
and ligature-component handling in `native_model.py` and `native_layout.py` are
adapted from the documented Indic model and informed by HarfBuzz 10.2.0 source.
This is an independent **runtime implementation**, not a claim to have invented a
new Bengali shaping algorithm. The model does not link to or call HarfBuzz, and
HarfBuzz is used only by the separate comparison tests/reference preparer.

Pinned reference revision: `7b27c8edd46c674e01dd226fa9e1aa7549f5c436`.
Relevant files include `src/hb-ot-shaper-indic-machine.rl`,
`src/hb-ot-shaper-indic.cc`, `src/hb-ot-layout-gsubgpos.hh`,
`src/hb-ot-shaper-indic-table.cc`, and `src/OT/Layout/GPOS/MarkBasePosFormat1.hh`.
Reference repository: https://github.com/harfbuzz/harfbuzz

The source notice is retained here for these adaptations:

> Copyright © 2011,2012 Google, Inc.
> Copyright © 2007,2008,2009,2010 Red Hat, Inc.
> Copyright © 2010,2012 Google, Inc.
>
> Permission is hereby granted, without written agreement and without
> license or royalty fees, to use, copy, modify, and distribute this
> software and its documentation for any purpose, provided that the
> above copyright notice and the following two paragraphs appear in
> all copies of this software.
>
> IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE TO ANY PARTY FOR
> DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES
> ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN
> IF THE COPYRIGHT HOLDER HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH
> DAMAGE.
>
> THE COPYRIGHT HOLDER SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING,
> BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
> FITNESS FOR A PARTICULAR PURPOSE. THE SOFTWARE PROVIDED HEREUNDER IS
> ON AN "AS IS" BASIS, AND THE COPYRIGHT HOLDER HAS NO OBLIGATION TO
> PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR MODIFICATIONS.

The contextual matching / positioning headers carry the repository's applicable
HarfBuzz license; this notice supplements, rather than replaces, the project MIT
license. No complete HarfBuzz source or library binary is redistributed here.
The fixed Bengali character-property projection is cross-checked against the
Unicode 16.0 data used by this pinned HarfBuzz revision. Original source Unicode
is never replaced by its normalized working sequence.

## FontTools and Noto

FontTools is a separately installed compiler dependency. It is not used by the
model's shape operation after a profile has been compiled. Its own license
continues to apply to FontTools.

Noto Serif Bengali is a separately installed, locally supplied font. No font
binary, glyph outline, or rendered font asset is committed. Compiling rules does
not replace the font's license or establish rights to redistribute derivatives.
The initial compiler deliberately accepts only the documented exact font binary.
