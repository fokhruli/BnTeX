"""Fixed-font compiler/model tests. HarfBuzz is only a comparison oracle here."""
from __future__ import annotations
from dataclasses import asdict, astuple, replace
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import pytest

from bntex.native_profile import (compile_profile, load_profile, serialize, validate, _compile_font,
    ProfileError, PINNED_FONT_SHA256, Feature, Lookup, Single, Multiple, Ligature, Chain,
    PairGlyph, PairClass, MarkBase, MarkMark, Value, Anchor)
from bntex.native_model import NativeShaper, DecodedInput, properties
from bntex.native_layout import Buffer, Item, Layout, ShapingError
from bntex.native import check_reference, main, read_json, write_new

ROOT = Path(__file__).resolve().parents[1]
FONT = Path(os.environ.get('BNTEX_REGULAR_FONT', '/usr/share/fonts/truetype/noto/NotoSerifBengali-Regular.ttf'))
PACKED = ROOT / 'corpus/oracles/user-forms-noto-hb10.2.0.json.gz'
INVENTORY = ROOT / 'corpus/inventories/user-alphabet-v1.json'


def git_blob(raw): return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


@pytest.fixture(scope='module')
def profile():
    if not FONT.exists():
        if os.environ.get('BNTEX_REQUIRE_INTEGRATION'): pytest.fail('pinned local font is required')
        pytest.skip('pinned local font not installed')
    return compile_profile(FONT)


@pytest.fixture(scope='module')
def model(profile): return NativeShaper(profile)


def rows(result): return [list(astuple(g)) for g in result.glyphs]


def frozen_runs():
    raw = PACKED.read_bytes()
    assert git_blob(raw) == '513f018036962986ac9a3663ba2496c1e1a5cbea'
    packed = json.loads(gzip.decompress(raw))
    assert packed['metadata']['font']['sha256'] == PINNED_FONT_SHA256
    assert packed['metadata']['toolchain']['harfbuzz'] == '10.2.0'
    return [(''.join(chr(int(cp,16)) for cp in cid[2:].split('-')), expected) for cid,expected in packed['runs']]


def oracle():
    # Imports intentionally kept out of the executable model and its CLI.
    from bntex.harfbuzz import HarfBuzz
    h = HarfBuzz(FONT)
    if h.version != '10.2.0':
        h.close()
        if os.environ.get('BNTEX_REQUIRE_ORACLE'): pytest.fail('HarfBuzz 10.2.0 is required')
        pytest.skip('generated differential test requires the pinned HarfBuzz 10.2.0')
    return h


def test_profile_closure_and_byte_stability(profile,tmp_path):
    assert profile.font_sha256 == PINNED_FONT_SHA256
    assert (profile.glyph_count,profile.upem,len(profile.cmap)) == (640,1000,173)
    assert (len(profile.gsub),len(profile.gpos)) == (54,6)
    assert len({k for f in profile.gsub_features for k in f.lookups}) == 29
    kinds = {type(s).__name__ for l in profile.gsub + profile.gpos for s in l.subtables}
    assert kinds == {'Single','Multiple','Ligature','Chain','PairGlyph','PairClass','MarkBase','MarkMark'}
    raw=serialize(profile); target=tmp_path/'profile.json'; target.write_bytes(raw)
    assert load_profile(target) == profile
    assert serialize(load_profile(target)) == raw == serialize(compile_profile(FONT))
    assert hashlib.sha256(raw).hexdigest() == 'f6294540099a3b6f622f2cdd9e863050390f75fd0576495d5a2316903f8cfb42'
    assert not any(word.encode() in raw for word in ['বাংলা','প্রযুক্তি','স্বাস্থ্য'])


def test_all_261_frozen_runs_without_executing_harfbuzz(model,monkeypatch):
    import builtins
    original=builtins.__import__
    def guarded(name,*a,**kw):
        if any(s in name for s in ['harfbuzz','fontTools','ctypes']): raise AssertionError(name)
        return original(name,*a,**kw)
    inputs=frozen_runs(); assert len(inputs)==261
    monkeypatch.setattr(builtins,'__import__',guarded)
    for text,expected in inputs:
        result=model.shape(text,allow_broken=True)
        assert rows(result)==expected,text
        assert result.utf8_hex==text.encode().hex() and result.text==text
        assert rows(model.shape_decoded(DecodedInput.from_text(text),allow_broken=True))==expected


