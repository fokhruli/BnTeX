"""Execute the expl3 shaper, not Python-prepared runs, in cache-free pdfTeX jobs.

Font installation is a session fixture completed before test text is selected.
Python is a test driver/reference only. The engine has shell execution disabled,
an empty executable search path, no Python modules/corpus/cache in its directory,
and a recorder audit. Exact frozen glyphs are never regenerated.
"""
from __future__ import annotations
from dataclasses import asdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import time

import pytest
from bntex.tex_export import export, emit_tables, grammar_dfa, MODULES, PROFILE_SHA, FONT_SHA

ROOT = Path(__file__).resolve().parents[1]
FONT = Path(os.environ.get('BNTEX_REGULAR_FONT', '/usr/share/fonts/truetype/noto/NotoSerifBengali-Regular.ttf'))
pytestmark = pytest.mark.integration
CONJUNCTS = '''ক্ক ক্ট ক্ত ক্ব ক্ম ক্র ক্ল ক্স ক্ষ ক্ষ্ণ ক্ষ্ম ক্ষ্য
গ্ধ গ্ন গ্ব গ্ম গ্র গ্ল ঘ্ন ঘ্র ঙ্ক ঙ্ক্ষ ঙ্খ ঙ্গ ঙ্ঘ চ্চ চ্ছ চ্ছ্ব চ্ঞ
জ্জ জ্ঝ জ্ঞ জ্ব জ্র ঞ্চ ঞ্ছ ঞ্জ ঞ্ঝ ট্ট ট্ব ট্র ড্ড ড্র ণ্ট ণ্ঠ ণ্ড ণ্ণ ণ্ব ণ্ম
ত্ত ত্ত্ব ত্থ ত্ন ত্ব ত্ম ত্র থ্ব থ্র দ্গ দ্দ দ্ধ দ্ব দ্ভ দ্ম দ্র ধ্ন ধ্ব ধ্র
ন্ট ন্ড ন্ত ন্ত্র ন্ত্ব ন্থ ন্দ ন্দ্র ন্ধ ন্ন ন্ব ন্ম প্ট প্ত প্ন প্প প্র প্ল প্স ফ্র ফ্ল
ব্জ ব্দ ব্ধ ব্ব ব্র ব্ল ভ্র ম্ন ম্প ম্ব ম্ভ ম্ম ম্র ম্ল ল্ক ল্গ ল্ট ল্ড ল্প ল্ব ল্ম ল্ল
শ্চ শ্ছ শ্ন শ্ব শ্ম শ্র শ্ল ষ্ক ষ্ট ষ্ট্র ষ্ঠ ষ্ণ ষ্প ষ্ফ ষ্ম
স্ক স্ক্র স্খ স্ট স্ত স্ত্র স্থ স্ন স্প স্ফ স্ব স্ম স্র স্ল হ্ণ হ্ন হ্ম হ্ব হ্র হ্ল'''.split()
MATRAS = ['', 'া', 'ি', 'ী', 'ু', 'ূ', 'ৃ', 'ে', 'ৈ', 'ো', 'ৌ']


def need(program: str) -> str:
    path = shutil.which(program)
    if path:
        return str(Path(path).absolute())  # Preserve pdfLaTeX's program name.
    if os.environ.get('BNTEX_REQUIRE_INTEGRATION') == '1':
        pytest.fail(f'Native TeX integration requires {program}.')
    pytest.skip(f'Install {program} to execute native TeX integration.')


@pytest.fixture(scope='session')
def tex_profile(tmp_path_factory):
    need('pdflatex'); need('pltotf')
    if not FONT.is_file():
        if os.environ.get('BNTEX_REQUIRE_INTEGRATION') == '1': pytest.fail('Pinned font is required.')
        pytest.skip('Install the pinned Noto Serif Bengali Regular font.')
    assert hashlib.sha256(FONT.read_bytes()).hexdigest() == FONT_SHA
    supplied = os.environ.get('BNTEX_NATIVE_PROFILE_JSON')
    if supplied:
        raw = Path(supplied).read_bytes()
    else:
        from bntex.native_profile import compile_profile, serialize
        raw = serialize(compile_profile(FONT))
    assert hashlib.sha256(raw).hexdigest() == PROFILE_SHA
    path = tmp_path_factory.mktemp('font-only') / 'profile.json'
    path.write_bytes(raw)
    return path


