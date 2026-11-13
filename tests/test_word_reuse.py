"""Glyph-run reuse (bntex-native-reuse): identical output, file reuse, damage handling.

Uses the installed-distribution build, copied beside the document as in a
project upload, so the same checks run on TeX Live and MiKTeX.
"""
from __future__ import annotations
import re
from pypdf import PdfReader
from test_installed_distribution import tds, run, text, flat_runtime, diagnostic_text  # noqa: F401  (fixture import)

BODY = r'''\documentclass{article}
\usepackage[OPTIONS]{bntex}
\usepackage[unicode,hidelinks]{hyperref}
\begin{document}
\section{বাংলা শিরোনাম}
বাংলা আমাদের মাতৃভাষা। This mixes বাংলা and English. বাংলা আবার।
\textbf{মোটা বাংলা লেখা} এবং \textit{বাঁকানো বাংলা লেখা}।
\bnNative{ক্ষ জ্ঞ স্বাস্থ্য প্রযুক্তি কর্ম} {\Large বড় লেখা}
\footnote{পাদটীকায় বাংলা।}
EXTRA
\BnTeXStats
\end{document}
'''


def document(options, extra='', stats=True):
    body = BODY.replace('OPTIONS', options).replace('EXTRA', extra)
    return body.replace(r'\BnTeXStats', r'\BnTeXCacheStats' if stats else '')


def stats(log):
    m = re.findall(r'BNTEX-CACHE\|hits=(\d+)\|misses=(\d+)\|entries=(\d+)\|loaded=(\d+)'
                   r'\|rejected=(\d+)\|written=(\d+)', log)
    assert m, log[-4000:]
    return dict(zip(('hits', 'misses', 'entries', 'loaded', 'rejected', 'written'), map(int, m[-1])))


def pages(pdf):
    return [(p.get_contents().get_data(), p.extract_text()) for p in PdfReader(pdf).pages]


def project(tds, tmp_path, name):
    empty = tmp_path / 'empty-home'
    empty.mkdir(exist_ok=True)
    folder = tmp_path / name
    flat_runtime(tds, folder)
    return empty, folder


def test_cold_warm_and_disabled_output_identical(tds, tmp_path):
    empty, off = project(tds, tmp_path, 'off')
    rc, log = run(empty, off, document('synthetic-italic,no-word-cache', stats=False))
    assert rc == 0, log[-8000:]
    assert not (off / 'main.bnc').exists()
    reference = pages(off / 'main.pdf')
    _, on = project(tds, tmp_path, 'on')
    rc, log = run(empty, on, document('synthetic-italic'))
    assert rc == 0, log[-8000:]
    cold = stats(log)
    assert cold['loaded'] == 0 and cold['misses'] > 0 and cold['hits'] > 0
    assert (on / 'main.bnc').read_text(encoding='ascii').startswith('BNTEXCACHE|bntex-native-reuse/1/')
    assert pages(on / 'main.pdf') == reference
    rc, log = run(empty, on, document('synthetic-italic'))
    assert rc == 0, log[-8000:]
    warm = stats(log)
    assert warm['misses'] == 0 and warm['loaded'] == cold['entries'] and warm['rejected'] == 0
    assert pages(on / 'main.pdf') == reference


def test_new_words_are_shaped_and_damaged_or_stale_files_are_ignored(tds, tmp_path):
    empty, folder = project(tds, tmp_path, 'doc')
    rc, log = run(empty, folder, document('synthetic-italic'))
    assert rc == 0, log[-8000:]
    good = (folder / 'main.bnc').read_text(encoding='ascii')
    rc, log = run(empty, folder, document('synthetic-italic', 'সম্পূর্ণ নতুন শব্দভাণ্ডার।'))
    assert rc == 0, log[-8000:]
    assert stats(log)['misses'] == 3
    lines = good.splitlines(keepends=True)
    damaged = lines[:2] + [lines[2].replace(',', ',9', 1)] + lines[3:]
    for name, content in (('damaged', ''.join(damaged)),
                          ('stale', good.replace('/1/', '/1/0', 1)),
                          ('garbage', '\\def\\x{x}}{\nR|R|R\n')):
        (folder / 'main.bnc').write_text(content, encoding='ascii')
        rc, log = run(empty, folder, document('synthetic-italic'))
        assert rc == 0, (name, log[-8000:])
        s = stats(log)
        if name == 'damaged':
            assert s['rejected'] == 1 and s['loaded'] == len(lines) - 2 and s['misses'] == 1
        else:
            assert s['loaded'] == 0 and s['rejected'] == 0, name
        assert 'বাংলা আমাদের মাতৃভাষা।' in text(folder)


def test_memo_and_reuse_cannot_both_be_loaded(tds, tmp_path):
    empty, folder = project(tds, tmp_path, 'both')
    body = document('', stats=False).replace(r'\begin{document}', '\\usepackage{bntex-native-memo}\n\\begin{document}')
    rc, log = run(empty, folder, body)
    assert rc != 0 and 'bntex-native-reuse, not both' in diagnostic_text(log), log[-4000:]