def test_original_corpus_frozen_runs(model):
    # This uses the *actual inherited* corpus; no replacement miniature fixture.
    report=check_reference(model,ROOT/'corpus/bengali-v1.json',ROOT/'corpus/oracles/noto-serif-bengali-regular-hb10.2.0.json')
    assert report['status']=='exact-match',report
    assert report['compared_shaped_cases']==128
    assert report['input_rejection_cases_not_compared']==10
    assert report['reference_engine_executed'] is False


def test_1606_conjunct_vowel_interactions(model):
    raw=INVENTORY.read_bytes(); assert git_blob(raw)=='26061b4760c267bd89fe663dcee79486057d926b'
    inventory=json.loads(raw); bases=[t for _,group in inventory['conjunct_groups'] for t in group.split()]
    vowels=['']+[row[1] for row in inventory['vowels'] if row[1]]
    assert len(bases)==146 and len(vowels)==11
    with oracle() as h:
        for base in bases:
            for sign in vowels:
                text=base+sign
                assert rows(model.shape(text)) == [list(astuple(g)) for g in h.shape(text)],text


def test_12000_generated_unseen_word_structures(model):
    # Grammar-shaped probes are not asserted to be words in a dictionary.
    r=random.Random(5126); consonants=list('কখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহ')
    vowels=['','া','ি','ী','ু','ূ','ৃ','ে','ৈ','ো','ৌ']
    with oracle() as h:
        for _ in range(12000):
            parts=[]
            for _ in range(r.randint(1,4)):
                chain='্'.join(r.choices(consonants,k=r.randint(1,4)))
                parts.append(('র্' if r.random()<.2 else '')+chain+r.choice(vowels)+r.choice(['']*8+['ঁ','ং','ঃ']))
            text=''.join(parts)
            assert rows(model.shape(text))==[list(astuple(g)) for g in h.shape(text)],text


@pytest.mark.parametrize('text',[
 'ক\u200cূ','শ\u200dৃ','া\u200cক','ী\u200cক','ফঁং\u200cীষ','ঝ্ন্টি',
 'র্টৌঁ','র্ষ্ম্ঠীঁ','জবশশজঠি\u200dোঁৌৃপ','কিা','ক্্','ক়়','কঁঁ','ঁক',
 'ক্\u200cষ','ক্\u200dষ','র্\u200dক','র্\u200cক','ত্\u200d','ত্\u200c',
 'স্বাস্থ্য','দৃষ্টিভঙ্গি','আত্মবিশ্বাস','প্রযুক্তিবিদ্যা','প্রত্যুৎপন্নমতিত্ব','শৃঙ্খলা',
 'ড়','ড়','ঢ়','ঢ়','য়','য়','কো','কো','কৌ','কৌ','বাংলা।','০১২৩৪৫৬৭৮৯',
])
def test_targeted_normalization_joining_and_component_regressions(model,text):
    with oracle() as h: assert rows(model.shape(text,allow_broken=True))==[list(astuple(g)) for g in h.shape(text)]


@pytest.mark.parametrize('text',['\u200dূ','◌\u200dূ','িৃ\u200dঁ','গঁৃ\u200c\u200dৈৃো'])
def test_unsupported_dotted_circle_joiner_is_explicit(model,text):
    with pytest.raises(ShapingError,match='diagnostic clusters'):
        model.shape(text,allow_broken=True)


@pytest.mark.parametrize('text',['ি','্','ং','্য','ঁক'])
def test_broken_sequences_require_opt_in(model,text):
    with pytest.raises(ShapingError,match='broken sequence'): model.shape(text)
    assert model.shape(text,allow_broken=True).glyphs


