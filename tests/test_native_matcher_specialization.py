"""Generated IgnoreMarks pairs versus the executable generic interpreter.

The font rules, Unicode references and execution budget are never rebaselined.
Synthetic internal-node tests are matcher semantics, not Bengali orthography.
"""
from pathlib import Path
import gzip
import hashlib
import json
import random
import re
import sys
import pytest
from bntex.tex_export import emit_tables, emit_matchers, mark_pair_declaration
from test_native_tex import tex_profile, native_install, hb_reference, run_tex, shape_runs, CONJUNCTS, MATRAS
from test_native_first_use import traced_words

GENERIC = r'\ExplSyntaxOn\bool_set_false:N\l__bn_mark_pair_enabled_bool\ExplSyntaxOff'


def eligible(profile):
    rid = 0
    for lookup in profile['gsub']:
        for st in lookup['subtables']:
            if st['kind'] == 'ligature':
                for glyphs, output in st['entries']:
                    rid += 1
                    if lookup['flags'] == 8 and len(glyphs) == 2:
                        yield rid, lookup['index'], glyphs, output


def test_generated_declarations_exactly_cover_one_font_rule_family(tex_profile):
    p = json.loads(tex_profile.read_text())
    lines = emit_matchers(p).decode('ascii').splitlines()
    actual = [s for s in lines if s.startswith(r'\cs_gset_protected:cpn {__bnp_r_')]
    expected = [mark_pair_declaration(r, l, 8, gs) for r, l, gs, _ in eligible(p)]
    assert actual == expected
    assert len(actual) == 54
    assert hashlib.sha256(emit_tables(p)).hexdigest() == 'e0599bf2311d96947cac928f76ebbf4c2596de2250ee934c0d8a34ab74bd5cae'


@pytest.mark.parametrize('flags,pattern', [(0,[1,2]),(16,[1,2]),(256,[1,2]),(8,[1]),(8,[1,2,3])])
def test_unproved_families_emit_no_specialization(flags,pattern):
    assert mark_pair_declaration(1,2,flags,pattern) is None


@pytest.mark.parametrize('rule,lookup,pattern', [(-1,2,[1,2]),(1,-1,[1,2]),(1,2,[-1,2]),(1,2,[1,65536]),(1,2,[True,2]),('x',2,[1,2])])
def test_generated_code_rejects_noninteger_or_out_of_range_indexes(rule,lookup,pattern):
    with pytest.raises(ValueError):mark_pair_declaration(rule,lookup,8,pattern)


def test_frozen_inventory_shaping_matches_generic(native_install):
    root=Path(__file__).resolve().parents[1]
    # Use exactly the original strings from the frozen reference, not normalized keys.
    oracle=json.loads(gzip.decompress((root/'corpus/oracles/user-forms-noto-hb10.2.0.json.gz').read_bytes()))
    # Frozen format carries original words in the compact text field.
    texts=[''.join(chr(int(c,16)) for c in cid[2:].split('-')) for cid,_ in oracle['runs']]
    a,_=shape_runs(native_install,texts,literal=True)
    pre=GENERIC
    body='\n'.join(r'\typeout{CASE|'+str(i)+r'}\BnTeXNativeShape{'+w+r'}\BnTeXNativeDump' for i,w in enumerate(texts))
    log,_=run_tex(native_install,body,preamble=pre)
    flat=[g for run in a for g in run]
    assert [list(map(int,l.split('|')[1:])) for l in log.splitlines() if l.startswith('BNTEX-GLYPH|')]==flat


@pytest.mark.parametrize('words', [
 ['কর্ম','প্রযুক্তি','স্বাস্থ্য','শিক্ষার্থীদের','হৃ','রু'],
 ['কো','কো','ড়','ড়','ক্\u200dষ','ক্\u200cষ'],
 ['র্শ্ম্ফ্ট্টি','র্টৌঁ','ক্ষ্ম','কৃ','অ্যা','ত্রিমাত্রিকীকরণসমূহ'],
])
def test_complete_stage_traces_match_generic(native_install,words):
    assert traced_words(native_install,words)==traced_words(native_install,words,GENERIC)


