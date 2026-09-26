"""Observer arithmetic, failure checks, output integrity, and real pdfTeX."""
from pathlib import Path
import re
import sys
import pytest
TOOLS=Path(__file__).resolve().parents[1]/'tools'
if str(TOOLS) not in sys.path:sys.path.insert(0,str(TOOLS))
import native_exclusive_profile as p
from test_native_tex import tex_profile,native_install,run_tex


def valid_log():
    return '\n'.join(f'BNTEX-PROFILE|{name}|{1 if i==0 else 0}|{110 if i==0 else 0}|{110 if i==0 else 0}'
                     for i,(name,_,_) in enumerate(p.PHASES))


def test_parse_partitions_without_double_count():
    result=p.parse(valid_log())
    assert result['instrumented_body_ticks']==110
    assert sum(r['exclusive_fraction'] for r in result['phases'].values())==1

@pytest.mark.parametrize('change',[
 lambda s:s+'\n'+s.splitlines()[0],
 lambda s:'\n'.join(s.splitlines()[1:]),
 lambda s:'\n'.join(reversed(s.splitlines())),
 lambda s:s.replace('|1|110|110','|1|109|110'),
 lambda s:s.replace('|1|110|110','|1|-1|110'),
 lambda s:s.replace('|1|110|110','|1|0|0'),
 lambda s:s.replace('decode_collect|0|0|0','decode_collect|1|1|0').replace('|1|110|110','|1|109|110'),
])
def test_corrupt_profile_rejected(change):
    with pytest.raises(ValueError):p.parse(change(valid_log()))


def test_fake_nested_clock_exact_accounting(native_install):
    pre=p.instrumentation(True)+r'''\ExplSyntaxOn
\int_new:N\g__test_clock_int
\cs_set:Npn\__bne_clock:{\int_use:N\g__test_clock_int}
\ExplSyntaxOff'''
    _,stop=p.markers()
    body=r'''\ExplSyntaxOn
\int_gset:Nn\g__test_clock_int{10}\__bne_start:
\int_gset:Nn\g__test_clock_int{20}\__bne_enter:n{2}
\int_gset:Nn\g__test_clock_int{30}\__bne_enter:n{6}
\int_gset:Nn\g__test_clock_int{40}\__bne_enter:n{6}
\int_gset:Nn\g__test_clock_int{60}\__bne_exit:
\int_gset:Nn\g__test_clock_int{90}\__bne_exit:
\int_gset:Nn\g__test_clock_int{110}\__bne_exit:
\int_gset:Nn\g__test_clock_int{120}\ExplSyntaxOff'''+stop
    output,_=run_tex(native_install,body,preamble=pre)
    rows=p.parse(output)['phases']
    assert rows['unattributed']['exclusive_ticks']==20
    assert rows['execute_other']['exclusive_ticks']==30
    assert rows['execute_other']['inclusive_ticks']==90
    assert rows['substitution']['exclusive_ticks']==60
    assert rows['substitution']['inclusive_ticks']==80
    assert rows['substitution']['calls']==2

@pytest.mark.parametrize('body,message',[
 (r'\__bne_enter:n{2}','not running'),
 (r'\__bne_exit:','stack underflow'),
 (r'\__bne_stop:','unbalanced stack'),
 (r'\__bne_start:\__bne_start:','already running'),
 (r'\__bne_start:\__bne_enter:n{0}','tag range'),
 (r'\__bne_start:\__bne_enter:n{13}','tag range'),
 (r'\__bne_start:\int_step_inline:nn{64}{\__bne_enter:n{2}}','stack limit'),
 (r'\__bne_start:\cs_set:Npn\__bne_clock:{0}\__bne_stop:','clock wrapped'),
])
def test_runtime_guards(native_install,body,message):
    output,_=run_tex(native_install,r'\ExplSyntaxOn'+body+r'\ExplSyntaxOff',
                     preamble=p.instrumentation(True),expect_success=False)
    assert message in output