def test_trace_stage_boundaries_and_reset(model):
    traced=model.shape('কর্মে',trace=True)
    stages=[e['stage'] for e in traced.trace]
    assert 'working-normalization' in stages and 'syllables' in stages and 'initial-reordering' in stages
    assert 'GSUB' in stages and 'GPOS' in stages and stages[-1]=='output'
    assert traced.glyphs==model.shape('কর্মে').glyphs and model.shape('কি').trace==()
    assert model.shape('কি').glyphs==model.shape('কি').glyphs
    assert all('cluster' in g and 'masks' in g for event in traced.trace for g in event['glyphs'])


@pytest.mark.parametrize('text',['','a','কA','😀','\0','ক\0খ','\ud800','ক\nখ','ক'*1366])
def test_reject_invalid_or_out_of_domain(model,text):
    with pytest.raises(ShapingError): model.shape(text)


@pytest.mark.parametrize('change',[
 {'scalars':(True,)},{'scalars':(0xD800,)},{'scalars':(0x110000,)},
 {'byte_offsets':(1,)},{'byte_lengths':(2,)},{'byte_offsets':(False,)},
 {'utf8_hex':'ff'},{'utf8_hex':'e0a69'},{'utf8_hex':'  e0a695'},
 {'byte_lengths':()},{'scalars':None},
])
def test_decoded_mapping_validation(model,change):
    with pytest.raises(ShapingError): model.shape_decoded(replace(DecodedInput.from_text('ক'),**change))


def test_source_encoding_not_normalized(model):
    a=model.shape('ড়');b=model.shape('ড়')
    assert a.glyphs==b.glyphs and a.utf8_hex!=b.utf8_hex
    assert a.text=='ড়' and b.text=='ড়'
    d=DecodedInput.from_text('ক্ষ');assert d.scalars==(2453,2509,2487) and d.byte_offsets==(0,3,6)
    assert model.shape_decoded(replace(d,utf8_hex=d.utf8_hex.upper())).utf8_hex==d.utf8_hex


def test_call_and_syllable_limits(model):
    assert len(model.shape('1'*4096).glyphs)==4096
    with pytest.raises(ShapingError,match='oversized'):model.shape('1'*4097)
    with pytest.raises(ShapingError,match='working scalars'):model.shape('ক'+'্ক'*40)
    with pytest.raises(ShapingError,match='snapshot budget'):model.shape('1'*4096,trace=True)
    with pytest.raises(ShapingError,match='booleans'):model.shape('ক',trace=1)
    b=Buffer([Item(1,1,0)],max_operations=1);b.tick()
    with pytest.raises(ShapingError,match='operation budget'):b.tick()
    with pytest.raises(ShapingError,match='glyph expansion'):Buffer([Item(1,1,0)]*8193).tick()


@pytest.mark.parametrize('field,value',[
 ('abi',True),('abi',2),('glyph_count',True),('script','beng'),('font_sha256','0'*64),
 ('upem',-1),('unrecognized',0),('kind','another-profile'),
])
def test_json_schema_corruption(profile,tmp_path,field,value):
    data=asdict(profile);data[field]=value;p=tmp_path/'bad.json';p.write_text(json.dumps(data))
    with pytest.raises(ProfileError):load_profile(p)


@pytest.mark.parametrize('raw',[b'[]',b'{"a":1,"a":2}',b'{"a":NaN}',b'\xff',b'{',b'{"a":'+b'['*80+b'0'+b']'*80+b'}'])
def test_malformed_profile_json(tmp_path,raw):
    p=tmp_path/'bad.json';p.write_bytes(raw)
    with pytest.raises(ProfileError):load_profile(p)