def test_seeded_conjunct_traces_match_generic(native_install):
    rng=random.Random(60720)
    words=[rng.choice(CONJUNCTS)+rng.choice(MATRAS) for _ in range(96)]
    assert traced_words(native_install,words)==traced_words(native_install,words,GENERIC)


def setup_nodes(nodes):
    lines=[rf'\int_gset:Nn\g__bn_count_int{{{len(nodes)}}}']
    for i,(gid,syl,mask,cp,lig) in enumerate(nodes):
        lines.append(rf'\intarray_gset:Nnn\g__bn_order_intarray{{{i+1}}}{{{i+1}}}')
        for field,val in zip(('gid','syl','mask','cp','lig'),(gid,syl,mask,cp,lig)):
            lines.append(rf'\intarray_gset:Nnn\g__bn_{field}_intarray{{{i+1}}}{{{val}}}')
    return ''.join(lines)


def snapshot(label):
    return (r'\iow_term:x{PAIR|'+label+r'|\bool_if:NTF\g__bn_success_bool{1}{0}'
            r'|\bool_if:NTF\g__bn_ignore_bool{1}{0}|\int_use:N\g__bn_ops_int'
            r'|\seq_use:Nn\g__bn_match_seq{,}|\int_use:N\g__bn_next_int}')


def test_every_generated_rule_on_adversarial_node_buffers(native_install,tex_profile):
    p=json.loads(tex_profile.read_text())
    mark=next(i for i,c in enumerate(p['glyph_classes']) if c==3)
    normal=next(i for i,c in enumerate(p['glyph_classes']) if c==1)
    body=[r'\ExplSyntaxOn'];cases=0
    for rid,lid,(a,b),_ in eligible(p):
        node=lambda g,s=1,m=127,c=2453,l=0:(g,s,m,c,l)
        variants=[([],0,-1,0),([node(a)],0,-1,0),([node(a),node(b)],-1,-1,0),
                  ([node(a),node(b)],2,-1,0),([node(a),node(b)],0,1,0),
                  ([node(a),node(b)],0,2,0),([node(a),node(b,m=0)],0,1,1),
                  ([node(mark),node(a),node(mark),node(b),node(mark)],0,1,0),
                  ([node(a),node(mark)],0,1,0),([node(normal),node(b)],0,-1,0),
                  ([node(a),node(normal)],0,-1,0),([node(a),node(b,s=2)],0,1,0),
                  ([node(a),node(b,c=8204)],0,1,0),([node(a),node(b,c=8205)],0,1,0),
                  ([node(a),node(b,c=8205,l=1)],0,1,0)]
        for nodes,start,syl,mask in variants:
            body.append(setup_nodes(nodes))
            for mode in ('fast','generic'):
                body.append(r'\int_gzero:N\g__bn_ops_int\bool_gset_true:N\g__bn_ignore_bool\int_gset:Nn\g__bn_next_int{77}')
                if mode=='fast':body.append(rf'\use:c{{__bnp_r_{rid}_mark_pair}}{{{start}}}{{{syl}}}{{{mask}}}')
                else:body.append(rf'\__bn_match:nnnnnnnn{{{start}}}{{\__bn_tab:n{{r_{rid}_pat}}}}{{{lid}}}{{1}}{{{syl}}}{{1}}{{{mask}}}{{0}}')
                body.append(snapshot(f'{cases}/{mode}'))
            cases+=1
    body.append(r'\ExplSyntaxOff')
    log,_=run_tex(native_install,'\n'.join(body),timeout=60)
    records=re.findall(r'^PAIR\|(\d+)/(fast|generic)\|(.*)$',log,re.M)
    assert len(records)==2*cases==1620
    for fast,generic in zip(records[::2],records[1::2]):
        assert fast[0]==generic[0] and fast[2]==generic[2],(fast,generic)


