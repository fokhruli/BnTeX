"""Installed trees where TeX cannot checksum font files (MiKTeX packages).

MiKTeX's pdfTeX reads only TeX inputs with \\pdfmdfivesum and does not expand
$TEXMF roots, so the fonts/ files of an installed package are unreadable there.
On MiKTeX, BnTeX then finds them by bare name through the font search and
compares every bank's TFM widths with the MD5-checked shaping tables.

TeX Live can reproduce that layout with separate input and font search paths.
It never needs the fallback itself, so these tests preset the switch.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from bntex import distribution as d
from bntex.native_profile import PINNED_BOLD_SHA256
from bntex.tex_export import FONT_SHA
from test_installed_distribution import tds, run, text, flat_runtime, diagnostic_text, ROOT  # noqa: F401  (fixture import)

REGULAR, BOLD = 'bnf'+FONT_SHA[:16], 'bnf'+PINNED_BOLD_SHA256[:16]
BANKS = [(f'{REGULAR}b{k}', 'p') for k in range(3)] + [(f'{BOLD}b{k}', 'b') for k in range(3)]
PRESET = (r'\ExplSyntaxOn\bool_new:N\g__bnd_font_search_bool'
          r'\bool_gset_true:N\g__bnd_font_search_bool\ExplSyntaxOff' + '\n')


def miktex() -> bool:
    banner = subprocess.run([shutil.which('pdflatex'), '--version'], capture_output=True, text=True).stdout
    return 'MiKTeX' in banner


def checks(calls):
    lines = '\n'.join(rf'\__bnd_check_metrics:nn{{{bank}}}{{{face}}}' for bank, face in calls)
    return ('\\documentclass{article}\n\\usepackage{bntex}\n\\ExplSyntaxOn\n' + lines +
            '\n\\ExplSyntaxOff\n\\begin{document}\nবাংলা\n\\end{document}\n')


def test_metric_check_accepts_every_bank_and_rejects_the_other_face(tds, tmp_path):
    empty = tmp_path/'empty-home'; empty.mkdir()
    folder = tmp_path/'project'; flat_runtime(tds, folder)
    rc, log = run(empty, folder, checks(BANKS)); assert rc == 0, log[-8000:]
    wrong = tmp_path/'wrong'; flat_runtime(tds, wrong)
    rc, log = run(empty, wrong, checks([(f'{BOLD}b0', 'p')])); assert rc != 0
    assert f'installed metrics changed: {BOLD}b0' in diagnostic_text(log), log[-8000:]


def split_tree(tree: Path, base: Path) -> tuple[Path, Path]:
    """TeX files on the input path; fonts only on the font search paths."""
    tex, fonts = base/'tex', base/'fonts'
    tex.mkdir(parents=True); fonts.mkdir()
    for p in (tree/d.TEX_DIR).iterdir():
        shutil.copyfile(p, tex/p.name)
    for dirname in d.FONT_DIRS.values():
        for p in (tree/dirname).iterdir():
            shutil.copyfile(p, fonts/p.name)
    return tex, fonts


def run_split(tex: Path, fonts: Path, folder: Path, body: str, home: Path):
    folder.mkdir(parents=True)
    (folder/'main.tex').write_text(body, encoding='utf-8')
    env = dict(os.environ)
    for key in ('TEXINPUTS', 'TTFONTS', 'TFMFONTS', 'ENCFONTS', 'TEXFONTMAPS', 'PYTHONPATH', 'openin_any'):
        env.pop(key, None)
    sep = os.pathsep
    env.update(TEXMFHOME=str(home), TEXINPUTS=f'{tex}{sep}', TFMFONTS=f'{fonts}{sep}',
               ENCFONTS=f'{fonts}{sep}', TTFONTS=f'{fonts}{sep}', PATH='/no-runtime-programs',
               openout_any='p', MKTEXPK='0', MKTEXTFM='0', max_print_line='10000')
    p = subprocess.run([shutil.which('pdflatex'), '-no-shell-escape', '-halt-on-error',
                        '-interaction=nonstopmode', 'main.tex'], cwd=folder, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    return p.returncode, p.stdout.decode('utf8', 'replace')


@pytest.fixture
def split(tds, tmp_path):
    if miktex():
        pytest.skip('MiKTeX ignores TFMFONTS/ENCFONTS/TTFONTS; see the manual MiKTeX check')
    home = tmp_path/'empty-home'; home.mkdir()
    tex, fonts = split_tree(tds, tmp_path/'installed')
    return tex, fonts, home


def test_font_search_install_compiles(split, tmp_path):
    tex, fonts, home = split
    body = (ROOT/'examples/installed/main.tex').read_text(encoding='utf-8')
    # Without the fallback the layout really hides the fonts from \pdfmdfivesum.
    rc, log = run_split(tex, fonts, tmp_path/'strict', body, home)
    assert rc != 0 and 'installed asset unreadable' in diagnostic_text(log), log[-8000:]
    rc, log = run_split(tex, fonts, tmp_path/'fallback', PRESET + body, home)
    assert rc == 0, log[-8000:]
    assert 'বাংলা আমাদের মাতৃভাষা।' in text(tmp_path/'fallback')


def test_font_search_install_rejects_mismatched_metrics(split, tmp_path):
    tex, fonts, home = split
    # A Bold metric file under the Regular name, as from a mixed-up install.
    shutil.copyfile(fonts/f'{BOLD}b0.tfm', fonts/f'{REGULAR}b0.tfm')
    body = PRESET + (ROOT/'examples/installed/main.tex').read_text(encoding='utf-8')
    rc, log = run_split(tex, fonts, tmp_path/'mixed', body, home)
    assert rc != 0
    assert f'installed metrics changed: {REGULAR}b0' in diagnostic_text(log), log[-8000:]
