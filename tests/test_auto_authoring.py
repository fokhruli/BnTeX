"""Exercise real pdfTeX: automatic input, true bold, and explicit slanted effects.

Each compilation runs with shell escape disabled and no executable search path.
Python installs font assets once and compares outputs AFTER pdfTeX exits.
"""
from __future__ import annotations
from dataclasses import asdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from bntex.authoring_export import export_authoring, style_delta, BOLD_PROFILE_SHA, DECLARATION
from bntex.native_profile import compile_profile, serialize, PINNED_BOLD_SHA256
from bntex.native_model import NativeShaper
from bntex.tex_export import emit_tables, FONT_SHA, PROFILE_SHA
from test_native_tex import CONJUNCTS, MATRAS

ROOT = Path(__file__).resolve().parents[1]
REG = Path(os.getenv('BNTEX_REGULAR_FONT', '/usr/share/fonts/truetype/noto/NotoSerifBengali-Regular.ttf'))
BOLD = Path(os.getenv('BNTEX_BOLD_FONT', '/usr/share/fonts/truetype/noto/NotoSerifBengali-Bold.ttf'))
pytestmark = pytest.mark.integration

@pytest.fixture(scope='session')
def family_install(tmp_path_factory):
    for tool in ('pdflatex', 'pltotf', 'pdftotext'):
        if not shutil.which(tool):
            if os.getenv('BNTEX_REQUIRE_INTEGRATION') == '1': pytest.fail('Missing '+tool)
            pytest.skip('Missing '+tool)
    if not REG.exists() or not BOLD.exists():
        if os.getenv('BNTEX_REQUIRE_INTEGRATION') == '1': pytest.fail('Pinned regular and bold fonts required')
        pytest.skip('Pinned fonts required')
    out=tmp_path_factory.mktemp('native-family')/'install'
    result=export_authoring(REG, BOLD, out)
    assert result['vocabulary'] is None
    return out

@pytest.fixture(scope='session')
def bold_reference():
    from bntex.harfbuzz import HarfBuzz
    with HarfBuzz(BOLD) as hb:
        if hb.version != '10.2.0':
            if os.getenv('BNTEX_REQUIRE_ORACLE') == '1': pytest.fail('Pinned HarfBuzz required')
            pytest.skip('Pinned HarfBuzz required')
        yield hb


def compile_tex(root, body, *, preamble='', options='', passes=1, ok=True, before='', klass='article'):
    text=(r'\errorcontextlines=30'+'\n'+rf'\documentclass{{{klass}}}'+'\n'+before+'\n'
          +rf'\usepackage[{options}]{{bntex-auto}}'+'\n'
          +r'\BnTeXNativeLoadProfile{bntex-native-profile.tex}'+'\n'+preamble+'\n'
          +r'\begin{document}\ifnum\pdfshellescape=0\else\errmessage{shell enabled}\fi'+'\n'
          +body+'\n'+r'\end{document}'+'\n')
    (root/'case.tex').write_bytes(text.encode('utf8'))
    return run_file(root, passes=passes, ok=ok)