@pytest.mark.parametrize('manual,enabled,expected_fast',[(1,True,True),(0,True,False),(1,False,False)])
def test_dispatch_uses_specialization_only_under_guards(native_install,tex_profile,manual,enabled,expected_fast):
    rid,lid,(a,b),_=next(eligible(json.loads(tex_profile.read_text())))
    pre=r'''\ExplSyntaxOn
\int_new:N\g__test_fast_int\int_new:N\g__test_generic_int
\cs_new_eq:NN\__test_fast:nnnnnn\__bn_match_mark_pair:nnnnnn
\cs_set_protected:Npn\__bn_match_mark_pair:nnnnnn#1#2#3#4#5#6{\int_gincr:N\g__test_fast_int\__test_fast:nnnnnn{#1}{#2}{#3}{#4}{#5}{#6}}
\cs_new_eq:NN\__test_generic:nnnnnnnn\__bn_match:nnnnnnnn
\cs_set_protected:Npn\__bn_match:nnnnnnnn#1#2#3#4#5#6#7#8{\int_gincr:N\g__test_generic_int\__test_generic:nnnnnnnn{#1}{#2}{#3}{#4}{#5}{#6}{#7}{#8}}
\ExplSyntaxOff'''
    body=r'\ExplSyntaxOn'+setup_nodes([(a,1,127,2453,0),(b,1,127,2453,0)])
    if not enabled:body+=r'\bool_set_false:N\l__bn_mark_pair_enabled_bool'
    body+=rf'\__bn_match_lig:nnnnnn{{{rid}}}{{{lid}}}{{0}}{{0}}{{{manual}}}{{1}}'
    body+=r'\iow_term:x{COUNTS|\int_use:N\g__test_fast_int|\int_use:N\g__test_generic_int}\ExplSyntaxOff'
    log,_=run_tex(native_install,body,preamble=pre)
    assert f'COUNTS|{int(expected_fast)}|{int(not expected_fast)}' in log


@pytest.mark.parametrize('generic',[False,True])
def test_operation_limit_is_not_weakened(native_install,tex_profile,generic):
    rid,lid,(a,b),_=next(eligible(json.loads(tex_profile.read_text())))
    body=r'\ExplSyntaxOn'+setup_nodes([(a,1,127,2453,0),(b,1,127,2453,0)])
    if generic:body+=r'\bool_set_false:N\l__bn_mark_pair_enabled_bool'
    body+=rf'\int_gset:Nn\g__bn_ops_int{{1999999}}\__bn_match_lig:nnnnnn{{{rid}}}{{{lid}}}{{0}}{{0}}{{1}}{{1}}\ExplSyntaxOff'
    log,_=run_tex(native_install,body,expect_success=False)
    assert 'operation budget exceeded' in re.sub(r'\s+', ' ', log.replace('(bntex-native)', '')), log[-5000:]


def test_actual_text_exercises_generated_path_and_grouped_control(native_install):
    pre=r'''\ExplSyntaxOn
\int_new:N\g__test_fast_int
\cs_new_eq:NN\__test_fast:nnnnnn\__bn_match_mark_pair:nnnnnn
\cs_set_protected:Npn\__bn_match_mark_pair:nnnnnn#1#2#3#4#5#6{\int_gincr:N\g__test_fast_int\__test_fast:nnnnnn{#1}{#2}{#3}{#4}{#5}{#6}}
\ExplSyntaxOff'''
    body=r'''\bnNative{বাংলা গবেষণা শিক্ষা}
\ExplSyntaxOn\int_compare:nNnF{\g__test_fast_int}>{0}{\errmessage{unused~fast~path}}
\group_begin:\bool_set_false:N\l__bn_mark_pair_enabled_bool\group_end:
\bool_if:NF\l__bn_mark_pair_enabled_bool{\errmessage{grouping}}\ExplSyntaxOff'''
    run_tex(native_install,body,preamble=pre)


def test_source_and_packaged_runtime_match():
    root=Path(__file__).resolve().parents[1]
    assert (root/'tex/latex/bntex/bntex-native-sub.def').read_bytes()==(root/'src/bntex/data/bntex-native-sub.def').read_bytes()