@pytest.mark.parametrize('words',[
 ['কর্ম','কো','ড়','ক্‍ষ','ক্‌ষ'],
 ['র্শ্ম্ফ্ট্টি','র্টৌঁ','ক্ষ্ম','হৃ','ত্রিমাত্রিকীকরণসমূহ'],
])
def test_observer_does_not_change_complete_traces(native_install,words):
    body=r'\BnTeXNativeTraceOn'+''.join(r'\BnTeXNativeShape{'+w+r'}\BnTeXNativeDump' for w in words)
    a,_=run_tex(native_install,body)
    start,stop=p.markers()
    b,_=run_tex(native_install,start+body+stop,preamble=p.instrumentation(True))
    prefixes=('BNTEX-STAGE|','BNTEX-NODE|','BNTEX-RUN|','BNTEX-GLYPH|')
    assert [l for l in a.splitlines() if l.startswith(prefixes)]==[l for l in b.splitlines() if l.startswith(prefixes)]
    assert p.parse(b)['phases']['execute_other']['calls']==len(words)

@pytest.mark.parametrize('kind',['distinct','repeated','digits-free','prose'])
def test_fixed_fixture_compile_and_drawings(native_install,tmp_path,kind):
    report=p.run(native_install,tmp_path/'report',kind=kind,repetitions=1,detail=True)
    assert report['all_drawings_equal']
    assert all(s['result']['all_tokens_extracted'] for s in report['samples'])
    assert all(s['result']['runs'][0]['immutable_assets_unchanged'] for s in report['samples'])
    for s in report['samples']:
        if s['mode']=='profiled':
            expected=1 if kind=='prose' else 6
            assert s['profile']['phases']['decode_collect']['calls']==expected


def test_rejects_invalid_fixture_and_repetitions(tmp_path):
    with pytest.raises(ValueError):p.instrument_source('not a document')
    with pytest.raises(ValueError):p.run(tmp_path,tmp_path/'new',repetitions=True)
    with pytest.raises(ValueError):p.run(tmp_path,tmp_path/'new',memo='on')
    tmp_path.joinpath('exists').mkdir()
    with pytest.raises(ValueError):p.run(tmp_path,tmp_path/'exists')


def small_pdf(path,name='/F1',base='/Helvetica',coordinate=10,actual='বাংলা'):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    writer=PdfWriter();page=writer.add_blank_page(width=200,height=100)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject(base)})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject(name):writer._add_object(font)})})
    stream=DecodedStreamObject()
    stream.set_data((f'/Span << /ActualText <FEFF{actual.encode("utf-16-be").hex()}> >> BDC BT {name} 10 Tf {coordinate} 10 Td (abc) Tj ET EMC').encode())
    page[NameObject('/Contents')]=writer._add_object(stream)
    with path.open('wb') as f:writer.write(f)


def test_resource_alias_is_not_drawing_change(tmp_path):
    a,b=tmp_path/'a.pdf',tmp_path/'b.pdf'
    small_pdf(a);small_pdf(b,name='/F72')
    assert p.drawing_identity(a)==p.drawing_identity(b)

@pytest.mark.parametrize('change',[{'base':'/Times-Roman'},{'coordinate':11},{'actual':'ভাষা'}])
def test_font_position_and_actualtext_changes_detected(tmp_path,change):
    a,b=tmp_path/'a.pdf',tmp_path/'b.pdf'
    small_pdf(a);small_pdf(b,**change)
    assert p.drawing_identity(a)!=p.drawing_identity(b)


def test_repeated_vocabulary_memo_is_separate(native_install,tmp_path):
    report=p.run(native_install,tmp_path/'memo',kind='repeated',repetitions=1,detail=True,memo=True)
    assert report['fixture']['memo_enabled'] is True
    assert report['fixture']['token_occurrences']==96
    assert report['fixture']['distinct_tokens']==16
    assert report['all_drawings_equal']
    for sample in report['samples']:
        counts=sample['result']['runs'][0]['memo']
        assert counts['hits']==80 and counts['misses']==16
        if sample['mode']=='profiled':
            assert sample['profile']['phases']['execute_other']['calls']==16
            assert sample['profile']['phases']['decode_collect']['calls']==6
