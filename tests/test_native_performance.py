"""Dispatch optimization contracts; all typography comes from the native runtime.

The original fixture never regenerates expected glyphs. An index-disabled path
also checks exact stage traces and preserves legacy ABI-1 execution semantics.
"""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest
from bntex.tex_export import entry_glyphs, emit_tables, export, FONT_SHA
from test_native_tex import tex_profile, native_install, hb_reference, run_tex, shape_runs, rows

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bntex_perf_tool', ROOT/'tools/native_performance.py')
perf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(perf)


@pytest.mark.parametrize('sub,expected', [
    ({'kind':'single','entries':[(9,3),(2,4)]}, (2,9)),
    ({'kind':'multiple','entries':[(9,[1,3]),(2,[4])]}, (2,9)),
    ({'kind':'ligature','entries':[([9,3],4),([2,5],3),([9,6],1)]}, (2,9)),
    ({'kind':'chain','inputs':[[9,9,2],[3]],'actions':[]}, (2,9)),
    ({'kind':'pair-glyph','entries':[(9,3,{},{}),(2,5,{},{})]}, (2,9)),
    ({'kind':'pair-class','coverage':[9,2],'class1':[],'class2':[],'matrix':[[[{},{}]]]}, (2,9)),
    ({'kind':'mark-base','marks':[(9,0,{}),(2,0,{})],'bases':[(8,[{}])]}, (2,9)),
    ({'kind':'mark-mark','marks':[(9,0,{}),(2,0,{})],'bases':[(8,[{}])]}, (2,9)),
])
def test_conservative_entry_coverage(sub, expected):
    before=copy.deepcopy(sub)
    assert entry_glyphs(sub)==expected
    assert sub==before


def test_unknown_entry_kind_rejected():
    with pytest.raises(ValueError,match='dispatch'):
        entry_glyphs({'kind':'unknown'})


def definitions(raw):
    return dict(re.findall(r'\\cs_gset:cpn \{__bnp_([A-Za-z0-9_]+)\}\{([-A-Za-z0-9_,.]*)\}',raw.decode('ascii')))


def test_indexes_preserve_exact_order_and_candidates(tex_profile):
    p=json.loads(tex_profile.read_text())
    raw=emit_tables(p); data=definitions(raw)
    assert data['dispatch_abi']=='1'
    tid=rid=0
    zero_action_count=0
    for table,letter in [('gsub','s'),('gpos','p')]:
        for lookup in p[table]:
            lid=lookup['index']; candidate={}; direct=letter=='s' and lookup['flags']==0 and all(s['kind']=='ligature' for s in lookup['subtables'])
            if letter=='s':
                assert (f's_{lid}_pair_mode' in data)==direct
            for st in lookup['subtables']:
                tid+=1
                for g in entry_glyphs(st): candidate.setdefault(g,[]).append(tid)
                if st['kind']=='chain' and not st['actions']:
                    zero_action_count+=1
                    assert data[f't_{tid}_actions']=='0'
                if st['kind']=='ligature':
                    by_first={};by_pair={}; ordered=[]
                    for pattern,out in st['entries']:
                        rid+=1;ordered.append(rid)
                        by_first.setdefault(pattern[0],[]).append(rid)
                        by_pair.setdefault(tuple(pattern[:2]),[]).append(rid)
                    assert data[f't_{tid}_rules']==','.join(map(str,ordered))
                    for g,ids in by_first.items():assert data[f't_{tid}_rules_at_{g}']==','.join(map(str,ids))
                    if direct:
                        for (a,b),ids in by_pair.items():
                            assert data[f't_{tid}_rules_pair_{a}_{b}']==','.join(map(str,ids))
                            assert data[f's_{lid}_pair_{a}_{b}']=='1'
                    else:
                        assert not any(k.startswith(f't_{tid}_rules_pair_') for k in data)
            for g in range(p['glyph_count']):
                key=f'{letter}_{lid}_at_{g}'
                assert data.get(key)==(','.join(map(str,candidate[g])) if g in candidate else None)
    assert zero_action_count>0  # Blocking rules cannot vanish from the dispatcher.


