"""Complete TDS installation tests, separate from project-local authoring tests.

No program search path, source checkout TEXINPUTS, or project-local assets are
provided to pdfTeX. The default Kpathsea read policy is tested, not overwritten.
Restricted-read behavior is probed independently because pdfTeX versions differ.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
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
    # Explicit UTF-8: some pdftotext builds (e.g. on Windows) default to Latin-1.
    return subprocess.check_output([shutil.which('pdftotext'),'-enc','UTF-8',str(folder/'main.pdf'),'-']).decode('utf8')


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
    # Select runtime files explicitly: the TDS includes reproducible .sty
    # sources too, and filesystem traversal order is not stable across hosts.
    names={'.sty':'bntex-native-styles.sty','.def':'bntex-native-tables.def',
           '.ttf':'bnf'+FONT_SHA[:16]+'.ttf',
           '.tfm':'bnf'+FONT_SHA[:16]+'b0.tfm',
           '.enc':'bnf'+FONT_SHA[:16]+'b0.enc'}
    file=tree/d.tds_path(names[suffix])
    assert file.is_file() and not file.is_relative_to(tree/d.SOURCE_DIR)
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


def flat_runtime(tree,folder):
    """Copy only runtime assets beside the document, as in a project upload."""
    folder.mkdir(parents=True)
    for dirname in (d.TEX_DIR,*d.FONT_DIRS.values()):
        for p in (tree/dirname).iterdir():
            if p.is_file():shutil.copyfile(p,folder/p.name)


def test_project_folder_copy_without_tds_root(tds,tmp_path):
    empty=tmp_path/'empty-home';empty.mkdir()
    folder=tmp_path/'project';flat_runtime(tds,folder)
    rc,log=run(empty,folder);assert rc==0,log[-8000:]
    assert 'বাংলা আমাদের মাতৃভাষা।' in text(folder)
    # The fallback keeps the pinned checksum: a changed local copy must fail.
    damaged=tmp_path/'damaged-project';flat_runtime(tds,damaged)
    name='bnf'+PINNED_BOLD_SHA256[:16]+'.ttf'
    (damaged/name).write_bytes((damaged/name).read_bytes()+b'corrupt')
    rc,log=run(empty,damaged);assert rc!=0
    assert 'installed asset changed: '+name in diagnostic_text(log),log[-8000:]
    assert not (damaged/'main.pdf').exists()


def checksum_probe(tree, folder, *, read_policy):
    """Measure the engine primitive before testing the package under that policy.

    This does not infer capabilities from a release number or accept an arbitrary
    package failure. A readable primitive must agree with the actual file hash.
    """
    assets=sorted(p for dirname in d.FONT_DIRS.values()
                  for p in (tree/dirname).iterdir() if p.is_file())
    lines=[r'\documentclass{article}\begin{document}Probe.']
    for i,path in enumerate(assets):
        name='$TEXMFHOME/'+str(path.relative_to(tree))
        lines.append(r'\typeout{BNTEX-READ|'+str(i)+r'|\pdfmdfivesum file{'+name+'}}')
    lines.append(r'\end{document}')
    rc,log=run(tree,folder,'\n'.join(lines),read_policy=read_policy)
    assert rc==0,log[-4000:]
    observed=dict((int(i),value) for i,value in re.findall(r'BNTEX-READ\|(\d+)\|([0-9A-F]*)',log))
    assert set(observed)==set(range(len(assets)))
    expected={i:hashlib.md5(p.read_bytes()).hexdigest().upper() for i,p in enumerate(assets)}
    assert all(value in ('',expected[i]) for i,value in observed.items())
    return all(observed.values()),log.splitlines()[0]


def diagnostic_text(log):
    """Normalize LaTeX message wrapping, not its diagnostic meaning."""
    unwrapped=re.sub(r'(?m)^\(bntex-native\)[ \t]*','',log)
    return ' '.join(unwrapped.split())


def test_diagnostic_matching_preserves_error_and_asset_identity():
    wrapped=('Native Bengali shaping rejected: installed\n'
             '(bntex-native)                      asset changed:\n'
             '(bntex-native)                 fonts/test.ttf.')
    normalized=diagnostic_text(wrapped)
    assert 'installed asset changed: fonts/test.ttf' in normalized
    assert 'installed asset unreadable:' not in normalized
    assert 'installed asset changed: fonts/other.ttf' not in normalized
    assert 'installed asset changed:' not in diagnostic_text('Undefined control sequence')


@pytest.mark.parametrize('read_policy',[None,'p'])
@pytest.mark.parametrize('suffix',['.ttf','.tfm','.enc'])
def test_read_policy_matches_primitive_without_relaxation(tds,tmp_path,suffix,read_policy):
    readable,banner=checksum_probe(tds,tmp_path/'probe',read_policy=read_policy)
    rc,log=run(tds,tmp_path/'doc',read_policy=read_policy)
    print(f'BNTEX-READ-POLICY|{read_policy or "default"}|readable={readable}|{banner}')
    if readable:
        # Validate rendering and the specific corrupted-asset diagnostic on
        # every readable policy. LaTeX can wrap error text even when the engine
        # max_print_line is high; unrelated failures must never count as a pass.
        assert rc==0,log[-8000:]
        assert 'বাংলা আমাদের মাতৃভাষা।' in text(tmp_path/'doc')
        tree=tmp_path/'damaged';shutil.copytree(tds,tree)
        name='bnf'+FONT_SHA[:16]+('' if suffix=='.ttf' else 'b0')+suffix
        path=tree/d.tds_path(name);path.write_bytes(path.read_bytes()+b'corrupt')
        rc,log=run(tree,tmp_path/'damaged-doc',read_policy=read_policy)
        assert rc!=0,log[-8000:]
        assert 'installed asset changed: '+d.tds_path(name) in diagnostic_text(log),log[-8000:]
        assert not (tmp_path/'damaged-doc/main.pdf').exists()
    else:
        assert rc!=0 and 'read-policy' in log,log[-8000:]
        assert not (tmp_path/'doc/main.pdf').exists()
    code=(ROOT/'tex/latex/bntex/bntex-distribution.sty').read_text()
    assert 'write18' not in code and 'openin_any=' not in code


def test_runtime_corruption_does_not_depend_on_source_copy_order(tds,tmp_path):
    tree=tmp_path/'tree';shutil.copytree(tds,tree)
    name='bntex-native-styles.sty'
    runtime=tree/d.TEX_DIR/name
    source=tree/d.SOURCE_DIR/'bntex/data'/name
    assert runtime.read_bytes()==source.read_bytes()
    # Breaking the non-executed reproducible source must not alter rendering.
    source.write_bytes(b'not executable TeX source')
    rc,log=run(tree,tmp_path/'source-damaged-doc');assert rc==0,log[-4000:]
    # Restore source, then corrupt runtime: the inverse MUST fail at runtime.
    source.write_bytes(runtime.read_bytes())
    runtime.write_bytes(runtime.read_bytes()+b'\n% runtime changed\n')
    rc,log=run(tree,tmp_path/'runtime-damaged-doc')
    assert rc!=0 and not (tmp_path/'runtime-damaged-doc/main.pdf').exists()


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
    with zipfile.ZipFile(tmp_path/'a/bntex-overleaf-starter.zip') as z:
        names=z.namelist()
        assert {'main.tex','README.md','bntex.sty','bntex-default-profile.def',
                'licenses/OFL-1.1.txt','licenses/LICENSE'}<=set(names)
        assert all('/' not in n for n in names if not n.startswith('licenses/'))
        assert sum(n.endswith('.ttf') for n in names)==2
    # Archives must be identical whichever OS builds them: Unix entry flags and
    # LF-only text, as CTAN and TeX Live expect.
    binary=('.ttf','.tfm','.pdf','.zip')
    for archive in a['archives']:
        with zipfile.ZipFile(tmp_path/'a'/archive) as z:
            for info in z.infolist():
                assert info.create_system==3 and info.external_attr>>16==0o100644, info.filename
                if not info.filename.endswith(binary):
                    assert b'\r' not in z.read(info), info.filename
    with pytest.raises(ValueError):d.pack(tds,tmp_path/'a')


def test_overleaf_starter_compiles_without_installation(tds,tmp_path):
    d.pack(tds,tmp_path/'archives')
    project=tmp_path/'project'
    with zipfile.ZipFile(tmp_path/'archives/bntex-overleaf-starter.zip') as z:z.extractall(project)
    empty=tmp_path/'empty-home';empty.mkdir()
    rc,log=run(empty,project,(project/'main.tex').read_text(encoding='utf-8'));assert rc==0,log[-8000:]
    assert 'বাংলা আমাদের মাতৃভাষা।' in text(project)
    assert (project/'main.bnc').is_file()

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
