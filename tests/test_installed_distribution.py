"""Complete TDS installation tests, separate from project-local authoring tests.

No program search path, source checkout TEXINPUTS, or project-local assets are
provided to pdfTeX. The default Kpathsea read policy is tested, not overwritten.
Restricted-read failure is an explicit unresolved acceptance case.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import pytest
from bntex import distribution as d
from bntex.tex_export import FONT_SHA
from bntex.native_profile import PINNED_BOLD_SHA256

ROOT=Path(__file__).resolve().parents[1]
REG=Path(os.getenv('BNTEX_REGULAR_FONT','/usr/share/fonts/truetype/noto/NotoSerifBengali-Regular.ttf'))
BOLD=Path(os.getenv('BNTEX_BOLD_FONT','/usr/share/fonts/truetype/noto/NotoSerifBengali-Bold.ttf'))


def arguments(pdf):
    return dict(license_file=ROOT/'licenses/OFL-1.1.txt',manual_pdf=pdf,
                manual_source=ROOT/'docs/distribution/bntex-installation.tex',
                example=ROOT/'examples/installed/main.tex', readme=ROOT/'docs/distribution/README.md',
                notices=ROOT/'licenses/FONT-NOTICES.md', code_license=ROOT/'LICENSE',
                third_party_notices=ROOT/'THIRD-PARTY-NOTICES.md')

@pytest.fixture(scope='module')
def tds(tmp_path_factory):
    for tool in ('pdflatex','pltotf','pdftotext'):
        if not shutil.which(tool):
            if os.getenv('BNTEX_REQUIRE_INTEGRATION')=='1':pytest.fail('Missing '+tool)
            pytest.skip('Missing '+tool)
    if not REG.exists() or not BOLD.exists():
        if os.getenv('BNTEX_REQUIRE_INTEGRATION')=='1':pytest.fail('Audited fonts missing')
        pytest.skip('Audited fonts missing')
    base=tmp_path_factory.mktemp('installed-family')
    p=subprocess.run([shutil.which('pdflatex'),'-no-shell-escape','-halt-on-error',
                      '-interaction=nonstopmode','-output-directory='+str(base),
                      str(ROOT/'docs/distribution/bntex-installation.tex')],
                      cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
    assert p.returncode==0,p.stdout.decode(errors='replace')[-3000:]
    d.assemble(REG,BOLD,base/'tds',**arguments(base/'bntex-installation.pdf'))
    return base/'tds'


def run(tree,folder,body=None,*,read_policy=None):
    folder.mkdir(parents=True,exist_ok=True)
    if body is None:body=(ROOT/'examples/installed/main.tex').read_text()
    (folder/'main.tex').write_text(body)
    env=dict(os.environ)
    for key in ('TEXINPUTS','TTFONTS','TFMFONTS','ENCFONTS','TEXFONTMAPS','PYTHONPATH','openin_any'):
        env.pop(key,None)
    env.update(TEXMFHOME=str(tree),PATH='/no-runtime-programs',openout_any='p',
               MKTEXPK='0',MKTEXTFM='0',SOURCE_DATE_EPOCH='1',FORCE_SOURCE_DATE='1',max_print_line='10000')
    if read_policy is not None:env['openin_any']=read_policy
    p=subprocess.run([shutil.which('pdflatex'),'-no-shell-escape','-halt-on-error',
                      '-interaction=nonstopmode','-recorder','main.tex'],
                      cwd=folder,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
    return p.returncode,p.stdout.decode('utf8','replace')


def text(folder):
    return subprocess.check_output([shutil.which('pdftotext'),str(folder/'main.pdf'),'-']).decode('utf8')


def test_document_only_folder_and_unseen_edit(tds,tmp_path):
    root=tmp_path/'author';root.mkdir()
    rc,log=run(tds,root);assert rc==0,log[-8000:]
    assert 'বাংলা আমাদের মাতৃভাষা।' in text(root)
    assert all(p.suffix not in ('.sty','.def','.ttf','.tfm','.enc') for p in root.iterdir())
    assert not any(k in log for k in ('Missing character:', 'Font Warning','Overfull'))
    new='বহুমাত্রিকীকরণের পরীক্ষায় একটি সম্পূর্ণ নতুন বাক্য যুক্ত হলো।'
    src=(root/'main.tex').read_text().replace(r'\end{document}',new+'\n'+r'\end{document}')
    rc,log=run(tds,root,src);assert rc==0,log[-8000:]
    assert new in text(root)
    inputs=[x[6:] for x in (root/'main.fls').read_text().splitlines() if x.startswith('INPUT ')]
    assert not any(Path(x).suffix in ('.py','.json','.gz') or Path(x).name=='bntex-cache.tex' for x in inputs)
    assert any('/fonts/truetype/public/bntex/' in x for x in inputs)
    assert d.verify(tds)['vocabulary'] is None


def test_move_entire_tree_and_compile_again(tds,tmp_path):
    copied=tmp_path/'old-tree';shutil.copytree(tds,copied)
    moved=tmp_path/'relocated tree';copied.rename(moved)
    rc,log=run(moved,tmp_path/'elsewhere');assert rc==0,log[-8000:]
    assert str(copied) not in log
    assert 'বাংলা শিরোনাম' in text(tmp_path/'elsewhere')
    d.verify(moved)

@pytest.mark.parametrize('suffix',['.ttf','.tfm','.enc','.def','.sty'])
@pytest.mark.parametrize('fault',['missing','changed'])
def test_missing_and_changed_assets_fail(tds,tmp_path,suffix,fault):
    tree=tmp_path/'tree';shutil.copytree(tds,tree)
    # Select manifest-checked files, not the wrapper/loader self bootstrap.
    patterns={'.sty':'bntex-native-styles.sty','.def':'bntex-native-tables.def'}
    file=next(tree.rglob(patterns.get(suffix,'bnf*'+suffix)))
    if fault=='missing':file.unlink()
    else:file.write_bytes(file.read_bytes()+b'\n% accidental change\n')
    rc,log=run(tree,tmp_path/'doc');assert rc!=0
    assert 'Fatal error' in log
    assert not (tmp_path/'doc/main.pdf').exists()


def test_verified_full_paths_do_not_load_local_font_shadow(tds,tmp_path):
    folder=tmp_path/'doc';folder.mkdir()
    for name in ['bnf'+FONT_SHA[:16]+'.ttf','bnf'+FONT_SHA[:16]+'b0.tfm','bnf'+FONT_SHA[:16]+'b0.enc']:
        (folder/name).write_bytes(b'not a valid font asset')
    rc,log=run(tds,folder);assert rc==0,log[-8000:]
    assert 'বাংলা আমাদের মাতৃভাষা।' in text(folder)


def test_restrictive_read_policy_fails_without_relaxation(tds,tmp_path):
    rc,log=run(tds,tmp_path/'doc',read_policy='p')
    assert rc!=0 and 'read-policy' in log
    assert not (tmp_path/'doc/main.pdf').exists()
    code=(ROOT/'tex/latex/bntex/bntex-distribution.sty').read_text()
    assert 'write18' not in code and 'openin_any=' not in code


def test_missing_default_profile_does_not_select_cached(tds,tmp_path):
    tree=tmp_path/'tree';shutil.copytree(tds,tree)
    (tree/d.TEX_DIR/'bntex-default-profile.def').unlink()
    rc,log=run(tree,tmp_path/'doc')
    assert rc!=0 and 'default font profile is missing' in log


def test_explicit_legacy_option_needs_no_native_profile(tds,tmp_path):
    src=r'\documentclass{article}\usepackage[cached]{bntex}\begin{document}Legacy interface loaded.\end{document}'
    rc,log=run(tds,tmp_path/'doc',src);assert rc==0,log[-3000:]
    assert 'bntex-cached.sty' in log and 'bntex-default-profile.def' not in log

@pytest.mark.parametrize('option',['invented','cached,synthetic-italic'])
def test_bad_package_options_fail(tds,tmp_path,option):
    src='\\documentclass{article}\n\\usepackage['+option+']{bntex}\n\\begin{document}Test\\end{document}'
    rc,log=run(tds,tmp_path/'doc',src);assert rc!=0


def test_installed_moving_arguments_and_math(tds,tmp_path):
    src=r'''\documentclass{article}
\usepackage[synthetic-italic]{bntex}
\usepackage{hyperref}\usepackage{amsmath}\usepackage{xcolor}
\hypersetup{pdftitle={বাংলা নথি}}
\begin{document}
\tableofcontents\section{গবেষণার ফলাফল}\label{sec:bangla}
\textbf{মোটা}\textit{বাঁকানো}\underline{দাগ}\textcolor{blue}{রঙিন}
\footnote{বাংলা পাদটীকা} $x_{\text{নতুন}}=1$\ref{sec:bangla}
\end{document}'''
    root=tmp_path/'doc'
    for _ in range(2):
        rc,log=run(tds,root,src);assert rc==0,log[-8000:]
    from pypdf import PdfReader
    pdf=PdfReader(root/'main.pdf')
    assert pdf.metadata.title=='বাংলা নথি'
    assert pdf.outline[0].title=='গবেষণার ফলাফল'
    assert 'বাংলা পাদটীকা' in text(root)


def test_complete_deterministic_local_archives(tds,tmp_path):
    a=d.pack(tds,tmp_path/'a');b=d.pack(tds,tmp_path/'b')
    assert a['archives']==b['archives'] and not a['publication_performed']
    with zipfile.ZipFile(tmp_path/'a/bntex.tds.zip') as z:
        for name in [d.TEX_DIR+'/bntex.sty',d.TEX_DIR+'/bntex-default-profile.def',
                     d.DOC_DIR+'/OFL-1.1.txt',d.DOC_DIR+'/bntex-manual.pdf',
                     d.DOC_DIR+'/bntex-manual.tex',d.SOURCE_DIR+'/bntex/distribution.py',
                     d.SOURCE_DIR+'/bntex/data/bntex-auto.sty']:
            assert name in z.namelist()
        assert sum(n.endswith('.ttf') for n in z.namelist())==2
        assert sum(n.endswith('.tfm') for n in z.namelist())==6
    with zipfile.ZipFile(tmp_path/'a/bntex-ctan-candidate.zip') as z:
        assert 'bntex.tds.zip' in z.namelist() and 'bntex/README.md' in z.namelist()
    with pytest.raises(ValueError):d.pack(tds,tmp_path/'a')

@pytest.mark.parametrize('name',['../bad.ttf','/bad.tfm','x/other.enc','x.json','x\\other.sty','X.TTF'])
def test_invalid_asset_paths(name):
    with pytest.raises(ValueError):d.tds_path(name)


def test_verify_rejects_unlisted_file(tds,tmp_path):
    tree=tmp_path/'tree';shutil.copytree(tds,tree);(tree/'rogue.txt').write_text('unexpected')
    with pytest.raises(ValueError,match='Unlisted'):d.verify(tree)


@pytest.mark.parametrize('field,value', [('schema',True),('font_sha256','0'*64),
    ('bold_profile_sha256','0'*64),('vocabulary',[])])
def test_verify_rejects_bad_identity(tds,tmp_path,field,value):
    tree=tmp_path/'tree';shutil.copytree(tds,tree)
    path=tree/d.DOC_DIR/'distribution-manifest.json'
    m=json.loads(path.read_text());m[field]=value;path.write_text(json.dumps(m))
    with pytest.raises(ValueError):d.verify(tree)


def test_verify_rejects_duplicate_manifest_keys(tds,tmp_path):
    tree=tmp_path/'tree';shutil.copytree(tds,tree)
    path=tree/d.DOC_DIR/'distribution-manifest.json'
    path.write_text(path.read_text().replace('"schema": 1','"schema": 1, "schema": 1'))
    with pytest.raises(ValueError,match='Duplicate'):d.verify(tree)


def test_incomplete_license_cannot_build(tds,tmp_path):
    wrong=tmp_path/'OFL.txt';wrong.write_text('SIL OPEN FONT LICENSE Version 1.1')
    args=arguments(tds/d.DOC_DIR/'bntex-manual.pdf');args['license_file']=wrong
    with pytest.raises(ValueError,match='Complete pinned font license'):d.assemble(REG,BOLD,tmp_path/'out',**args)
    assert not (tmp_path/'out').exists()


def test_sources_and_font_names_are_reproducible(tds,tmp_path):
    m=d.assemble(REG,BOLD,tmp_path/'new',**arguments(tds/d.DOC_DIR/'bntex-manual.pdf'))
    assert m==d.verify(tds)
    assert all(not str(ROOT).encode() in p.read_bytes()
               for p in (tmp_path/'new'/d.TEX_DIR).glob('*'))


def test_maintainer_builder_reproduces_complete_archives(tds,tmp_path):
    reports=[]
    for name in ('first','second'):
        out=tmp_path/name
        cmd=[sys.executable,str(ROOT/'tools/build_distribution.py'),'--out',str(out),
             '--regular-font',str(REG),'--bold-font',str(BOLD)]
        result=subprocess.run(cmd,cwd=tmp_path,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),
                              capture_output=True,text=True,timeout=120)
        assert result.returncode==0,result.stdout+result.stderr
        reports.append(json.loads((out/'build-report.json').read_text()))
        d.verify(out/'texmf')
    assert reports[0]['archives']==reports[1]['archives']
    assert reports[0]['release_ready'] is False