def test_profile_invalid_references(profile):
    with pytest.raises(ProfileError,match='dangling'):validate(replace(profile,gsub_features=(Feature('half',(999,)),)))
    cycle=Lookup(0,0,None,(Chain('chain',(),((1,),),(),((0,0),)),))
    with pytest.raises(ProfileError,match='Cyclic'):validate(replace(profile,gsub=(cycle,),gsub_features=(Feature('half',(0,)),)))
    bad=Lookup(0,16,99,(Single('single',((1,2),)),))
    with pytest.raises(ProfileError,match='filtering'):validate(replace(profile,gsub=(bad,),gsub_features=(Feature('half',(0,)),)))
    for flag in (1,32):
        with pytest.raises(ProfileError):validate(replace(profile,gsub=(replace(bad,flags=flag,mark_filter_set=None),),gsub_features=(Feature('half',(0,)),)))
    with pytest.raises(ProfileError,match='every glyph'):validate(replace(profile,advances=profile.advances[:-1]))


def test_wrong_font_rejected_before_parsing(tmp_path):
    font=tmp_path/'not-a-font.ttf';font.write_bytes(b'font')
    with pytest.raises(ProfileError,match='pinned'):compile_profile(font)


@pytest.mark.parametrize('mode',['device','anchor','variation','extension','context-format'])
def test_unsupported_required_font_construct(profile,mode):
    from fontTools.ttLib import TTFont
    with TTFont(FONT) as font:
        if mode=='device':font['GPOS'].table.LookupList.Lookup[0].SubTable[0].ValueFormat1=0x10
        elif mode=='anchor':font['GPOS'].table.LookupList.Lookup[1].SubTable[0].MarkArray.MarkRecord[0].MarkAnchor.Format=2
        elif mode=='variation':font['GDEF'].table.VarStore=object()
        elif mode=='extension':font['GSUB'].table.LookupList.Lookup[7].LookupType=99
        else:
            lookup=next(l for l in font['GSUB'].table.LookupList.Lookup if l.LookupType==6)
            lookup.SubTable[0].Format=1
        with pytest.raises(ProfileError):_compile_font(font,PINNED_FONT_SHA256)


def synthetic(profile,lookups,features=(Feature('test',(0,)),),*,gpos=()):
    return replace(profile,gsub=tuple(lookups),gsub_features=features,gpos=tuple(gpos),
                   gpos_features=(Feature('mark',tuple(l.index for l in gpos)),) if gpos else ())


def test_ordered_ligature_rules_not_longest_dictionary(profile):
    p=synthetic(profile,[Lookup(0,0,None,(Ligature('ligature',(((1,2),4),((1,2,3),5))),))])
    b=Buffer([Item(i,0,i) for i in (1,2,3)]);Layout(p).apply_gsub(b,('test',))
    assert [g.gid for g in b.items]==[4,3]


def test_nested_context_targets_after_length_change(profile):
    p=synthetic(profile,[Lookup(0,0,None,(Chain('chain',(),((1,),(2,)),(),((0,1),(1,2))),)),
      Lookup(1,0,None,(Multiple('multiple',((1,(3,4)),)),)),Lookup(2,0,None,(Single('single',((2,5),)),))])
    b=Buffer([Item(1,0,0),Item(2,0,3)]);Layout(p).apply_gsub(b,('test',))
    assert [g.gid for g in b.items]==[3,4,5]


def test_class_zero_pair_positioning(profile):
    tab=PairClass('pair-class',True,False,(1,),(),(),(((Value(x_advance=-20),Value()),),))
    p=synthetic(profile,[],(),gpos=[Lookup(0,0,None,(tab,))])
    b=Buffer([Item(1,0,0),Item(2,0,1)]);Layout(p).apply_gpos(b)
    assert b.items[0].advance==profile.advances[1]-20


def test_mark_attachment_offsets_use_parent_pen(profile):
    p=synthetic(profile,[],(),gpos=[Lookup(0,0,None,(MarkBase('mark-base',1,
          ((623,0,Anchor(10,20)),),((238,(Anchor(90,120),)),)),))])
    b=Buffer([Item(238,0,0),Item(623,0,1)]);Layout(p).apply_gpos(b)
    assert (b.items[1].x_offset,b.items[1].y_offset)==(80-profile.advances[238],100)