@pytest.mark.parametrize('text',['ক্ষ','কর্ম','স্বাস্থ্য','র্টৌঁ','র্শ্ম্ফ্ট্টি','ক্\u200dষ','ক্\u200cষ','অ্যা'])
def test_indexed_and_generic_stage_traces_are_identical(native_install,text):
    command=r'\BnTeXNativeTraceOn\BnTeXNativeShape{'+text+r'}\BnTeXNativeDump'
    indexed,_=run_tex(native_install,command)
    plain,_=run_tex(native_install,command,preamble=r'\ExplSyntaxOn\cs_undefine:N\__bnp_dispatch_abi\ExplSyntaxOff')
    def trace(s):return [line for line in s.splitlines() if line.startswith(('BNTEX-STAGE|','BNTEX-NODE|','BNTEX-RUN|','BNTEX-GLYPH|'))]
    assert trace(indexed)==trace(plain)


def test_direct_pair_guard_respects_flags_manual_mode_and_legacy(native_install):
    pre=r'''\ExplSyntaxOn
\cs_new_protected:Npn\PerfPair#1#2{\__bn_direct_pair:nnTF{#1}{#2}{\iow_term:n{PAIR-YES}}{\iow_term:n{PAIR-NO}}}
\ExplSyntaxOff'''
    # Lookup 18 is unfiltered cjct; lookup 25 ignores marks. Neither must get
    # adjacency shortcuts when auto join-control handling is requested.
    body=r'''\PerfPair{18}{1}\PerfPair{18}{0}\PerfPair{25}{1}
\ExplSyntaxOn\cs_undefine:N\__bnp_dispatch_abi\ExplSyntaxOff
\PerfPair{18}{1}'''
    output,_=run_tex(native_install,body,preamble=pre)
    assert [s for s in output.splitlines() if s in {'PAIR-YES','PAIR-NO'}]==['PAIR-YES','PAIR-NO','PAIR-NO','PAIR-NO']


