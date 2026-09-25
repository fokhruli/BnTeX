"""Decode-once span transport; real pdfTeX and original-byte regression tests."""
from __future__ import annotations
import re
import pytest
from test_native_tex import native_install, tex_profile, hb_reference, run_tex, rows

COUNT_DECODE = r'''\ExplSyntaxOn
\int_new:N\g__test_decode_int
\cs_new_eq:NN\__test_decode:nTF\bntex_utfviii_decode:nTF
\cs_set_protected:Npn\bntex_utfviii_decode:nTF#1#2#3
 {\int_gincr:N\g__test_decode_int\__test_decode:nTF{#1}{#2}{#3}}
\ExplSyntaxOff'''
COUNT_OUTPUT = r'\ExplSyntaxOn\iow_term:x{DECODES|\int_use:N\g__test_decode_int}\ExplSyntaxOff'

@pytest.mark.parametrize('memo', [False, True])
def test_one_decode_for_multiword_span(native_install, memo):
    pre = (r'\usepackage{bntex-native-memo}' if memo else '') + COUNT_DECODE
    text, _ = run_tex(native_install,
        r'\bnNative{কর্ম প্রযুক্তি কর্ম গবেষণা}' + COUNT_OUTPUT, preamble=pre)
    assert re.findall(r'^DECODES\|(\d+)$', text, re.M) == ['1']

from pathlib import Path
import gzip
import hashlib
import json
import subprocess
from test_native_tex import need

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = r'''\ExplSyntaxOn
\cs_new_eq:NN\__test_execute:\__bn_execute:
\cs_set_protected:Npn\__bn_execute:
 {\iow_term:x{SLICE|\l_bntex_utfviii_hex_tl|\seq_use:Nn\l_bntex_utfviii_scalars_seq{,}|\seq_use:Nn\l_bntex_utfviii_offsets_seq{,}|\seq_use:Nn\l_bntex_utfviii_lengths_seq{,}}\__test_execute:}
\cs_new_eq:NN\__test_render:\__bn_render:
\cs_set_protected:Npn\__bn_render:{\BnTeXNativeDump\__test_render:}
\ExplSyntaxOff'''
TRACE_PREFIXES = ('BNTEX-STAGE|', 'BNTEX-NODE|', 'BNTEX-RUN|', 'BNTEX-GLYPH|')

def sliced(output):
    result = []
    for line in output.splitlines():
        if line.startswith('SLICE|'):
            _, hexd, scalars, offsets, lengths = line.split('|')
            result.append((hexd.lower(), *[list(map(int, x.split(','))) for x in (scalars, offsets, lengths)]))
    return result

def expected_slice(word):
    lengths = [len(ch.encode('utf8')) for ch in word]
    offsets, at = [], 0
    for n in lengths:
        offsets.append(at); at += n
    return word.encode().hex(), list(map(ord, word)), offsets, lengths

def glyph_runs(output):
    result = []
    for line in output.splitlines():
        if line.startswith('BNTEX-RUN|'):
            result.append([])
        elif line.startswith('BNTEX-GLYPH|'):
            result[-1].append(list(map(int, line.split('|')[1:])))
    return result

def raw_span(hex_string):
    # Deliberate exact-byte input: avoid source-file whitespace normalization.
    return (r'\ExplSyntaxOn\tl_set:Nx\l_tmpa_tl{\pdfunescapehex{' + hex_string +
            r'}}\exp_args:NV\bnNative\l_tmpa_tl\ExplSyntaxOff')

@pytest.mark.parametrize('words', [
    ['কর্ম', 'প্রযুক্তি', 'গবেষণা'],
    ['কো', 'কো', 'ড়', 'ড়', 'ঢ়', 'ঢ়', 'য়', 'য়'],
    ['ক্\u200dষ', 'ক্\u200cষ', 'রু', 'হৃ', 'ক্ষ্ম', 'জ্ঞ'],
    ['১২৩', '123', '।', '—', 'কর্ম।', 'তথ্য,'],
    ['অণুজীবপ্রযুক্তিগত', 'পুনর্বিন্যাসসমূহ', 'দূরনিয়ন্ত্রণযোগ্যতা'],
])
def test_exact_original_slices_and_glyphs(native_install, hb_reference, words):
    output, _ = run_tex(native_install, r'\bnNative{' + ' '.join(words) + '}', preamble=SNAPSHOT)
    assert sliced(output) == [expected_slice(w) for w in words]
    assert glyph_runs(output) == [rows(hb_reference.shape(w)) for w in words]

