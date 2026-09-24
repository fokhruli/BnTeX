import json
from pathlib import Path
import shutil
import subprocess
import pytest
from bntex.build import prepare, verify, digest


def compile_pdf(directory):
    p=subprocess.run(['pdflatex','-no-shell-escape','-halt-on-error','-interaction=nonstopmode','input.tex'],
       cwd=directory,capture_output=True,text=True,errors="replace",timeout=40)
    return p

@pytest.mark.integration
def test_build_determinism_and_native_roundtrip(tmp_path,minimal,fonts,tex_tools):
    a=tmp_path/'build-a'; b=tmp_path/'build-b'
    m=prepare([minimal],fonts,a); n=prepare([minimal],fonts,b)
    assert m==n
    assert verify(a)==m
    for info in m['styles'].values():
        original=next(p for p in fonts.values() if digest(p.read_bytes())==info['sha256'])
        assert (a/info['prepared_font_filename']).read_bytes()==original.read_bytes()
    assert len(m['styles']['regular']['banks'])>=2
    assert '\\includegraphics' not in (a/'bntex-cache.tex').read_text()
    proc=compile_pdf(a)
    assert proc.returncode==0,proc.stdout[-5000:]
    text=subprocess.check_output(['pdftotext',str(a/'input.pdf'),'-'],text=True)
    assert 'বাংলা ভাষা স্বাস্থ্য ক্ষ কি কো কর্ম' in text
    assert text.count('বাংলা ভাষা')>=3  # regular, bold, and footnote
    assert 'Missing character' not in (a/'input.log').read_text()
    prepare([minimal],fonts,a) # explicitly marked generated build may be replaced
    assert verify(a)==m

@pytest.mark.integration
def test_missing_word_is_an_error(tmp_path,minimal,fonts,tex_tools):
    out=tmp_path/'build';prepare([minimal],fonts,out)
    p=out/'input.tex';p.write_text(p.read_text().replace('স্বাস্থ্য','অনুপস্থিতশব্দ'))
    result=compile_pdf(out)
    assert result.returncode!=0 and 'Uncached Bengali word' in result.stdout

@pytest.mark.integration
def test_asset_tampering_is_rejected(tmp_path,minimal,fonts,tex_tools):
    out=tmp_path/'build';m=prepare([minimal],fonts,out)
    name=next(x for x in m['files'] if x.endswith('.enc'))
    with (out/name).open('a') as f:f.write('% modified\n')
    with pytest.raises(ValueError,match='changed'):verify(out)
    result=compile_pdf(out)
    assert result.returncode!=0 and 'Prepared asset changed' in result.stdout

@pytest.mark.integration
def test_missing_style_is_an_error(tmp_path,minimal,fonts,tex_tools):
    out=tmp_path/'build';prepare([minimal],{'regular':fonts['regular']},out)
    result=compile_pdf(out)
    assert result.returncode!=0 and 'was not prepared' in result.stdout

@pytest.mark.integration
def test_output_directory_safety(tmp_path,minimal,fonts,tex_tools):
    out=tmp_path/'keep';out.mkdir();(out/'important.txt').write_text('keep me')
    with pytest.raises(ValueError,match='nonempty unmarked'):prepare([minimal],fonts,out)
    assert (out/'important.txt').read_text()=='keep me'
    with pytest.raises(ValueError,match='inside'):prepare([minimal],fonts,tmp_path)
    with pytest.raises(ValueError,match='regular'):prepare([minimal],{'sans':fonts['sans']},tmp_path/'other')
    reserved=tmp_path/'bntex-cache.tex';reserved.write_text(r'\bn{ক}')
    with pytest.raises(ValueError,match='non-reserved'):prepare([reserved],fonts,tmp_path/'other')
    with pytest.raises(ValueError,match='unique'):prepare([minimal,minimal],fonts,tmp_path/'other')

@pytest.mark.integration
def test_incomplete_build_does_not_replace_previous(tmp_path,minimal,fonts,tex_tools):
    out=tmp_path/'build';previous=prepare([minimal],fonts,out)
    minimal.write_text('\\bn{' + chr(0x10ffff) + '}')
    with pytest.raises(ValueError):prepare([minimal],fonts,out)
    assert verify(out)==previous

@pytest.mark.integration
def test_explicit_sans_and_size_color(tmp_path,minimal,fonts,tex_tools):
    source=minimal.read_text().replace(r'\end{document}',r'''\par
{\fontsize{20}{24}\selectfont\bn[sans]{স্বাস্থ্য বাংলা}}
\end{document}''')
    minimal.write_text(source)
    out=tmp_path/'build';prepare([minimal],fonts,out)
    result=compile_pdf(out)
    assert result.returncode==0,result.stdout[-5000:]
    text=subprocess.check_output(['pdftotext',str(out/'input.pdf'),'-'],text=True)
    assert 'স্বাস্থ্য বাংলা' in text