@pytest.fixture(scope='session')
def native_install(tex_profile, tmp_path_factory):
    target = tmp_path_factory.mktemp('native-runtime') / 'installation'
    manifest = export(tex_profile, FONT, target)
    assert manifest['vocabulary'] is None
    assert not list(target.glob('*.py'))
    assert not list(target.glob('*cache*'))
    return target


@pytest.fixture(scope='session')
def hb_reference():
    from bntex.harfbuzz import HarfBuzz
    with HarfBuzz(FONT) as hb:
        if hb.version != '10.2.0':
            if os.environ.get('BNTEX_REQUIRE_ORACLE') == '1':
                pytest.fail('Exact live differential tests require HarfBuzz 10.2.0.')
            pytest.skip('This environment is not the pinned live reference; frozen tests still run.')
        yield hb


def run_tex(directory: Path, body: str, *, preamble='', expect_success=True, timeout=45):
    engine = need('pdflatex')
    (directory / 'empty-bin').mkdir(exist_ok=True)
    env = dict(os.environ, PATH=str(directory / 'empty-bin'), TEXINPUTS='.:',
               max_print_line='10000', openin_any='p', openout_any='p',
               MKTEXPK='0', MKTEXTFM='0', SOURCE_DATE_EPOCH='1', FORCE_SOURCE_DATE='1')
    source = ('\\errorcontextlines=40\n\\documentclass{article}\n'
              '\\usepackage{bntex-native}\n'
              '\\BnTeXNativeLoadProfile{bntex-native-profile.tex}\n' + preamble + '\n'
              '\\begin{document}\n\\ifnum\\pdfshellescape=0\\else\\errmessage{shell enabled}\\fi\n'
              + body + '\n\\end{document}\n')
    (directory / 'native-case.tex').write_text(source, encoding='utf-8')
    t0 = time.monotonic()
    result = subprocess.run([engine, '-no-shell-escape', '-halt-on-error', '-interaction=nonstopmode',
                             '-recorder', 'native-case.tex'], cwd=directory, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    text = result.stdout.decode('utf-8', errors='replace')
    if expect_success:
        assert result.returncode == 0, text[-10000:]
        assert 'Missing character:' not in text
        recorded = (directory / 'native-case.fls').read_text()
        inputs = [line[6:] for line in recorded.splitlines() if line.startswith('INPUT ')]
        assert not any(Path(p).suffix in {'.py', '.json', '.jsonl', '.gz'} or 'bntex-cache' in p for p in inputs)
    else:
        assert result.returncode != 0, text
    return text, time.monotonic() - t0


def shape_runs(directory: Path, texts: list[str], *, literal=False):
    body = []
    for i, text in enumerate(texts):
        data = text if literal else text.encode('utf-8').hex()
        command = 'BnTeXNativeShape' if literal else 'BnTeXNativeShapeHex'
        body.append(f'\\typeout{{CASE|{i}}}\\{command}{{{data}}}\\BnTeXNativeDump')
    output, elapsed = run_tex(directory, '\n'.join(body))
    actual, sources, index = [], [], -1
    for line in output.splitlines():
        if line.startswith('CASE|'):
            index = int(line.split('|')[1]); assert index == len(actual)
            actual.append([])
        elif line.startswith('BNTEX-RUN|'):
            sources.append(line.split('|')[1].lower())
        elif line.startswith('BNTEX-GLYPH|'):
            actual[index].append(list(map(int, line.split('|')[1:])))
    assert len(actual) == len(texts)
    assert sources == [s.encode().hex() for s in texts]
    return actual, elapsed


def rows(glyphs):
    return [list(asdict(g).values()) for g in glyphs]


@pytest.mark.parametrize('block', range(3))
def test_frozen_inventory_all_seven_fields(native_install, block):
    raw = (ROOT / 'corpus/oracles/user-forms-noto-hb10.2.0.json.gz').read_bytes()
    assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == '513f018036962986ac9a3663ba2496c1e1a5cbea'
    frozen = json.loads(gzip.decompress(raw))['runs']
    assert len(frozen) == 261
    batch = frozen[block*87:(block+1)*87]
    texts = [''.join(chr(int(c, 16)) for c in cid[2:].split('-')) for cid, _ in batch]
    actual, _ = shape_runs(native_install, texts, literal=True)
    for text, got, (_, expected) in zip(texts, actual, batch): assert got == expected, (text, got, expected)


@pytest.mark.parametrize('sign', MATRAS)
def test_conjunct_matra_matrix(native_install, hb_reference, sign):
    assert len(set(CONJUNCTS)) == 146
    texts = [c+sign for c in CONJUNCTS]
    actual, _ = shape_runs(native_install, texts)
    for text, got in zip(texts, actual): assert got == rows(hb_reference.shape(text)), text


def generated(seed, count):
    rng = random.Random(seed)
    consonants = list('কখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহ') + ['ড়', 'ঢ়', 'য়', 'ড়', 'ঢ়', 'য়']
    for _ in range(count):
        parts=[]
        for __ in range(rng.randint(1, 3)):
            cs=[rng.choice(consonants) for ___ in range(rng.randint(1, 5))]
            parts.append(('র্' if rng.random()<.3 else '')+'্'.join(cs)+rng.choice(MATRAS+['ৄ','ৢ','ৣ','ো','ৌ'])
                         +rng.choice(['','','','ঁ','ং','ঃ']))
        yield ''.join(parts)


@pytest.mark.parametrize('seed', [6601,6602,6603,6604,6605,6606,6607,6608])
def test_generated_extended_runs(native_install, hb_reference, seed):
    # 8 x 24 generated probes, not approved Bengali dictionary words.
    texts=list(generated(seed,24))
    actual,_=shape_runs(native_install,texts)
    for text,got in zip(texts,actual): assert got==rows(hb_reference.shape(text)), (text,got,rows(hb_reference.shape(text)))


def test_join_controls_and_regressions(native_install, hb_reference):
    texts=[a+'্'+j+b+s for a in ['ক','র','ত'] for j in ['','\u200c','\u200d'] for b in ['ক','য','র'] for s in ['','ি','ো','ু']]
    texts += ['র্টৌঁ','র্শ্ম্ফ্ট্টি','ক\u200dু','ক\u200cু','র্\u200dক','ত্\u200c','ত্\u200d','অ্যা']
    actual,_=shape_runs(native_install,texts)
    for text,got in zip(texts,actual): assert got==rows(hb_reference.shape(text)), (text,got,rows(hb_reference.shape(text)))


def test_literal_hex_equivalence_and_original_bytes(native_install):
    texts=['ক্ষ','কর্ম','সূর্য','কো','কো','কৌ','কৌ','ড়','ড়','য়','য়','ক্\u200dষ','ক্\u200cষ']
    a,_=shape_runs(native_install,texts,literal=True); b,_=shape_runs(native_install,texts)
    assert a==b


@pytest.mark.parametrize('text,message', [
    ('','empty'), ('\0','unsupported'), ('A','unsupported'), ('😀','non-BMP'),
    ('কিা','multiple'), ('ক়়','nukta'), ('কঁঁ','terminal'), ('ক্্','broken'),
    ('ঁক','broken'), ('অা','independent'), ('ক\u200d\u200cষ','consecutive'),
    ('\u200dূ','broken'), (' ি','broken'), ('ক ি','broken'), (' ো','broken'), ('ক'*1366,'UTF-8'), ('ক্'*40+'ক','64'),
])
def test_explicit_rejections(native_install,text,message):
    output,_=run_tex(native_install,'\\BnTeXNativeShapeHex{'+text.encode().hex()+'}',expect_success=False)
    assert message.lower() in output.lower(), output[-4000:]


@pytest.mark.parametrize('raw', ['80','c0af','e0a6','eda080','f4908080','f0808080','e0a641'])
def test_malformed_byte_rejection(native_install, raw):
    output,_=run_tex(native_install,'\\BnTeXNativeShapeHex{'+raw+'}',expect_success=False)
    assert 'UTF-8' in output


def test_scope_no_input_macro_execution(native_install):
    output,_=run_tex(native_install,r'\def\trap{\errmessage{TRAP EXECUTED}}\bnNative{\trap}',expect_success=False)
    assert 'literal' in output and '! TRAP EXECUTED' not in output


@pytest.mark.parametrize('prefix,message', [(r'\bfseries','regular'),(r'\itshape','upright'),('$','text mode')])
def test_unsupported_outer_styles_are_not_silent(native_install,prefix,message):
    output,_=run_tex(native_install,prefix+r'\bnNative{বাংলা}',expect_success=False)
    assert message in output.replace('~',' '),output[-2000:]


def test_empty_bin_unseen_edit_and_pdf_semantics(native_install):
    # Installation exists first. No vocabulary is supplied when it is exported.
    installed=json.loads((native_install/'native-installation.json').read_text())
    before={name:hashlib.sha256((native_install/name).read_bytes()).hexdigest() for name in installed['files']}
    words=['অণুজীবপ্রযুক্তিগত','পুনর্বিন্যাসসমূহ','শিক্ষকসম্মেলনের','দূরনিয়ন্ত্রণযোগ্যতা']
    reference=json.loads(gzip.decompress((ROOT/'corpus/oracles/user-forms-noto-hb10.2.0.json.gz').read_bytes()))
    known={''.join(chr(int(c,16)) for c in cid[2:].split('-')) for cid,_ in reference['runs']}
    assert not known.intersection(words)
    body='English remains Latin.\n\\par\\bnNative{'+' '.join(words)+'}\n'
    # Choose another spelling after the first actual compile, without re-export.
    run_tex(native_install,body)
    extra='কো কো ক্\u200dষ ক্\u200cষ ড় ড়'
    run_tex(native_install,body+'\\par\\bnNative{'+extra+'}')
    after={name:hashlib.sha256((native_install/name).read_bytes()).hexdigest() for name in before}
    assert before==after
    text=subprocess.check_output([need('pdftotext'),'-enc','UTF-8',str(native_install/'native-case.pdf'),'-']).decode()
    for word in words+extra.split(): assert word in text,(word,text)
    fonts=subprocess.check_output([need('pdffonts'),str(native_install/'native-case.pdf')]).decode()
    assert 'TrueType' in fonts and 'Type 3' not in fonts
    assert 'English remains Latin.' in text


@pytest.mark.parametrize('size',[10,12,17])
def test_native_word_geometry(native_install,hb_reference,tex_profile,size):
    texts=['ক্ষ','প্রযুক্তি','স্বাস্থ্য','কর্ম','সূর্য','র্টৌঁ','কু','ড়','কো','কো']
    body='\\fontsize{'+str(size)+'}{'+str(size*1.4)+'}\\selectfont\n'
    for i,t in enumerate(texts):body+=f'\\setbox0=\\hbox{{\\bnNative{{{t}}}}}\\typeout{{SIZE|{i}|\\number\\wd0|\\number\\ht0|\\number\\dp0}}\n'
    output,_=run_tex(native_install,body)
    measurements=[list(map(int,line.split('|')[1:])) for line in output.splitlines() if line.startswith('SIZE|')]
    assert len(measurements)==len(texts)
    profile=json.loads(tex_profile.read_bytes())
    for i,w,h,d in measurements:
        gs=hb_reference.shape(texts[i]); height=max([0]+[g.y_offset+(profile['bounds'][g.gid] or [0]*4)[3] for g in gs])
        depth=-min([0]+[g.y_offset+(profile['bounds'][g.gid] or [0]*4)[1] for g in gs])
        expected=[sum(g.x_advance for g in gs),height,depth]
        for got,units in zip((w,h,d),expected):assert abs(got-units*size*65536/1000)<=1,(texts[i],got,units)


def test_trace_and_repeat_state(native_install):
    output,_=run_tex(native_install,r'\BnTeXNativeTraceOn\BnTeXNativeShape{কর্ম}\BnTeXNativeTraceOff\BnTeXNativeDump')
    for stage in ['normalized','syllables','initial-reorder','GSUB-','GPOS-','positioned']:assert stage in output
    actual,_=shape_runs(native_install,['কর্ম','স্বাস্থ্য','কর্ম'])
    assert actual[0]==actual[2]


@pytest.mark.parametrize('asset',['bntex-native-tables.def','bntex-native-core.def','bnf'+FONT_SHA[:16]+'.ttf'])
def test_changed_assets_fail_before_shaping(native_install,tmp_path,asset):
    target=tmp_path/'changed';shutil.copytree(native_install,target)
    p=target/asset;p.write_bytes(p.read_bytes()+b'\n% altered\n')
    output,_=run_tex(target,r'\bnNative{ক্ষ}',expect_success=False)
    assert 'asset changed' in output


def test_export_is_deterministic_and_no_vocabulary(tex_profile,tmp_path):
    a=export(tex_profile,FONT,tmp_path/'a');b=export(tex_profile,FONT,tmp_path/'b')
    assert a==b
    assert a['vocabulary'] is None
    assert a['glyph_count']==640
    assert (tmp_path/'a/bntex-native-tables.def').read_bytes().isascii()
    with pytest.raises(ValueError,match='exist'):export(tex_profile,FONT,tmp_path/'a')


@pytest.mark.parametrize('which',['profile','font'])
def test_export_pin_mismatch(tex_profile,tmp_path,which):
    p=tmp_path/'corrupt';p.write_bytes((tex_profile if which=='profile' else FONT).read_bytes()+b'x')
    with pytest.raises(ValueError):export(p if which=='profile' else tex_profile,p if which=='font' else FONT,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_export_symlink_is_rejected(tex_profile,tmp_path):
    target=tmp_path/'target';target.mkdir();link=tmp_path/'alias';link.symlink_to(target,target_is_directory=True)
    with pytest.raises(ValueError,match='Symlink'):export(tex_profile,FONT,link/'new')


def test_package_resources_identical():
    for name in MODULES:
        # Existing decoder resource remains upstream's byte-identical copy.
        assert (ROOT/'tex/latex/bntex'/name).read_bytes()==(ROOT/'src/bntex/data'/name).read_bytes()


def test_dfa_deterministic_and_closed():
    a=grammar_dfa();assert a==grammar_dfa()
    edges,accept=a
    assert edges and accept and len({s for s,_ in edges})<2048
    assert set(accept.values()) <= {0,1,2,3,4,5}


def test_runtime_has_no_helper_invocation():
    for name in MODULES:
        source=(ROOT/'tex/latex/bntex'/name).read_text()
        assert not any(token in source for token in (r'\write18',r'\directlua',r'\luaexec',r'\sys_shell'))

def test_category_membership_is_declared():
    source=''.join((ROOT/'tex/latex/bntex'/name).read_text() for name in MODULES)
    used=set(re.findall(r'\\__bn_cat(?:_p)?:nn(?:TF|T|F)?\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\{([0-9,]+)\}',source))
    for group in used:
        for category in group.split(','):
            assert '{__bn_catset_'+group+'_'+category+'}' in source