@pytest.mark.parametrize('text', ['', ' ', '  ', ' কর্ম', 'কর্ম ', '  কর্ম  তথ্য   ', 'কর্ম\u00a0তথ্য'])
def test_spaces_match_original_split_policy(native_install, text):
    output, _ = run_tex(native_install, raw_span(text.encode().hex()), preamble=SNAPSHOT + COUNT_DECODE)
    assert sliced(output) == [expected_slice(w) for w in text.split(' ') if w]

@pytest.mark.parametrize('words', [
    ['কো', 'কো', 'ড়', 'ড়', 'কর্ম'],
    ['ক্ষ', 'জ্ঞ', 'স্বাস্থ্য', 'ক্\u200dষ', 'ক্\u200cষ'],
    ['র্টৌঁ', 'র্শ্ম্ফ্ট্টি', 'পুনর্বিন্যাসসমূহ'],
])
def test_complete_traces_match_standalone_shape(native_install, words):
    body = r'\BnTeXNativeTraceOn\bnNative{' + ' '.join(words) + '}'
    a, _ = run_tex(native_install, body, preamble=SNAPSHOT)
    body = r'\BnTeXNativeTraceOn' + ''.join(r'\BnTeXNativeShape{' + w + r'}\BnTeXNativeDump' for w in words)
    b, _ = run_tex(native_install, body)
    assert [s for s in a.splitlines() if s.startswith(TRACE_PREFIXES)] == [s for s in b.splitlines() if s.startswith(TRACE_PREFIXES)]

@pytest.mark.parametrize('block', range(3))
def test_frozen_forms_in_multiword_transport(native_install, block):
    raw = (ROOT/'corpus/oracles/user-forms-noto-hb10.2.0.json.gz').read_bytes()
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() == '513f018036962986ac9a3663ba2496c1e1a5cbea'
    batch = json.loads(gzip.decompress(raw))['runs'][87*block:87*(block+1)]
    words = [''.join(chr(int(c,16)) for c in cid[2:].split('-')) for cid,_ in batch]
    output, _ = run_tex(native_install, r'\bnNative{'+' '.join(words)+'}', preamble=SNAPSHOT)
    assert sliced(output) == [expected_slice(w) for w in words]
    assert glyph_runs(output) == [expected for _,expected in batch]

@pytest.mark.parametrize('memo', [False, True])
def test_public_interfaces_never_use_stale_slice(native_install, memo):
    pre = (r'\usepackage{bntex-native-memo}' if memo else '') + COUNT_DECODE + SNAPSHOT
    body = (r'\bnNative{কর্ম তথ্য}\BnTeXNativeShape{প্রযুক্তি}\BnTeXNativeDump'
            r'\BnTeXNativeShapeHex{'+ 'গবেষণা'.encode().hex() + r'}\BnTeXNativeDump'
            r'\ExplSyntaxOn\__bn_typeset_word:n{বাংলা}\ExplSyntaxOff' + COUNT_OUTPUT)
    output, _ = run_tex(native_install, body, preamble=pre)
    assert sliced(output) == [expected_slice(w) for w in ['কর্ম','তথ্য','প্রযুক্তি','গবেষণা','বাংলা']]
    assert re.findall(r'^DECODES\|(\d+)$', output, re.M) == ['3'] # Hex is a separate decoder.

@pytest.mark.parametrize('text', ['কো কো কো কো', 'ড় ড় ড় ড়', 'কর্ম তথ্য কর্ম তথ্য'])
def test_memo_uses_original_keys_and_new_words(native_install, text):
    pre = r'\usepackage{bntex-native-memo}' + SNAPSHOT + COUNT_DECODE
    output, _ = run_tex(native_install, r'\bnNative{'+text+r'}\BnTeXNativeMemoStats'+COUNT_OUTPUT, preamble=pre)
    assert len(sliced(output)) == 2
    assert re.findall(r'BNTEX-MEMO\|hits=(\d+)\|misses=(\d+)\|entries=(\d+)',output) == [('2','2','2')]
    assert re.findall(r'^DECODES\|(\d+)$', output, re.M) == ['1']

