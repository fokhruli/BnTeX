import ctypes.util
import os
from pathlib import Path
import shutil
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope='session')
def fonts():
    root=Path('/usr/share/fonts/truetype/noto')
    result={
      'regular':Path(os.environ.get('BNTEX_REGULAR_FONT',root/'NotoSerifBengali-Regular.ttf')),
      'bold':Path(os.environ.get('BNTEX_BOLD_FONT',root/'NotoSerifBengali-Bold.ttf')),
      'sans':Path(os.environ.get('BNTEX_SANS_FONT',root/'NotoSansBengali-Regular.ttf')),
    }
    if not all(p.is_file() for p in result.values()) or not ctypes.util.find_library('harfbuzz'):
        if os.environ.get('BNTEX_REQUIRE_INTEGRATION')=='1':
            pytest.fail('Release gate: Bengali fonts or libharfbuzz are missing.')
        pytest.skip('Install three static Bengali fonts and libharfbuzz; see docs/TESTING.md.')
    return result

@pytest.fixture(scope='session')
def tex_tools():
    for tool in ['pdflatex','pltotf','pdftotext']:
        if not shutil.which(tool):
            if os.environ.get('BNTEX_REQUIRE_INTEGRATION')=='1':
                pytest.fail('Release gate: missing '+tool)
            pytest.skip('Missing '+tool)

@pytest.fixture
def minimal(tmp_path):
    p=tmp_path/'input.tex'
    p.write_text(r'''\documentclass{article}
\usepackage{bntex}
\BnTeXLoadCache{bntex-cache.tex}
\begin{document}
\bn{বাংলা ভাষা স্বাস্থ্য ক্ষ কি কো কর্ম}
\textbf{\bn{বাংলা ভাষা}}
\footnote{\bn{বাংলা ভাষা}}
\end{document}
''',encoding='utf8')
    return p
