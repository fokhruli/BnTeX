"""Copy and search in viewers that ignore /ActualText (PDF.js: Overleaf's preview, Firefox).

The bank encodings name glyphs /index<gid>, so pdfTeX's ToUnicode CMaps stayed
empty and such viewers copied raw slot codes. bntex-native-tounicode.def gives
every glyph its text. Viewers that honour /ActualText keep exact logical order.
"""
from __future__ import annotations
import collections
from dataclasses import asdict
import json
import re

import pytest
from pypdf import PdfReader

from bntex.native_profile import compile_profile
from bntex.tex_export import ZWSP, emit_tounicode, glyph_text
from test_installed_distribution import tds, run, text, flat_runtime, ROOT, REG  # noqa: F401  (fixture import)

# HarfBuzz decomposes these before shaping; the glyphs show the decomposed parts.
DECOMP = {'\u09cb': '\u09c7\u09be', '\u09cc': '\u09c7\u09d7',
          '\u09dc': '\u09a1\u09bc', '\u09dd': '\u09a2\u09bc', '\u09df': '\u09af\u09bc'}
INVISIBLE = {ZWSP, '\u200c', '\u200d', '\u25cc'}


def characters(s):
    return collections.Counter(c for ch in s for c in DECOMP.get(ch, ch) if c not in INVISIBLE)


@pytest.fixture(scope='module')
def regular():
    if not REG.is_file():
        pytest.skip('Audited fonts missing')
    from fontTools.ttLib import TTFont
    with TTFont(REG) as font:
        names = font.getGlyphOrder()
    return asdict(compile_profile(REG)), names


def test_every_oracle_glyph_has_its_input_text(regular):
    p, names = regular
    table = glyph_text(p, names)
    oracle = json.loads((ROOT/'corpus/oracles/noto-serif-bengali-regular-hb10.2.0.json').read_text('utf-8'))
    cases = {c['id']: c for c in json.loads((ROOT/'corpus/bengali-v1.json').read_text('utf-8'))['cases']}
    checked = 0
    for record in oracle['records']:
        if not record.get('glyphs'):
            continue
        source = bytes.fromhex(cases[record['id']]['utf8_hex']).decode('utf-8')
        glyphs = [g[0] for g in record['glyphs']]
        assert all(g in table for g in glyphs), record['id']
        copied = ''.join(table[g] for g in glyphs)
        if record['id'] == 'join-controls-05':
            # TA + HASANT + ZWJ is drawn, and so copied, as khanda ta.
            assert copied.replace(ZWSP, '') == '\u09ce'
        else:
            # Pre-base forms may come first, so compare characters, not order.
            assert characters(copied) == characters(source), (record['id'], source, copied)
        checked += 1
    assert checked >= 120


def test_table_maps_only_real_text(regular):
    p, names = regular
    lines = emit_tounicode(p, names).decode('ascii').splitlines()
    pairs = [m.groups() for m in map(re.compile(r'\\pdfglyphtounicode\{index(\d+)\}\{([0-9A-F ]+)\}').fullmatch, lines) if m]
    assert len(pairs) >= 600
    for _, codes in pairs:
        for code in map(lambda h: int(h, 16), codes.split()):
            assert code >= 0x20 and not 0x7F <= code <= 0x9F and not 0xD800 <= code <= 0xF8FF
    # The space glyph is only drawn for a hidden ZWJ/ZWNJ; real spaces are TeX glue.
    assert (str(names.index('space')), '200B') in pairs


BODY = r'''\documentclass{article}
\usepackage[synthetic-italic]{bntex}
\begin{document}
বাংলা মাতৃভাষা। স্বাস্থ্য উজ্জ্বল রাষ্ট্র

\textbf{বাংলা মাতৃভাষা।} \textit{স্বাস্থ্য}

কর্ম আমাদের র‍্যাব
\end{document}
'''


def test_copy_without_actualtext(tds, tmp_path):
    empty = tmp_path/'empty-home'; empty.mkdir()
    folder = tmp_path/'project'; flat_runtime(tds, folder)
    rc, log = run(empty, folder, BODY); assert rc == 0, log[-8000:]
    # pypdf reads only the fonts' ToUnicode CMaps, as PDF.js does.
    copied = ''.join(page.extract_text() for page in PdfReader(folder/'main.pdf').pages)
    for word in ('বাংলা', 'মাতৃভাষা।', 'স্বাস্থ্য', 'উজ্জ্বল', 'রাষ্ট্র'):
        assert copied.count(word) >= (2 if word in ('বাংলা', 'মাতৃভাষা।', 'স্বাস্থ্য') else 1), (word, copied)
    assert not any(ord(c) < 0x20 and c not in '\n\r\t' for c in copied), copied
    # Pre-base and reph forms keep their characters, in drawing order.
    for word in ('কর্ম', 'আমাদের'):
        assert any(characters(chunk) == characters(word) for chunk in re.split(r'\s+', copied)), (word, copied)
    # Viewers that honour /ActualText still get exact logical order.
    exact = text(folder)
    for word in ('বাংলা মাতৃভাষা।', 'কর্ম আমাদের র\u200d্যাব'):
        assert word in exact, exact