def test_isolated_runtime_requires_no_font_or_shaping_library(profile,tmp_path):
    p=tmp_path/'profile.json';p.write_bytes(serialize(profile))
    script=r'''
import sys,importlib.abc,json
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,*args,**kwargs):
  if fullname.split('.')[0] in {'ctypes','fontTools','uharfbuzz'} or 'harfbuzz' in fullname:
   raise RuntimeError('forbidden runtime import: '+fullname)
sys.meta_path.insert(0,Block())
from bntex.native_profile import load_profile
from bntex.native_model import NativeShaper,DecodedInput
s=NativeShaper(load_profile(sys.argv[1]))
print(json.dumps(s.shape_decoded(DecodedInput.from_text('আত্মবিশ্বাস')).to_dict(),ensure_ascii=False))
'''
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PATH=str(tmp_path/'empty-path'))
    done=subprocess.run([sys.executable,'-S','-c',script,str(p)],cwd=tmp_path,env=env,capture_output=True,text=True,timeout=20)
    assert done.returncode==0,done.stderr
    result=json.loads(done.stdout);assert result['text']=='আত্মবিশ্বাস' and result['glyphs']


def test_pdftex_decoded_handoff(profile,tmp_path):
    engine=shutil.which('pdflatex')
    if not engine:
        if os.environ.get('BNTEX_REQUIRE_INTEGRATION'):pytest.fail('pdfLaTeX required')
        pytest.skip('pdfLaTeX not installed')
    source=r'''\documentclass{article}
\usepackage{bntex-utf8}
\begin{document}
\BnTeXDecodeUTFviii{ক্ষ}
{\typeout{NATIVE-S=\BnTeXUTFviiiScalars}
 \typeout{NATIVE-O=\BnTeXUTFviiiOffsets}
 \typeout{NATIVE-L=\BnTeXUTFviiiLengths}
 \typeout{NATIVE-H=\BnTeXUTFviiiHex}}
{\errmessage{Decoder failed}}
Decoder-to-model interface test.
\end{document}
'''
    (tmp_path/'main.tex').write_text(source)
    env=dict(os.environ,TEXINPUTS=str(ROOT/'tex/latex/bntex')+os.pathsep,PATH=str(tmp_path/'empty'))
    r=subprocess.run([engine,'-no-shell-escape','-halt-on-error','main.tex'],cwd=tmp_path,env=env,capture_output=True,timeout=30)
    assert r.returncode==0,r.stdout.decode(errors='replace')
    log=(tmp_path/'main.log').read_text();values={k:re.search('NATIVE-'+k+'=([^\n]+)',log).group(1) for k in 'SOLH'}
    d=DecodedInput(*(tuple(map(int,values[k].split(','))) for k in 'SOL'),values['H'])
    assert d==replace(DecodedInput.from_text('ক্ষ'),utf8_hex=d.utf8_hex)
    assert NativeShaper(profile).shape_decoded(d).glyphs==NativeShaper(profile).shape('ক্ষ').glyphs


def test_cli_safeguards_and_decoded_input(profile,tmp_path,capsys):
    pp=tmp_path/'profile.json';pp.write_bytes(serialize(profile));out=tmp_path/'out.json'
    assert main(['shape','--profile',str(pp),'--text','ক্ষ','--out',str(out)])==0
    before=out.read_bytes();assert main(['shape','--profile',str(pp),'--text','ক','--out',str(out)])==2
    assert out.read_bytes()==before
    assert main(['shape','--profile',str(pp),'--text','ক','--out',str(pp)])==2
    assert pp.read_bytes()==serialize(profile)
    d=tmp_path/'decoded.json';d.write_text(json.dumps(asdict(DecodedInput.from_text('কর্ম'))))
    assert main(['shape','--profile',str(pp),'--decoded',str(d)])==0
    assert main(['compile','--font',str(FONT),'--out',str(pp)])==2
    link=tmp_path/'symlink';link.symlink_to(out)
    with pytest.raises(ValueError):write_new(link,b'bad',[])


