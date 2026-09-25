"""First-use optimizations must preserve native output without a word cache.

The dense reordering functions and activity-disabled root scans are executable
controls. Frozen typography expectations remain in the inherited test suite.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import random
import re

import pytest
from bntex.tex_export import emit_tables, entry_glyphs
from test_native_tex import (
    tex_profile, native_install, hb_reference, run_tex, rows, CONJUNCTS, MATRAS,
)

ROOT = Path(__file__).resolve().parents[1]
DENSE = r'''\ExplSyntaxOn
\cs_undefine:N\__bnp_activity_abi
\cs_set_eq:NN\__bn_initial_range_args:nn\__bn_initial_range_dense:nn
\cs_set_eq:NN\__bn_final_range_args:nn\__bn_final_range_dense:nn
\ExplSyntaxOff'''
TRACE_PREFIXES = ('WORD|', 'BNTEX-STAGE|', 'BNTEX-NODE|', 'BNTEX-RUN|', 'BNTEX-GLYPH|')


def traced_words(directory, words, preamble=''):
    body = r'\BnTeXNativeTraceOn' + '\n' + '\n'.join(
        r'\typeout{WORD|' + str(i) + r'}\BnTeXNativeShape{' + text + r'}\BnTeXNativeDump'
        for i, text in enumerate(words))
    output, _ = run_tex(directory, body, preamble=preamble)
    return [line for line in output.splitlines() if line.startswith(TRACE_PREFIXES)]


def test_activation_index_is_exact_reverse_coverage(tex_profile):
    profile = json.loads(tex_profile.read_text())
    data = emit_tables(profile).decode('ascii')
    assert r'\cs_gset:cpn {__bnp_activity_abi}{1}' in data
    declarations = re.findall(r'^\\cs_gset:cpn \{__bnp_activate_(\d+)\}\{(.*)\}$', data, re.M)
    assert len(declarations) == profile['glyph_count'] == 640
    assert len(dict(declarations)) == len(declarations)
    for glyph, commands in declarations:
        expected = []
        for table, letter in [('gsub', 's'), ('gpos', 'p')]:
            for lookup in profile[table]:
                if any(int(glyph) in entry_glyphs(st) for st in lookup['subtables']):
                    expected.append((letter, str(lookup['index'])))
        actual = re.findall(r'\\cs_gset_eq:cN\{__bn_active_([sp])_(\d+)\}\\g__bn_activity_stamp_tl', commands)
        assert actual == expected
        assert commands == ''.join(r'\cs_gset_eq:cN{__bn_active_' + t + '_' + i +
                                   r'}\g__bn_activity_stamp_tl' for t, i in expected)
    assert any(not st['actions'] for lookup in profile['gsub']
               for st in lookup['subtables'] if st['kind'] == 'chain')


def test_added_activation_data_does_not_change_existing_rules(tex_profile):
    raw = emit_tables(json.loads(tex_profile.read_text()))
    extra = re.compile(rb'\\cs_gset:cpn \{__bnp_(?:activity_abi|activate_\d+)\}')
    old_dispatch_tables = b''.join(line for line in raw.splitlines(keepends=True) if not extra.match(line))
    # Exact pre-change indexed tables, not a reference regenerated from new code.
    assert hashlib.sha256(old_dispatch_tables).hexdigest() == '1f6c6135dec97b3260deee6826508b9688d20c16257437f3e6582af7221df78d'


@pytest.mark.parametrize('words', [
    ['ক', 'খ', 'গ', 'র', 'অ', 'আ', 'ৎ', '০', '১'],
    ['কা', 'কি', 'কী', 'কু', 'কূ', 'কৃ', 'কে', 'কৈ', 'কো', 'কৌ'],
    ['ক্', 'ক়', 'কঁ', 'কং', 'কঃ', 'কাঁ', 'শু', 'রু', 'হৃ'],
    ['ক্ষ', 'জ্ঞ', 'কর্ম', 'স্বাস্থ্য', 'র্শ্ম্ফ্ট্টি', 'র্টৌঁ'],
    ['কো', 'কো', 'ড়', 'ড়', 'ক্\u200dষ', 'ক্\u200cষ', 'অ্যা'],
    ['পুনর্বিন্যাসসমূহ', 'অণুজীবপ্রযুক্তিগত', 'শিক্ষকসম্মেলনের', 'দূরনিয়ন্ত্রণযোগ্যতা'],
])
def test_optimized_and_dense_complete_stage_traces(native_install, words):
    assert traced_words(native_install, words) == traced_words(native_install, words, DENSE)


@pytest.mark.parametrize('seed', [719, 1037])
def test_generated_conjunct_traces_match_dense(native_install, seed):
    rng = random.Random(seed)
    words = [rng.choice(CONJUNCTS) + rng.choice(MATRAS) for _ in range(32)]
    assert traced_words(native_install, words) == traced_words(native_install, words, DENSE)


def test_simple_shortcut_is_actually_exercised(native_install):
    # Make the dense initial/final routines reject. A one-base syllable and a
    # base with one sign must actually take the guarded paths, not merely pass
    # because the fast-path category set was accidentally left undeclared.
    pre = r'''\ExplSyntaxOn
\cs_set_protected:Npn\__bn_initial_range_dense:nn#1#2{\errmessage{unexpected dense initial}}
\ExplSyntaxOff'''
    run_tex(native_install, r'\BnTeXNativeShape{ক}\BnTeXNativeShape{কি}\BnTeXNativeShape{কী}', preamble=pre)
    pre = r'''\ExplSyntaxOn
\cs_set_protected:Npn\__bn_final_range_dense:nn#1#2{\errmessage{unexpected dense final}}
\ExplSyntaxOff'''
    run_tex(native_install, r'\BnTeXNativeShape{ক}', preamble=pre)


def test_complex_clusters_retain_dense_reordering(native_install):
    pre = r'''\ExplSyntaxOn
\cs_new_eq:NN\__test_initial_dense:nn\__bn_initial_range_dense:nn
\cs_set_protected:Npn\__bn_initial_range_dense:nn#1#2
 {\iow_term:n{USED-DENSE}\__test_initial_dense:nn{#1}{#2}}
\ExplSyntaxOff'''
    text, _ = run_tex(native_install, r'\BnTeXNativeShape{ক্‍ষ}', preamble=pre)
    assert 'USED-DENSE' in text


def test_epoch_is_per_shape_not_a_word_cache(native_install, hb_reference):
    words = ['প্রযুক্তি', 'গবেষণা', 'অণুজীবপ্রযুক্তিগত', 'প্রযুক্তি']
    body = []
    for word in words:
        body.append(r'\bnNative{' + word + r'}\BnTeXNativeDump'
                    r'\ExplSyntaxOn\iow_term:x{EPOCH|\int_use:N\g__bn_activity_epoch_int}\ExplSyntaxOff')
    output, _ = run_tex(native_install, '\n'.join(body))
    assert list(map(int, re.findall(r'^EPOCH\|(\d+)$', output, re.M))) == [1, 2, 3, 4]
    actual = []
    for line in output.splitlines():
        if line.startswith('BNTEX-RUN|'):
            actual.append([])
        if line.startswith('BNTEX-GLYPH|'):
            actual[-1].append(list(map(int, line.split('|')[1:])))
    assert actual == [rows(hb_reference.shape(w)) for w in words]


def test_gid_stores_activate_new_lookups_monotonically_and_reset(native_install, tex_profile):
    p = json.loads(tex_profile.read_text())
    # Two glyphs with different entry memberships, selected from the actual
    # profile rather than relying on magic glyph numbers or example vocabulary.
    coverage = {l['index']: set(g for st in l['subtables'] for g in entry_glyphs(st)) for l in p['gsub']}
    lid, cov = next((i, c) for i, c in coverage.items() if c and len(c) < p['glyph_count'])
    glyph = min(cov)
    other = next(g for g in range(p['glyph_count']) if g not in cov)
    body = r'''\ExplSyntaxOn
\__bn_activity_reset:
\__bn_setid:nnn{1}{gid}{GLYPH}
\__bn_lookup_active:nnTF{s}{LOOKUP}{\iow_term:n{ACTIVE-A}}{\errmessage{missing activation}}
\__bn_setid:nnn{1}{gid}{OTHER}
\__bn_lookup_active:nnTF{s}{LOOKUP}{\iow_term:n{ACTIVE-B}}{\errmessage{activation lost}}
\int_gset:Nn\g__bn_allocated_int{1}\__bn_clone:n{1}
\__bn_activity_reset:
\__bn_lookup_active:nnTF{s}{LOOKUP}{\errmessage{stale run}}{\iow_term:n{CLEARED}}
\ExplSyntaxOff'''.replace('GLYPH', str(glyph)).replace('OTHER', str(other)).replace('LOOKUP', str(lid))
    output, _ = run_tex(native_install, body)
    assert all(s in output for s in ['ACTIVE-A', 'ACTIVE-B', 'CLEARED'])


def test_epoch_wrap_clears_stale_stamps(native_install):
    body = r'''\ExplSyntaxOn
\int_gset:Nn\g__bn_activity_epoch_int{1000000000}
\tl_gset:Nn\g__bn_activity_stamp_tl{1}
\cs_gset_eq:cN{__bn_seen_glyph_40}\g__bn_activity_stamp_tl
\cs_gset_eq:cN{__bn_active_s_18}\g__bn_activity_stamp_tl
\cs_gset_eq:cN{__bn_active_p_0}\g__bn_activity_stamp_tl
\__bn_activity_reset:
\int_compare:nNnF{\g__bn_activity_epoch_int}={1}{\errmessage{epoch wrap}}
\cs_if_exist:cT{__bn_seen_glyph_40}{\errmessage{stale glyph}}
\__bn_lookup_active:nnTF{s}{18}{\errmessage{stale lookup}}{\iow_term:n{WRAP-OK}}
\__bn_lookup_active:nnTF{p}{0}{\errmessage{stale position}}{}
\ExplSyntaxOff'''
    output, _ = run_tex(native_install, body)
    assert 'WRAP-OK' in output


def test_old_profiles_use_dense_root_scans(native_install):
    body = r'''\ExplSyntaxOn
\cs_undefine:N\__bnp_activity_abi
\__bn_activity_reset:
\__bn_lookup_active:nnTF{s}{18}{\iow_term:n{GSUB-LEGACY}}{\errmessage{wrong fallback}}
\__bn_lookup_active:nnTF{p}{0}{\iow_term:n{GPOS-LEGACY}}{\errmessage{wrong fallback}}
\ExplSyntaxOff\BnTeXNativeShape{প্রযুক্তি}\BnTeXNativeDump'''
    output, _ = run_tex(native_install, body)
    assert 'GSUB-LEGACY' in output and 'GPOS-LEGACY' in output


@pytest.mark.parametrize('table', ['s', 'p'])
@pytest.mark.parametrize('count', [0, 1, 97, 8192])
def test_skipped_scan_charges_work_and_preserves_terminal_state(native_install, table, count):
    body = r'''\ExplSyntaxOn
\int_gset:Nn\g__bn_count_int{COUNT}
\int_gset:Nn\g__bn_ops_int{100}
\int_gset:Nn\g__bn_next_int{999}
\bool_gset_true:N\g__bn_success_bool
\__bn_skip_pass:n{TABLE}
\iow_term:x{RESULT|\int_use:N\g__bn_ops_int|\int_use:N\g__bn_next_int|\bool_if:NTF\g__bn_success_bool{1}{0}}
\ExplSyntaxOff'''.replace('COUNT', str(count)).replace('TABLE', table)
    output, _ = run_tex(native_install, body)
    expected = f'RESULT|{100+count}|{count if count else 999}|{0 if table=="s" and count else 1}'
    assert expected in output


def test_skipped_scan_cannot_bypass_operation_limit(native_install):
    body = r'''\ExplSyntaxOn
\int_gset:Nn\g__bn_count_int{2}\int_gset:Nn\g__bn_ops_int{1999999}
\__bn_skip_pass:n{s}\ExplSyntaxOff'''
    output, _ = run_tex(native_install, body, expect_success=False)
    assert re.search(r'operation\s+(?:\(bntex-native\)\s+)?budget exceeded', output)


DECODE = r'''\ExplSyntaxOn
\cs_new_protected:Npn\__test_decode_report:
 {\iow_term:x{D|\tl_use:N\l_bntex_utfviii_hex_tl|\seq_use:Nn\l_bntex_utfviii_scalars_seq{,}|\seq_use:Nn\l_bntex_utfviii_offsets_seq{,}|\seq_use:Nn\l_bntex_utfviii_lengths_seq{,}|\str_use:N\l_bntex_utfviii_error_str|\int_use:N\l_bntex_utfviii_error_offset_int|\int_use:N\l_bntex_utfviii_error_start_int}}
\cs_new_protected:Npn\__test_literal:n#1
 {\bntex_utfviii_decode:nTF{#1}{}{}\__test_decode_report:}
\cs_new_protected:Npn\__test_hex:n#1
 {\bntex_utfviii_decode_hex:nTF{#1}{}{}\__test_decode_report:}
\ExplSyntaxOff'''


@pytest.mark.parametrize('mode', ['single-octets', 'valid-sequences', 'malformed-sequences'])
def test_literal_primitive_and_exact_hex_have_identical_decoder_results(native_install, mode):
    if mode == 'single-octets':
        samples = [bytes([i]) for i in range(256)]
    elif mode == 'valid-sequences':
        points = [0, 31, 32, 65, 127, 128, 255, 2047, 2048, 0x995, 0x200c, 0x200d,
                  0xd7ff, 0xe000, 0xffff, 0x10000, 0x10ffff]
        samples = [chr(i).encode('utf-8') for i in points]
        samples += [s.encode() for s in ['কো', 'কো', 'ড়', 'ড়', 'ক্\u200dষ', 'ক্\u200cষ', 'বাংলা text']]
    else:
        samples = [bytes.fromhex(s) for s in ['c0af','c180','e08080','eda080','f0808080',
                    'f4908080','f880808080','c2','e0a6','f09080','c241','e0a641','f0908041','61e0a6']]
    body = r'\ExplSyntaxOn' + '\n'
    for raw in samples:
        # Build byte tokens without source-file newline/NUL processing. Catcode
        # 12 is allowed by the literal contract; no input macro is expanded by
        # the decoder itself. The exact hex interface is the control path.
        tokens = ''.join(r'\char_generate:nn{' + str(b) + r'}{12}' for b in raw)
        body += r'\exp_args:Ne\__test_literal:n{' + tokens + '}\n'
        body += r'\__test_hex:n{' + raw.hex() + '}\n'
    body += r'\ExplSyntaxOff'
    output, _ = run_tex(native_install, body, preamble=DECODE)
    records = [l for l in output.splitlines() if l.startswith('D|')]
    assert len(records) == 2 * len(samples)
    for a, b in zip(records[::2], records[1::2]):
        assert a == b


def test_literal_macros_and_active_ascii_are_not_expanded(native_install):
    pre = DECODE + r'''\def\Danger{\errmessage{EXPANDED}}
\begingroup\catcode`!=13\gdef!{\errmessage{EXPANDED}}\endgroup'''
    body = r'''\ExplSyntaxOn
\__test_literal:n{ক\Danger}
\group_begin:\char_set_catcode_active:N!\__test_literal:n{ক!}\group_end:
\ExplSyntaxOff'''
    output, _ = run_tex(native_install, body, preamble=pre)
    records = [l for l in output.splitlines() if l.startswith('D|')]
    assert len(records) == 2 and all('|non-literal|3|3' in r for r in records)
    assert 'EXPANDED' not in output


def test_source_resource_identity():
    names = ['bntex-native-core.def','bntex-native-sub.def','bntex-native-position.def',
             'bntex-native-reorder.def','bntex-native.sty','bntex-utf8.def']
    for name in names:
        assert (ROOT/'tex/latex/bntex'/name).read_bytes() == (ROOT/'src/bntex/data'/name).read_bytes()
