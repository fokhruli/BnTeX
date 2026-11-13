"""Executed document contexts, bounded memoization and project-file contracts."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile
import pytest
from pypdf import PdfReader
from bntex.native_project import stage, verify, pack, relative, compile_once, installation_manifest
from test_native_tex import tex_profile, native_install, hb_reference, ROOT, need

FIELDS=('gid','cluster','x_advance','y_advance','x_offset','y_offset','flags')


@pytest.fixture
def runtime(native_install,tmp_path):
    target=tmp_path/'runtime';shutil.copytree(native_install,target);return target


def compile_document(root,body,*,preamble='',cls='article',passes=1,timeout=45):
    source=('\\documentclass[12pt]{'+cls+'}\n\\usepackage{bntex-native-integration}\n'
        '\\BnTeXNativeLoadProfile{bntex-native-profile.tex}\n'+preamble+'\n\\begin{document}\n'+body+'\n\\end{document}\n')
    (root/'main.tex').write_text(source,encoding='utf-8')
    rows=[compile_once(root,'main.tex',tag=f'test-{i+1}',timeout=timeout) for i in range(passes)]
    return rows[-1]


def assert_ok(row):
    assert row['status']=='success',row.get('diagnostic_tail',row)
    assert not row['recorder_forbidden_inputs']
    assert not any('Missing character:' in x for x in row['warnings'])


def glyph_runs(text):
    runs=[]
    for line in text.splitlines():
        if line.startswith('BNTEX-RUN|'):runs.append([])
        if line.startswith('BNTEX-GLYPH|'):runs[-1].append(list(map(int,line.split('|')[1:])))
    return runs


@pytest.mark.parametrize('name',['../a.tex','/a.tex','a//b.tex','./a.tex','.hidden/a.tex','a b.tex','a\\b.tex','C:/a.tex','বাংলা.tex','a/../b.tex','a/./b.tex','a\x00.tex'])
def test_path_rejections(name):
    with pytest.raises(ValueError):relative(name)


@pytest.mark.parametrize('name',['main.tex','chapters/one.tex','figures/one-2.pdf'])
def test_portable_paths(name):assert relative(name)==name


@pytest.fixture
def source_project(tmp_path):
    p=tmp_path/'sources';(p/'one').mkdir(parents=True);(p/'two').mkdir()
    (p/'main.tex').write_text(r'\documentclass{article}\begin{document}\input{one/body}\input{two/body}\end{document}')
    (p/'one/body.tex').write_text('one');(p/'two/body.tex').write_text('two')
    m={'schema':1,'backend':'native','main':'main.tex','files':['main.tex','one/body.tex','two/body.tex']}
    (p/'project.json').write_text(json.dumps(m));return p/'project.json'


def test_manifest_preserves_subdirectories_and_edits(source_project,native_install,tmp_path):
    out=tmp_path/'staged';stage(source_project,native_install,out)
    assert (out/'one/body.tex').read_text()=='one' and (out/'two/body.tex').read_text()=='two'
    assert not verify(out)['modified_sources']
    (out/'one/body.tex').write_text('new ordinary source content')
    report=verify(out);assert report['installation_intact'] and report['modified_sources']==['one/body.tex']
    assert report['source_edits_require_preparation'] is False
    assert not any('cache' in p.name for p in out.iterdir())


@pytest.mark.parametrize('fault',['duplicate','case-collision','outside','missing','main','backend','schema','extra','reserved','extension'])
def test_bad_manifests(fault,source_project,native_install,tmp_path):
    d=json.loads(source_project.read_text())
    if fault=='duplicate':d['files'].append('main.tex')
    if fault=='case-collision':d['files'].append('MAIN.tex')
    if fault=='outside':d['files'].append('../evil.tex')
    if fault=='missing':d['files'].append('missing.tex')
    if fault=='main':d['main']='none.tex'
    if fault=='backend':d['backend']='cached'
    if fault=='schema':d['schema']=True
    if fault=='extra':d['vocabulary']=[]
    if fault=='reserved':
        (source_project.parent/'bntex-native.sty').write_text('fake');d['files'].append('bntex-native.sty')
    if fault=='extension':
        (source_project.parent/'bad.py').write_text('');d['files'].append('bad.py')
    source_project.write_text(json.dumps(d));out=tmp_path/'out'
    with pytest.raises((ValueError,OSError)):stage(source_project,native_install,out)
    assert not out.exists()


def test_no_overwrite_or_symlink(source_project,native_install,tmp_path):
    out=tmp_path/'out';out.mkdir();(out/'keep').write_text('user work')
    with pytest.raises(ValueError):stage(source_project,native_install,out)
    assert (out/'keep').read_text()=='user work'
    (source_project.parent/'one/body.tex').unlink();(source_project.parent/'one/body.tex').symlink_to(source_project.parent/'two/body.tex')
    with pytest.raises(ValueError):stage(source_project,native_install,tmp_path/'other')


def test_asset_tamper(source_project,runtime,tmp_path):
    (runtime/'bntex-native-tables.def').write_text('% changed')
    with pytest.raises(ValueError):stage(source_project,runtime,tmp_path/'out')


def test_local_pack_is_deterministic_and_ignores_build_clutter(source_project,native_install,tmp_path):
    out=tmp_path/'out';stage(source_project,native_install,out)
    (out/'main.log').write_text('not a source');(out/'secret.txt').write_text('not a source')
    a,b=tmp_path/'a.zip',tmp_path/'b.zip';pack(out,a);pack(out,b)
    assert a.read_bytes()==b.read_bytes()
    with zipfile.ZipFile(a) as z:
        assert 'one/body.tex' in z.namelist() and 'main.tex' in z.namelist()
        assert 'secret.txt' not in z.namelist() and 'main.log' not in z.namelist()
    with pytest.raises(ValueError):pack(out,a)


@pytest.mark.parametrize('cls,heading',[('article','section'),('report','chapter'),('book','chapter')])
def test_moving_arguments_and_actual_pdf_strings(runtime,cls,heading):
    pre=r'\usepackage[unicode=true,pdfencoding=unicode]{hyperref}\BnTeXNativeDeclareText{intro}{ভূমিকা ও গবেষণা}\BnTeXNativeDeclareText{author}{লেখক}\hypersetup{pdftitle={\BnTeXNativeText{intro}},pdfauthor={\BnTeXNativeText{author}}}'
    row=compile_document(runtime,'\\tableofcontents\\'+heading+r'{\BnTeXNativeRegularText{intro}}\label{s}\bnNative{বাংলা ভাষা} Section~\ref{s}.',preamble=pre,cls=cls,passes=3)
    assert_ok(row);assert not row['warnings']
    pdf=PdfReader(runtime/'main.pdf')
    assert pdf.metadata.title=='ভূমিকা ও গবেষণা' and pdf.metadata.author=='লেখক'
    assert pdf.outline[0].title=='ভূমিকা ও গবেষণা'
    assert row['extracted_text'].count('ভূমিকা ও গবেষণা')>=2


@pytest.mark.parametrize('text',['ড়','ড়','কো','কো','ক্\u200dষ','ক্\u200cষ'])
def test_metadata_preserves_original_encoding(runtime,text):
    pre=r'\usepackage[unicode=true,pdfencoding=unicode]{hyperref}\BnTeXNativeDeclareText{k}{'+text+r'}\hypersetup{pdftitle={\BnTeXNativeText{k}}}'
    row=compile_document(runtime,r'\section{\BnTeXNativeRegularText{k}}',preamble=pre,passes=2)
    assert_ok(row);pdf=PdfReader(runtime/'main.pdf')
    assert pdf.metadata.title==text and pdf.outline[0].title==text


def test_hyperref_loaded_before_integration(runtime):
    source=r'\documentclass{article}\usepackage[unicode=true,pdfencoding=unicode]{hyperref}\usepackage{bntex-native-integration}\BnTeXNativeLoadProfile{bntex-native-profile.tex}\BnTeXNativeDeclareText{k}{বাংলা}\hypersetup{pdftitle={\BnTeXNativeText{k}}}\begin{document}\BnTeXNativeText{k}\end{document}'
    (runtime/'main.tex').write_text(source)
    row=compile_once(runtime,'main.tex');assert_ok(row)
    assert PdfReader(runtime/'main.pdf').metadata.title=='বাংলা'


@pytest.mark.parametrize('body,preamble',[
    (r'\bnNative{বাংলা}\footnote{\bnNative{এটি পাদটীকা।}}',''),
    (r'\begin{tabular}{ll}\bnNative{নাম}&\bnNative{মান}\\\bnNative{প্রথম}&\bnNative{১২৩}\end{tabular}',r'\usepackage{booktabs}'),
    (r'\listoffigures\begin{figure}[h]Example\caption{\BnTeXNativeText{k}}\end{figure}',r'\BnTeXNativeDeclareText{k}{বাংলা চিত্র}'),
    (r'\[a_{\text{\bnNative{প্রথম}}}+\text{\bnNative{বাংলা}}\]',r'\usepackage{amsmath}'),
    (r'\begin{tikzpicture}\node[draw]{\bnNative{বাংলা প্রযুক্তি}};\end{tikzpicture}',r'\usepackage{tikz}'),
])
def test_individual_contexts(runtime,body,preamble):
    row=compile_document(runtime,body,preamble=preamble,passes=2);assert_ok(row)
    assert not row['warnings']


def test_beamer_regular_profile(runtime):
    row=compile_document(runtime,r'\begin{frame}{\BnTeXNativeRegularText{k}}\bnNative{এটি বাংলা বাক্য।}\end{frame}',cls='beamer',preamble=r'\BnTeXNativeDeclareText{k}{বাংলা শিরোনাম}',passes=2)
    assert_ok(row);assert row['pages']==1
    assert 'এটি বাংলা বাক্য।' in row['extracted_text']


def test_bibtex_generated_text(runtime):
    pre=r'\BnTeXNativeDeclareText{k}{বাংলা নির্দেশিকা}'
    source=r'\documentclass{article}\usepackage{bntex-native-integration}\BnTeXNativeLoadProfile{bntex-native-profile.tex}'+pre+r'\begin{document}\cite{demo}\bibliographystyle{plain}\bibliography{references}\end{document}'
    (runtime/'main.tex').write_text(source)
    (runtime/'references.bib').write_text(r'@misc{demo,author={BnTeX contributors},title={{\BnTeXNativeRegularText{k}}},year={2026}}')
    assert_ok(compile_once(runtime,'main.tex',tag='first'))
    bibtex=shutil.which('bibtex') or shutil.which('bibtex.original')
    if not bibtex: pytest.fail('BibTeX is required for the bibliography integration test')
    b=subprocess.run([bibtex,'main'],cwd=runtime,env=dict(os.environ,PATH='/nonexistent'),capture_output=True,timeout=30)
    assert b.returncode==0,b.stdout
    assert_ok(compile_once(runtime,'main.tex',tag='second'))
    row=compile_once(runtime,'main.tex',tag='third');assert_ok(row)
    assert 'বাংলা নির্দেশিকা' in row['extracted_text']


@pytest.mark.parametrize('code',[
 r'\BnTeXNativeDeclareText{bad key}{বাংলা}',
 r'\BnTeXNativeDeclareText{a}{বাংলা}\BnTeXNativeDeclareText{a}{বাংলা}',
 r'\BnTeXNativeText{unknown}',
 r'\BnTeXNativeDeclareText{a}{}',
 r'\def\danger{\errmessage{EXPANDED}}\BnTeXNativeDeclareText{a}{\danger}',
 r'\textbf{\bnNative{বাংলা}}',r'\textit{\bnNative{বাংলা}}',
 r'\BnTeXNativeMemoLimit{0}',r'\BnTeXNativeMemoLimit{257}',r'\BnTeXNativeMemoLimit{\relax}',
])
def test_explicit_rejections(runtime,code):
    row=compile_document(runtime,code,preamble=r'\usepackage{bntex-native-memo}')
    assert row['status']=='compile-error'
    # Literal user macros never execute as part of declaration/decoding.
    assert '! EXPANDED' not in (runtime/'test-1-stdout.txt').read_text()


def test_memo_matches_all_seven_fields_and_encoding(runtime,hb_reference):
    texts=['কর্ম','কো','কো','ড়','ড়','ক্\u200dষ','ক্\u200cষ','নতুনশব্দসমূহ']
    body=''.join('\\bnNative{'+s+r'}\BnTeXNativeDump\par' for s in texts+texts)+r'\BnTeXNativeMemoStats'
    row=compile_document(runtime,body,preamble=r'\usepackage{bntex-native-memo}')
    assert_ok(row)
    runs=glyph_runs((runtime/'test-1-stdout.txt').read_text())
    expected=[[[getattr(g,k) for k in FIELDS] for g in hb_reference.shape(s)] for s in texts]
    assert runs==expected+expected
    assert row['memo']['hits']==len(texts) and row['memo']['misses']==len(texts)


def test_memo_style_geometry_and_color_remain_dynamic(runtime):
    body=r'\setbox0=\hbox{\bnNative{প্রযুক্তি}}\typeout{WIDTH-A|\the\wd0}\setbox0=\hbox{\Large\bnNative{প্রযুক্তি}}\typeout{WIDTH-B|\the\wd0}\textcolor{red}{\bnNative{প্রযুক্তি}}\textcolor{blue}{\bnNative{প্রযুক্তি}}\BnTeXNativeMemoStats'
    row=compile_document(runtime,body,preamble=r'\usepackage{xcolor,bntex-native-memo}');assert_ok(row)
    log=(runtime/'test-1-stdout.txt').read_text();a=float(re.search(r'WIDTH-A\|([0-9.]+)pt',log)[1]);b=float(re.search(r'WIDTH-B\|([0-9.]+)pt',log)[1])
    assert b>a and row['memo']['hits']==3
    content=PdfReader(runtime/'main.pdf').pages[0].get_contents().get_data()
    assert b'1 0 0 rg' in content and b'0 0 1 rg' in content
    assert row['extracted_text'].count('প্রযুক্তি')==2


def test_memo_eviction_clear_and_disabled_gate(runtime):
    body=r'\BnTeXNativeMemoLimit{2}\bnNative{বাংলা ভাষা শিক্ষা বাংলা}\BnTeXNativeMemoStats\BnTeXNativeMemoOff\bnNative{নতুনশব্দ}\BnTeXNativeMemoOn\bnNative{নতুনশব্দ}\BnTeXNativeMemoStats'
    row=compile_document(runtime,body,preamble=r'\usepackage{bntex-native-memo}');assert_ok(row)
    assert row['memo']['entries']==1 and row['memo']['evictions']==1
    assert row['memo']['misses']==5 and 'নতুনশব্দ' in row['extracted_text']


def test_trace_bypasses_memo(runtime):
    row=compile_document(runtime,r'\BnTeXNativeTraceOn\bnNative{কর্ম কর্ম}\BnTeXNativeMemoStats',preamble=r'\usepackage{bntex-native-memo}')
    assert_ok(row);assert row['memo']['entries']==0 and row['memo']['hits']==0


def test_latin_font_not_changed(runtime):
    body=r'\setbox0=\hbox{Latin text}\typeout{BEFORE|\the\wd0}\bnNative{বাংলা}\setbox0=\hbox{Latin text}\typeout{AFTER|\the\wd0}'
    row=compile_document(runtime,body);assert_ok(row)
    text=(runtime/'test-1-stdout.txt').read_text()
    assert re.search(r'BEFORE\|([^\n]+)',text)[1]==re.search(r'AFTER\|([^\n]+)',text)[1]


def test_multifile_example_new_edit(native_install,tmp_path):
    target=tmp_path/'project';stage(ROOT/'examples/native-project/project.json',native_install,target)
    for i in range(3):row=compile_once(target,'main.tex',tag=f'pass-{i+1}',timeout=60);assert_ok(row)
    assert row['pages']==3 and not row['warnings']
    assert PdfReader(target/'main.pdf').metadata.title=='বাংলায় গবেষণা-নথির উদাহরণ'
    path=target/'sections/results.tex';path.write_text(path.read_text()+'\n'+r'\bnNative{পাঠপরিকল্পনাসমূহ}\par'+'\n')
    row=compile_once(target,'main.tex',tag='new-edit',timeout=60);assert_ok(row)
    assert 'পাঠপরিকল্পনাসমূহ' in row['extracted_text']
    assert verify(target)['modified_sources']==['sections/results.tex']


def test_timeout_is_reported_and_child_reaped(runtime):
    (runtime/'main.tex').write_text(r'\documentclass{article}\begin{document}\loop\iftrue\repeat\end{document}')
    row=compile_once(runtime,'main.tex',timeout=.3)
    assert row['status']=='timeout' and 'pages' not in row


def test_module_resources_match():
    for name in ['bntex-native-integration.sty','bntex-native-memo.sty','bntex-native.sty']:
        assert (ROOT/'tex/latex/bntex'/name).read_bytes()==(ROOT/'src/bntex/data'/name).read_bytes()


def test_latexmk_configuration_is_trusted_plain_source():
    path=ROOT/'examples/native-project/latexmkrc'
    code=path.read_text()
    assert 'pdflatex %O -no-shell-escape -halt-on-error %S' in code
    process=subprocess.run([need('perl'),'-c',str(path)],capture_output=True,timeout=10)
    assert process.returncode==0,process.stderr


@pytest.mark.parametrize('name',['bntex-cache.tex','backup-bntex-cache.tex','bntex-cache-copy.tex'])
def test_copied_vocabulary_filename_remains_forbidden(runtime,name):
    (runtime/name).write_text('% Controlled non-executing cache-name audit probe.\n')
    row=compile_document(runtime,r'\input{'+name+r'}\bnNative{বাংলা}')
    assert row['returncode']==0 and row['status']=='validation-error'
    assert any(Path(x).name==name for x in row['recorder_forbidden_inputs'])


def test_cached_compatibility_module_is_not_word_vocabulary(runtime):
    # Loading this implementation supplies commands, not prepared words.
    (runtime/'bntex-cached.sty').write_bytes((ROOT/'tex/latex/bntex/bntex-cached.sty').read_bytes())
    row=compile_document(runtime,r'\bnNative{বাংলা}',preamble=r'\usepackage{bntex-cached}')
    assert_ok(row)