def run_file(root, *, passes=1, ok=True):
    env=dict(os.environ, PATH='/no-runtime-executables', TEXINPUTS='.:', max_print_line='10000',
             openin_any='p', openout_any='p', MKTEXTFM='0', MKTEXPK='0', SOURCE_DATE_EPOCH='1', FORCE_SOURCE_DATE='1')
    assets=json.loads((root/'native-installation.json').read_text())['files']
    for _ in range(passes):
        p=subprocess.run([shutil.which('pdflatex'), '-no-shell-escape', '-halt-on-error',
                          '-interaction=nonstopmode','-recorder','case.tex'], cwd=root, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    log=p.stdout.decode('utf8', 'replace')
    if ok:
        assert p.returncode==0, log[-12000:]
        assert 'Missing character:' not in log
        inputs=[x[6:] for x in (root/'case.fls').read_text().splitlines() if x.startswith('INPUT ')]
        assert not any(Path(x).suffix in {'.py','.json','.gz'} or 'cache' in Path(x).name for x in inputs)
        assert all(hashlib.sha256((root/n).read_bytes()).hexdigest()==h for n,h in assets.items())
    else: assert p.returncode!=0, log
    return log


def extracted(root):
    return subprocess.check_output([shutil.which('pdftotext'), str(root/'case.pdf'), '-']).decode('utf8')

DUMP=r'''\ExplSyntaxOn
\cs_set_eq:NN\__test_render:\__bn_render:
\cs_set_protected:Npn\__bn_render:{\BnTeXNativeDump\__test_render:}
\ExplSyntaxOff'''


def runs(log):
    result=[]
    for line in log.splitlines():
        if line.startswith('BNTEX-RUN|'): result.append([bytes.fromhex(line.split('|')[1]).decode('utf8'), []])
        if line.startswith('BNTEX-GLYPH|'): result[-1][1].append(list(map(int,line.split('|')[1:])))
    return result


def frozen_texts():
    raw=(ROOT/'corpus/oracles/user-forms-noto-hb10.2.0.json.gz').read_bytes()
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='513f018036962986ac9a3663ba2496c1e1a5cbea'
    return [(''.join(chr(int(c,16)) for c in cid[2:].split('-')), rows)
            for cid,rows in json.loads(gzip.decompress(raw))['runs']]

@pytest.mark.parametrize('block',range(3))
def test_auto_original_inventory_and_bold_positions(family_install,bold_reference,block):
    batch=frozen_texts()[block*87:(block+1)*87]
    # Every original inventory scalar sequence is covered by explicit transport.
    # Automatic mode only starts on script runs; skip pure ASCII/dotted-circle controls.
    batch=[(text, rows) for text,rows in batch if all(0x980<=ord(c)<=0x9ff or ord(c) in (0x964,0x965,0x200c,0x200d) for c in text)]
    body='\n'.join(text+r'\quad '+r'\textbf{'+text+r'}\par' for text,_ in batch)
    observed=runs(compile_tex(family_install,body,preamble=DUMP))
    assert len(observed)==2*len(batch)
    for i,(text, expected) in enumerate(batch):
        assert observed[2*i]==[text,expected]
        assert observed[2*i+1]==[text,[list(asdict(g).values()) for g in bold_reference.shape(text)]]

@pytest.mark.parametrize('sign',MATRAS)
def test_bold_conjunct_matrix(family_install,bold_reference,sign):
    texts=[c+sign for c in CONJUNCTS]
    log=compile_tex(family_install,'\n'.join(r'\textbf{'+s+r'} ' for s in texts),preamble=DUMP)
    assert runs(log)==[[s,[list(asdict(g).values()) for g in bold_reference.shape(s)]] for s in texts]

@pytest.mark.parametrize('body,expected',[
    ('LatinবাংলাEnglish',['বাংলা']),
    ('কর্ম, স্বাস্থ্য; বাংলা.',['কর্ম','স্বাস্থ্য','বাংলা']),
    ('বাংলা—English café',['বাংলা']),
    (r'বাংলা\textbf{কর্ম}লেখা',['বাংলা','কর্ম','লেখা']),
    (r'{বাংলা}{কর্ম}',['বাংলা','কর্ম']),
    ('বাংলা\n\nকর্ম',['বাংলা','কর্ম']),
    (r'বাংলা $x^2$ কর্ম',['বাংলা','কর্ম']),
    ('ক্\u200dষ ক্\u200cষ র\u09cdয কো কো ড় ড\u09bc',['ক্\u200dষ','ক্\u200cষ','র\u09cdয','কো','কো','ড়','ড\u09bc']),
    (r'বাংলা\foo কর্ম',['বাংলা','কর্ম']),
])
def test_boundaries_and_original_bytes(family_install,body,expected):
    log=compile_tex(family_install,body,preamble=DUMP+r'\newcommand\foo{LATIN}')
    assert [x[0] for x in runs(log)]==expected

@pytest.mark.parametrize('effect',[r'\textbf',r'\textit',r'\emph',r'\underline',r'\uline',r'\sout'])
def test_effects_compile_and_preserve_text(family_install,effect):
    pre=r'\usepackage[normalem]{ulem}'
    compile_tex(family_install,effect+'{বাংলা কর্ম গবেষণা}',preamble=pre,options='synthetic-italic')
    text=extracted(family_install)
    assert all(s in text for s in ['বাংলা','কর্ম','গবেষণা'])

@pytest.mark.parametrize('before',[False,True])
def test_heading_toc_pdfstrings_both_load_orders(family_install,before):
    from pypdf import PdfReader
    hyper=r'\usepackage[unicode,hidelinks]{hyperref}'
    title='কো কো ড় ড\u09bc ক্\u200dষ'
    pre=('' if before else hyper)+r'\hypersetup{pdftitle={'+title+'}}'
    compile_tex(family_install,r'\tableofcontents\section{বাংলা শিরোনাম}\label{sec:বাংলা} বাংলা। Section~\ref{sec:বাংলা}.',
                preamble=pre,before=hyper if before else '',passes=3)
    pdf=PdfReader(family_install/'case.pdf')
    assert pdf.metadata.title==title
    assert pdf.outline[0].title=='বাংলা শিরোনাম'
    assert 'বাংলা শিরোনাম' in extracted(family_install)


def test_memo_face_keys_size_color_and_slant(family_install,bold_reference):
    pre=r'\usepackage{bntex-native-memo}\usepackage{xcolor}'+DUMP
    body=r'বাংলা \textbf{বাংলা} বাংলা \textbf{বাংলা} \textit{বাংলা} {\Large\textcolor{blue}{বাংলা}}\BnTeXNativeMemoStats'
    log=compile_tex(family_install,body,preamble=pre,options='synthetic-italic')
    actual=runs(log)
    assert len(actual)==6
    assert actual[0]==actual[2]==actual[4]==actual[5]
    assert actual[1]==actual[3]==['বাংলা',[list(asdict(g).values()) for g in bold_reference.shape('বাংলা')]]
    assert actual[0][1]!=actual[1][1]
    assert 'BNTEX-MEMO|hits=4|misses=2|entries=2|' in log


def test_ordinary_verbatim_ascii_url_and_bengali_filename(family_install):
    (family_install/'অধ্যায়.tex').write_text('অন্তর্ভুক্ত লেখা।\n')
    pre=r'\usepackage{url}'
    body=r'''\verb|\textbf{not executed}|
\begin{verbatim}
A_B % literal
\end{verbatim}
\url{https://example.org/a_b?q=x}
\input{অধ্যায়.tex}'''
    compile_tex(family_install,body,preamble=pre)
    assert 'অন্তর্ভুক্ত লেখা।' in extracted(family_install)


def test_grouped_disable_preserves_explicit_interface(family_install):
    compile_tex(family_install,r'বাংলা {\BnTeXAutoOff\bnNative{কর্ম}} ভাষা',preamble=DUMP)
    log=compile_tex(family_install,r'{\BnTeXAutoOff বাংলা}',ok=False)
    assert 'automatic' in log

@pytest.mark.parametrize('body,part',[
    (r'$বাংলা$','text'),
    (r'\textit{বাংলা}','true'),
    (r'\textsc{বাংলা}','shape'),
    ('কিা','vowel'),
    ('ক'*1366,'4096'),
])
def test_explicit_rejections(family_install,body,part):
    log=compile_tex(family_install,body,ok=False)
    assert part in log

@pytest.mark.parametrize('tail',[b'\xe0',b'\xe0\xa6',b'\xe0\x80\x80',b'\xe0\xa6\\boom'])
def test_malformed_tail_rejected_without_expanding_macro(family_install,tail):
    compile_tex(family_install,'বাংলা')
    p=family_install/'case.tex';raw=p.read_bytes().replace('বাংলা'.encode(),'বাংলা'.encode()+tail)
    raw=raw.replace(b'\\begin{document}',b'\\def\\boom{\\typeout{MUST-NOT-RUN}}\\begin{document}')
    p.write_bytes(raw)
    log=run_file(family_install,ok=False)
    assert 'MUST-NOT-RUN\n' not in log


def test_bold_profile_and_model_identity():
    r,b=compile_profile(REG),compile_profile(BOLD)
    assert hashlib.sha256(serialize(r)).hexdigest()==PROFILE_SHA
    assert hashlib.sha256(serialize(b)).hexdigest()==BOLD_PROFILE_SHA
    assert r.gsub==b.gsub and r.gpos!=b.gpos and r.advances!=b.advances
    assert NativeShaper(b).identity==BOLD_PROFILE_SHA


def test_style_delta_reconstructs_complete_bold_tables():
    r,b=map(asdict,(compile_profile(REG),compile_profile(BOLD)))
    delta,count=style_delta(r,b)
    a=dict(DECLARATION.findall(emit_tables(r).decode()))
    actual=dict(DECLARATION.findall(emit_tables(b).decode()))
    changed=dict(re.findall(r'\\cs_gset:cpn \{__bnb_([^}]+)\}\{([^}]*)\}',delta.decode()))
    a.update(changed)
    assert a==actual
    assert count==len(changed)>0
    # Structural changes must not fall through to regular data silently.
    b['gsub']=[]
    with pytest.raises(ValueError,match='share'):style_delta(r,b)


def test_changed_bold_asset_is_rejected(family_install,tmp_path):
    root=tmp_path/'altered';shutil.copytree(family_install,root)
    p=root/'bntex-native-bold.def';p.write_text(p.read_text()+'% changed\n')
    log=compile_tex(root,r'\textbf{বাংলা}',ok=False)
    assert 'installation asset changed' in log


def test_authoring_export_rejects_swap_and_overwrite(family_install,tmp_path):
    with pytest.raises(ValueError,match='regular'):export_authoring(BOLD,REG,tmp_path/'wrong')
    assert not (tmp_path/'wrong').exists()
    with pytest.raises(ValueError,match='fresh'):export_authoring(REG,BOLD,family_install)


def test_latin_font_metrics_are_not_changed(family_install):
    body=r'''\newsavebox{\latinA}\newsavebox{\latinB}
\sbox{\latinA}{\textbf{Latin Test}} বাংলা \textbf{বাংলা}
\sbox{\latinB}{\textbf{Latin Test}}
\ifdim\wd\latinA=\wd\latinB\else\errmessage{Latin metrics changed}\fi'''
    compile_tex(family_install,body)


def test_nested_emphasis_and_weight_restore(family_install,bold_reference):
    text='বাংলা'
    body=r'বাংলা \textbf{বাংলা \textmd{বাংলা} বাংলা} \emph{বাংলা \emph{বাংলা} বাংলা} বাংলা'
    observed=runs(compile_tex(family_install,body,preamble=DUMP,options='synthetic-italic'))
    assert len(observed)==8
    normal=observed[0]
    bold=[text,[list(asdict(g).values()) for g in bold_reference.shape(text)]]
    assert observed==[normal,bold,normal,bold,normal,normal,normal,normal]


def test_math_text_superscript_and_subscript(family_install):
    pre=r'\usepackage{amsmath}'+DUMP
    body=r'বাংলা $x_{\text{বাংলা}}+\text{কর্ম}$ \textsuperscript{বাংলা} \textsubscript{কর্ম}'
    log=compile_tex(family_install,body,preamble=pre)
    assert {x[0] for x in runs(log)}=={'বাংলা','কর্ম'}
    # amsmath evaluates several mathchoice styles; measure the PDF, not one call.
    assert all(t in extracted(family_install) for t in ('বাংলা','কর্ম'))


def test_breakable_underline_and_strikeout(family_install):
    phrase='বাংলা কর্ম গবেষণা প্রযুক্তি '*15
    body=r'\begin{minipage}{8cm}\uline{'+phrase+r'}\par\textbf{\sout{বাংলা কর্ম}}\end{minipage}'
    log=compile_tex(family_install,body,preamble=r'\usepackage[normalem]{ulem}')
    assert 'Overfull' not in log
    assert 'বাংলা' in extracted(family_install)


@pytest.mark.parametrize('control',[r'\BnTeXSyntheticItalicOff', r'\BnTeXAutoOff'])
def test_local_options_do_not_leak(family_install,control):
    body='{'+control+' Latin only} '+r'\textit{বাংলা}'
    compile_tex(family_install,body,options='synthetic-italic')


def test_unrelated_macro_is_not_expanded_by_lookahead(family_install):
    # The following command executes after the Bengali run is fully rendered.
    pre=DUMP+r'\newcommand\afterword{\typeout{AFTER-WORD}}'
    log=compile_tex(family_install,r'বাংলা\afterword',preamble=pre)
    assert log.index('BNTEX-RUN|') < log.index('AFTER-WORD')


def test_bold_geometry_and_explicit_paths_match(family_install):
    pre=r'''\ExplSyntaxOn
\cs_new_protected:Npn\bntestmeasure#1#2{
 \hbox_set:Nn\l_tmpa_box{#2}
 \typeout{GEOMETRY|#1|\dim_use:N\box_wd:N\l_tmpa_box}
}
\ExplSyntaxOff'''
    # Direct TeX dimensions, with equivalent rendering entry points.
    body=r'''\newsavebox{\autoA}\newsavebox{\explicitB}
\sbox{\autoA}{\textbf{কর্ম}}
\sbox{\explicitB}{\textbf{\bnNative{কর্ম}}}
\ifdim\wd\autoA=\wd\explicitB\else\errmessage{width differs}\fi
\ifdim\ht\autoA=\ht\explicitB\else\errmessage{height differs}\fi
\ifdim\dp\autoA=\dp\explicitB\else\errmessage{depth differs}\fi
\usebox{\autoA}'''
    compile_tex(family_install,body)


def test_edit_new_text_without_preparing_again(family_install):
    compile_tex(family_install,'বাংলা ভাষা')
    p=family_install/'case.tex';new='অপ্রচলিতশব্দরূপের পুনর্গঠনযোগ্যতা'
    p.write_text(p.read_text().replace('বাংলা ভাষা',new))
    run_file(family_install)
    assert all(x in extracted(family_install) for x in new.split())


def test_unknown_option_rejected(family_install):
    compile_tex(family_install,'বাংলা',options='invented-style',ok=False)


def test_unicode_inventory_automatic_count_is_complete():
    texts=frozen_texts()
    assert len(texts)==261
    assert all(all(0x980<=ord(c)<=0x9ff or ord(c) in (0x964,0x965,0x200c,0x200d)
                   for c in text) for text,_ in texts)


def test_complete_wrapper_free_example(family_install,tmp_path):
    from pypdf import PdfReader
    source=(ROOT/'examples/automatic-authoring/main.tex').read_text()
    assert not re.search(r'\\bn(?:Native)?\b',source)
    root=tmp_path/'example';shutil.copytree(family_install,root)
    (root/'case.tex').write_text(source)
    log=run_file(root,passes=2)
    assert 'Overfull' not in log and 'Underfull' not in log
    pdf=PdfReader(root/'case.pdf')
    assert len(pdf.pages)==2
    assert pdf.metadata.title=='বাংলা লেখার স্বাধীনতা'
    assert 'নিচে দাগ' in extracted(root)


def test_capability_template_uses_automatic_authoring():
    import sys, importlib.util
    sys.path.insert(0,str(ROOT/'tools'))
    try:
        spec=importlib.util.spec_from_file_location('auto_capability',ROOT/'tools/automatic_chroot_gate.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        source=module.document(['নতুনবাংলাশব্দ'])
    finally:
        sys.path.pop(0)
    assert not re.search(r'\\bn(?:Native)?\b',source)
    assert r'\textbf{নতুনবাংলাশব্দ}' in source
    assert r'\textit{নতুনবাংলাশব্দ}' in source
    assert 'synthetic-italic' in source