@pytest.mark.parametrize('size',['0.00002','7.3','10','12','17','1000'])
def test_scaled_dimensions_exact_to_rational_reference(native_install,size):
    # At 1000pt a direct 32-bit intermediate would overflow; e-TeX's combined
    # multiply/divide remains valid. Final values stay inside TeX's dimension range.
    values=[-16001,-1001,-1000,-999,-501,-500,-1,0,1,499,500,501,999,1000,16001]
    body=r'\ExplSyntaxOn\dim_set:Nn\l__bn_em_dim{'+size+r'pt}\iow_term:x{EM|\dim_to_decimal_in_sp:n{\l__bn_em_dim}}'+'\n'
    for n in values:
        body+=r'\iow_term:x{DIM|'+str(n)+r'|\dim_to_decimal_in_sp:n{\__bn_scaled:n{'+str(n)+r'}}}'+'\n'
    body+=r'\ExplSyntaxOff'
    output,_=run_tex(native_install,body)
    em=int(re.search(r'^EM\|(-?\d+)',output,re.M)[1])
    def nearest(v):return (1 if v>=0 else -1)*((abs(v)+500)//1000)
    actual={int(k):int(v) for k,v in re.findall(r'^DIM\|(-?\d+)\|(-?\d+)',output,re.M)}
    assert actual=={n:nearest(em*n) for n in values}


def test_memo_and_new_word_keep_original_text_and_current_style(native_install,hb_reference):
    texts=['কো','কো','ক্\u200dষ','ক্\u200cষ','পুনর্গঠনযোগ্যতার','শিক্ষকসম্মেলনের']
    body=[]
    for i,word in enumerate(texts*2):
        body.append(('\\small' if i<len(texts) else '\\Large')+r'\bnNative{'+word+r'}\BnTeXNativeDump\par')
    body.append(r'\BnTeXNativeMemoStats\BnTeXNativeMemoOff\bnNative{নবায়নযোগ্যতাসমূহ}\BnTeXNativeDump')
    output,_=run_tex(native_install,'\n'.join(body),preamble=r'\usepackage{bntex-native-memo}')
    assert 'hits=6|misses=6|' in output
    actual=[]
    for line in output.splitlines():
        if line.startswith('BNTEX-RUN|'):actual.append([])
        if line.startswith('BNTEX-GLYPH|'):actual[-1].append(list(map(int,line.split('|')[1:])))
    assert actual==[rows(hb_reference.shape(w)) for w in texts*2+['নবায়নযোগ্যতাসমূহ']]
    extracted=subprocess.check_output(['pdftotext',str(native_install/'native-case.pdf'),'-']).decode()
    assert all(w in extracted for w in texts+['নবায়নযোগ্যতাসমূহ'])


def test_live_declared_heading_interface_unchanged(native_install):
    pre=r'''\usepackage{bntex-native-integration}
\usepackage[unicode=true,pdfencoding=unicode]{hyperref}
\BnTeXNativeDeclareText{title}{গবেষণা ও কর্মপরিকল্পনা}
\hypersetup{pdftitle={\BnTeXNativeText{title}}}'''
    body=r'\tableofcontents\section{\BnTeXNativeRegularText{title}}\bnNative{শিক্ষার্থীদের আলোচনা}'
    for _ in range(3):run_tex(native_install,body,preamble=pre)
    from pypdf import PdfReader
    reader=PdfReader(native_install/'native-case.pdf')
    assert reader.metadata.title=='গবেষণা ও কর্মপরিকল্পনা'
    assert reader.outline[0].title=='গবেষণা ও কর্মপরিকল্পনা'


@pytest.mark.parametrize('mode',['repeated','distinct'])
@pytest.mark.parametrize('memo',[False,True])
def test_benchmark_source_is_deterministic(mode,memo):
    a,spec,words=perf.source(10,96,mode,memo)
    assert perf.source(10,96,mode,memo)==(a,spec,words)
    assert spec['token_occurrences']==960
    assert spec['distinct_tokens']==(16 if mode=='repeated' else 960)
    assert a.count(r'\clearpage')==10
    assert spec['source_sha256']==hashlib.sha256(a.encode()).hexdigest()
    assert (r'\usepackage{bntex-native-memo}' in a)==memo


@pytest.mark.parametrize('fault',['existing','inside','pages','memo','mode','passes','timeout'])
def test_benchmark_validation_before_creation(native_install,tmp_path,fault):
    out=tmp_path/'out';kwargs={'pages':[1],'tokens':16,'modes':['repeated'],'memo_modes':[False],'passes':1,'timeout':10}
    if fault=='existing':out.mkdir();(out/'keep').write_text('keep')
    if fault=='inside':out=native_install/'performance-output'
    if fault=='pages':kwargs['pages']=[1,1]
    if fault=='memo':kwargs['memo_modes']=[False,False]
    if fault=='mode':kwargs['modes']=['unsupported']
    if fault=='passes':kwargs['passes']=0
    if fault=='timeout':kwargs['timeout']=float('nan')
    with pytest.raises(ValueError):perf.benchmark({'candidate':native_install},out,**kwargs)
    assert not out.exists() or fault=='existing'


def test_benchmark_paired_source_and_complete_evidence(native_install,tmp_path):
    result=perf.benchmark({'first':native_install,'second':native_install},tmp_path/'paired',pages=[1],tokens=16,
                          modes=['distinct'],memo_modes=[False],passes=1,timeout=30)
    a,b=result['rows']
    assert a['workload']['source_sha256']==b['workload']['source_sha256']
    for row in result['rows']:
        assert row['status']=='compiled' and row['pdf_pages']==1
        assert row['all_tokens_extracted'] and row['bengali_font_entries']==3
        assert row['runs'][0]['immutable_assets_unchanged']
        assert row['runs'][0]['forbidden_runtime_inputs']==[]


def test_benchmark_timeout_not_counted_as_completed_pdf(native_install,tmp_path):
    assets,_=perf.installation(native_install);root=tmp_path/'timeout';root.mkdir()
    for name,raw in assets.items():(root/name).write_bytes(raw)
    (root/'main.tex').write_text(r'\documentclass{article}\begin{document}\def\forever{\forever}\forever\end{document}')
    # A stale-looking PDF is deliberately present. An unsuccessful TeX process
    # must not report it as a completed new run.
    (root/'main.pdf').write_bytes(b'%PDF-not-a-success')
    row=perf.compile_run(root,assets,[],1,1)
    assert row['status']=='timeout' and row['pdf_pages'] is None and row['pdf_bytes'] is None
    assert row['runs'][0]['immutable_assets_unchanged']


def test_legacy_table_bytes_are_unchanged_after_removing_indexes(tex_profile):
    raw=emit_tables(json.loads(tex_profile.read_text()))
    indexed=re.compile(rb"\\cs_gset:cpn \{__bnp_(?:dispatch_abi|activity_abi|activate_\d+|[sp]_\d+_at_\d+|s_\d+_pair_(?:mode|\d+_\d+)|t_\d+_rules_(?:at_\d+|pair_\d+_\d+))\}")
    legacy=b''.join(line for line in raw.splitlines(keepends=True) if not indexed.match(line))
    # Verified parent installation table identity, not a freshly regenerated oracle.
    assert hashlib.sha256(legacy).hexdigest()=='7fd73a9d0d21b99c4d2580f209ec0c1cc8bf15d72c8eb444522b38898577cd4a'