@pytest.mark.parametrize('control', [r'\BnTeXNativeMemoOff', r'\BnTeXNativeTraceOn', r'\BnTeXNativeMemoLimit{1}'])
def test_memo_disabled_trace_and_eviction_still_decode_once(native_install, control):
    pre = r'\usepackage{bntex-native-memo}' + SNAPSHOT + COUNT_DECODE
    output, _ = run_tex(native_install, control + r'\bnNative{কর্ম তথ্য কর্ম}' + COUNT_OUTPUT, preamble=pre)
    assert len(sliced(output)) == 3
    assert re.findall(r'^DECODES\|(\d+)$', output, re.M) == ['1']

@pytest.mark.parametrize('bad', ['ff','c080','e0a6','eda080','f4908080','e0a620'])
def test_bad_utf8_tail_rejected_before_any_render(native_install, bad):
    # A valid earlier word must not be rendered before validation of the tail.
    pre = r'\ExplSyntaxOn\cs_set_protected:Npn\__bn_render:{\iow_term:n{ACTUAL-RENDER}}\ExplSyntaxOff'
    data = 'কর্ম '.encode().hex() + bad
    output, _ = run_tex(native_install, raw_span(data), preamble=pre, expect_success=False)
    assert not re.search(r'^ACTUAL-RENDER$',output,re.M)
    assert 'literal UTF-8 input required' in ' '.join(output.replace('(bntex-native)', '').split())

@pytest.mark.parametrize('body', [r'\bnNative{কর্ম\BOOM}', r'\bnNative{কর্ম {তথ্য}}'])
def test_input_macros_and_nested_groups_still_rejected(native_install, body):
    pre = r'\def\BOOM{\typeout{MACRO-EXECUTED}}'
    output, _ = run_tex(native_install, body, preamble=pre, expect_success=False)
    assert not re.search(r'^MACRO-EXECUTED$',output,re.M)

@pytest.mark.parametrize('n,success', [(4096,True),(4097,False)])
def test_whole_span_byte_limit_is_preserved(native_install, n, success):
    data = ('ক'.encode() + b' '*(n-3)).hex()
    output, _ = run_tex(native_install, raw_span(data), preamble=SNAPSHOT, expect_success=success)
    assert len(sliced(output)) == (1 if success else 0)

@pytest.mark.parametrize('text', ['কিা', 'ক়়', 'কঁঁ', 'A', '\U0001f600'])
def test_supported_domain_rejections_unchanged(native_install, text):
    run_tex(native_install, r'\bnNative{কর্ম '+text+'}', expect_success=False)

@pytest.mark.parametrize('memo', [False,True])
def test_grouping_and_decoder_state_restored(native_install, memo):
    pre = (r'\usepackage{bntex-native-memo}' if memo else '')
    body = r'''\ExplSyntaxOn
\bntex_utfviii_decode:nTF{abc}{}{\errmessage{unexpected}}
\tl_set:Nx\l_tmpa_tl{\seq_use:Nn\l_bntex_utfviii_scalars_seq{,}|\l_bntex_utfviii_hex_tl}
\ExplSyntaxOff
{\small\bnNative{কর্ম তথ্য}}
\ExplSyntaxOn
\tl_set:Nx\l_tmpb_tl{\seq_use:Nn\l_bntex_utfviii_scalars_seq{,}|\l_bntex_utfviii_hex_tl}
\tl_if_eq:NNF\l_tmpa_tl\l_tmpb_tl{\errmessage{decoder state leaked}}
\bool_if:NT\l__bn_word_decoded_bool{\errmessage{slice flag leaked}}
\ExplSyntaxOff
\bnNative{প্রযুক্তি}'''
    run_tex(native_install, body, preamble=pre)

def test_resource_copies_match():
    for name in ['bntex-native.sty','bntex-native-memo.sty']:
        assert (ROOT/'tex/latex/bntex'/name).read_bytes() == (ROOT/'src/bntex/data'/name).read_bytes()