def test_check_detects_corrupted_glyph_field(model,tmp_path):
    text='ক্ষ';case={'id':'test','text':text,'utf8_hex':text.encode().hex(),'expect':'shape'}
    corpus={'version':'1','cases':[case]};cp=tmp_path/'corpus.json';cp.write_text(json.dumps(corpus))
    config={'direction':'ltr','script':'Beng','language':'bn','cluster_level':0,'cluster_units':'utf8-bytes',
            'buffer_flags':0,'features':'HarfBuzz defaults','face_index':0,'scale':'upem','font_funcs':'ot',
            'normalization':'HarfBuzz internal; source preserved'}
    frozen={'schema':1,'generator_abi':1,'toolchain':{'harfbuzz':'10.2.0'},'kind':'bntex-pinned-shaping-oracle','corpus_sha256':hashlib.sha256(cp.read_bytes()).hexdigest(),
      'corpus_version':'1','font':{'sha256':PINNED_FONT_SHA256},'config':config,
      'glyph_fields':['gid','cluster','x_advance','y_advance','x_offset','y_offset','flags'],
      'records':[{'id':'test','outcome':'shape','source_sha256':hashlib.sha256(text.encode()).hexdigest(),
                  'glyphs':rows(model.shape(text))}]}
    op=tmp_path/'oracle.json';op.write_text(json.dumps(frozen))
    assert check_reference(model,cp,op)['status']=='exact-match'
    frozen['records'][0]['glyphs'][0][4]+=1;op.write_text(json.dumps(frozen))
    assert check_reference(model,cp,op)['mismatches']==1
    frozen['records'][0]['glyphs'][0][4]=True;op.write_text(json.dumps(frozen))
    with pytest.raises(ValueError,match='glyph rows'):check_reference(model,cp,op)


def test_rule_content_digest_not_just_font_metadata(profile):
    altered=list(profile.advances);altered[238]+=1
    with pytest.raises(ShapingError,match='compiled-rule fingerprint'):
        NativeShaper(replace(profile,advances=tuple(altered)))


def test_all_96_mapped_bengali_scalars(profile,model):
    scalars=[cp for cp,_ in profile.cmap if 0x980<=cp<=0x9ff]
    assert len(scalars)==96
    with oracle() as h:
        for cp in scalars:
            text=chr(cp)
            assert rows(model.shape(text,allow_broken=True))==[list(astuple(g)) for g in h.shape(text)],hex(cp)


@pytest.mark.parametrize('change', ['null-font','wrong-version','nonobject-case','boolean-config'])
def test_check_rejects_malformed_reference_metadata(model,tmp_path,change):
    text='ক্ষ';cp=tmp_path/'corpus.json';op=tmp_path/'oracle.json'
    case={'id':'test','text':text,'utf8_hex':text.encode().hex(),'expect':'shape'}
    corpus={'version':'1','cases':[case]}
    config={'direction':'ltr','script':'Beng','language':'bn','cluster_level':0,'cluster_units':'utf8-bytes',
      'buffer_flags':0,'features':'HarfBuzz defaults','face_index':0,'scale':'upem','font_funcs':'ot',
      'normalization':'HarfBuzz internal; source preserved'}
    frozen={'schema':1,'generator_abi':1,'kind':'bntex-pinned-shaping-oracle','corpus_version':'1',
      'font':{'sha256':PINNED_FONT_SHA256},'toolchain':{'harfbuzz':'10.2.0'},'config':config,
      'glyph_fields':['gid','cluster','x_advance','y_advance','x_offset','y_offset','flags'],
      'records':[{'id':'test','outcome':'shape','source_sha256':hashlib.sha256(text.encode()).hexdigest(),
                  'glyphs':rows(model.shape(text))}]}
    if change=='null-font': frozen['font']=None
    elif change=='wrong-version': frozen['toolchain']['harfbuzz']='0.0'
    elif change=='nonobject-case': corpus['cases']=[None]
    else: config['cluster_level']=False
    cp.write_text(json.dumps(corpus));frozen['corpus_sha256']=hashlib.sha256(cp.read_bytes()).hexdigest()
    op.write_text(json.dumps(frozen))
    with pytest.raises(ValueError): check_reference(model,cp,op)