def test_generated_matcher_observer_counts_both_paths(native_install):
    tools=Path(__file__).resolve().parents[1]/'tools'
    sys.path.insert(0,str(tools))
    import native_exclusive_profile as profiler
    pre=profiler.instrumentation(True)
    start,stop=profiler.markers()
    body=start+r'\BnTeXNativeShape{গবেষণা}\BnTeXNativeShape{প্রযুক্তি}'+stop
    fast,_=run_tex(native_install,body,preamble=pre)
    slow,_=run_tex(native_install,body,preamble=GENERIC+pre)
    assert profiler.parse(fast)['phases']['match']['calls']==profiler.parse(slow)['phases']['match']['calls']
    assert profiler.parse(fast)['phases']['match']['calls']>0


def test_varied_prose_preserves_all_existing_fixture_identities():
    tools=Path(__file__).resolve().parents[1]/'tools';sys.path.insert(0,str(tools))
    import native_decode_benchmark as b
    src,spec,words=b.make_source('prose',1,False)
    assert spec['source_sha256']=='06210cf745863fa82aeed6daf4c907772f4beb9f76f94bddf7a87f3aba7d41a8'
    src,spec,words=b.make_source('varied-prose',10,False)
    spans=re.findall(r'\\bnNative\{([^}]+)\}',src)
    assert len(spans)==len(set(spans))==10
    assert spec['token_occurrences']==len(words)
    assert spec['distinct_tokens']==len(set(words))
    assert len(words)>500 and len(set(words))>200
    assert all(len(t.encode())<=4096 for t in spans)


def test_mark_skip_tail_handles_maximum_node_buffer(native_install,tex_profile):
    p=json.loads(tex_profile.read_text())
    rid,lid,(a,b),_=next(eligible(p));mark=next(i for i,c in enumerate(p['glyph_classes']) if c==3)
    body=r'''\ExplSyntaxOn
\int_gset:Nn\g__bn_count_int{8192}
\int_step_inline:nn{8192}{\intarray_gset:Nnn\g__bn_order_intarray{#1}{#1}\intarray_gset:Nnn\g__bn_gid_intarray{#1}{MARK}\intarray_gset:Nnn\g__bn_mask_intarray{#1}{127}\intarray_gset:Nnn\g__bn_syl_intarray{#1}{1}}
\intarray_gset:Nnn\g__bn_gid_intarray{1}{FIRST}
\intarray_gset:Nnn\g__bn_gid_intarray{8192}{SECOND}
'''.replace('MARK',str(mark)).replace('FIRST',str(a)).replace('SECOND',str(b))
    for mode in ('fast','generic'):
        body+=r'\int_gzero:N\g__bn_ops_int'
        if mode=='fast':body+=rf'\use:c{{__bnp_r_{rid}_mark_pair}}{{0}}{{1}}{{0}}'
        else:body+=rf'\__bn_match:nnnnnnnn{{0}}{{\__bn_tab:n{{r_{rid}_pat}}}}{{{lid}}}{{1}}{{1}}{{1}}{{0}}{{0}}'
        body+=snapshot(mode)
    log,_=run_tex(native_install,body+r'\ExplSyntaxOff',timeout=30)
    got=re.findall(r'^PAIR\|(fast|generic)\|(.*)$',log,re.M)
    assert len(got)==2 and got[0][1]==got[1][1]
    assert '|8192|0,8191|' in got[0][1]


@pytest.mark.parametrize('mutation',['delete','change'])
def test_generated_matcher_asset_is_required_and_integrity_checked(native_install,tmp_path,mutation):
    import shutil
    target=tmp_path/'installation';shutil.copytree(native_install,target)
    path=target/'bntex-native-matchers.def'
    manifest=json.loads((target/'native-installation.json').read_text())
    assert manifest['files'][path.name]==hashlib.sha256(path.read_bytes()).hexdigest()
    if mutation=='delete':path.unlink()
    else:path.write_bytes(path.read_bytes()+b'\n% changed\n')
    log,_=run_tex(target,r'\bnNative{বাংলা}',expect_success=False)
    assert path.name in log
