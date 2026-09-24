"""Exercise the actual expl3 decoder, not a Python implementation of its DFA.

Python's strict UTF-8 codec is the independent encoding oracle. HarfBuzz, fonts,
network and shell helpers are not used by the decoder compilation tests.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import random
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / 'tex' / 'latex' / 'bntex'
MAX_BYTES = 4096
pytestmark = pytest.mark.integration

PREAMBLE = rb'''\documentclass{article}
\usepackage{bntex-utf8}
\newwrite\results
\immediate\openout\results=results.txt
\newcommand\Emit[2]{\immediate\write\results{#1|#2|\BnTeXUTFviiiHex|\BnTeXUTFviiiScalars|\BnTeXUTFviiiOffsets|\BnTeXUTFviiiLengths|\BnTeXUTFviiiError|\BnTeXUTFviiiErrorOffset|\BnTeXUTFviiiErrorStart}}
\ifnum\pdfshellescape=0\else\errmessage{Shell access was not disabled}\fi
\begin{document}
'''


@pytest.fixture(scope='module')
def pdftex_engine():
    engine = shutil.which('pdflatex')
    if engine is None:
        if os.environ.get('BNTEX_REQUIRE_INTEGRATION') == '1':
            pytest.fail('UTF-8 gate requires pdflatex.')
        pytest.skip('Install pdfLaTeX for actual TeX decoder tests.')
    return str(Path(engine).absolute())


def compile_tex(directory, engine, body, *, expected_rc=0, preamble=PREAMBLE):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'input.tex').write_bytes(preamble + body + b'\n\\end{document}\n')
    empty_bin = directory / 'empty-bin'
    empty_bin.mkdir(exist_ok=True)
    env = dict(os.environ, TEXINPUTS=str(TEX) + os.pathsep,
               PATH=str(empty_bin), openout_any='p')
    # The absolute engine path remains usable, but no external helper is on PATH.
    result = subprocess.run(
        [engine, '-no-shell-escape', '-halt-on-error', '-interaction=nonstopmode',
         '-recorder', 'input.tex'], cwd=directory, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    log = result.stdout.decode('utf-8', errors='replace')
    assert (result.returncode == 0) == (expected_rc == 0), log[-6000:]
    if expected_rc == 0:
        assert 'Undefined control sequence' not in log
        assert 'Runaway argument' not in log
        # No word-cache or font-profile input is needed for decoding.
        fls = (directory / 'input.fls').read_text(errors='replace')
        assert 'bntex-cache' not in fls
    return log


def run_cases(directory, engine, inputs, *, mode='hex', extra=b''):
    commands = []
    for i, raw in enumerate(inputs):
        content = raw.hex().encode('ascii') if mode == 'hex' else raw
        name = b'\\BnTeXDecodeUTFviiiHex' if mode == 'hex' else b'\\BnTeXDecodeUTFviii'
        commands.append(name + b'{' + content + b'}{\\Emit{' + str(i).encode() +
                        b'}{ok}}{\\Emit{' + str(i).encode() + b'}{error}}')
    compile_tex(directory, engine, extra + b'\n'.join(commands))
    rows = [line.split('|') for line in (directory / 'results.txt').read_text().splitlines()]
    assert len(rows) == len(inputs)
    for i, row in enumerate(rows):
        assert len(row) == 9
        assert row[0] == str(i)
    return rows


def integers(field):
    return [int(n) for n in field.split(',')] if field else []


def assert_codec_parity(raw, row):
    assert row[2] == raw.hex().upper()  # Complete original bytes, including failures.
    try:
        text = raw.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        assert row[1] == 'error'
        assert row[3:6] == ['', '', '']  # Never expose a valid prefix as success.
        assert row[6]
        assert 0 <= int(row[8]) <= int(row[7]) <= len(raw)
        return
    assert row[1] == 'ok', (raw, row)
    assert row[6:] == ['', '-1', '-1']
    scalars, offsets, widths = map(integers, row[3:6])
    assert scalars == list(map(ord, text))
    expected_offsets, position = [], 0
    for char in text:
        expected_offsets.append(position)
        position += len(char.encode('utf-8'))
    assert offsets == expected_offsets
    assert widths == [len(char.encode('utf-8')) for char in text]
    assert ''.join(map(chr, scalars)).encode('utf-8') == raw
    assert sum(widths) == len(raw)


def test_all_single_bytes(tmp_path, pdftex_engine):
    data = [bytes([b]) for b in range(256)]
    for raw, row in zip(data, run_cases(tmp_path, pdftex_engine, data)):
        assert_codec_parity(raw, row)


@pytest.mark.parametrize('lead', range(0xC2, 0xE0))
def test_all_valid_two_byte_encodings(tmp_path, pdftex_engine, lead):
    data = [bytes([lead, tail]) for tail in range(0x80, 0xC0)]
    for raw, row in zip(data, run_cases(tmp_path, pdftex_engine, data)):
        assert_codec_parity(raw, row)


@pytest.mark.parametrize('lead,width', [(0xE0, 3), (0xE1, 3), (0xED, 3),
                                      (0xEF, 3), (0xF0, 4), (0xF1, 4), (0xF4, 4)])
def test_all_second_bytes_at_range_boundaries(tmp_path, pdftex_engine, lead, width):
    data = [b'A' + bytes([lead, b] + [0x80] * (width - 2)) for b in range(256)]
    for raw, row in zip(data, run_cases(tmp_path, pdftex_engine, data)):
        assert_codec_parity(raw, row)


@pytest.mark.parametrize('prefix,suffix', [(b'\xe1\x80', b''),
                        (b'\xf1\x80', b'\x80'), (b'\xf1\x80\x80', b'')])
def test_all_later_continuation_bytes(tmp_path, pdftex_engine, prefix, suffix):
    data = [prefix + bytes([b]) + suffix for b in range(256)]
    for raw, row in zip(data, run_cases(tmp_path, pdftex_engine, data)):
        assert_codec_parity(raw, row)


@pytest.mark.parametrize('raw,code,offset,start', [
    (b'\x80', 'stray-continuation', 0, 0),
    (b'\xc0\xaf', 'overlong', 0, 0),
    (b'\xc1\xbf', 'overlong', 0, 0),
    (b'A\xe0\x80\x80', 'overlong', 2, 1),
    (b'\xf0\x80\x80\x80', 'overlong', 1, 0),
    (b'\xed\xa0\x80', 'surrogate', 1, 0),
    (b'\xf4\x90\x80\x80', 'out-of-range', 1, 0),
    (b'\xf5\x80\x80\x80', 'out-of-range', 0, 0),
    (b'\xf8\x88\x80\x80\x80', 'invalid-lead', 0, 0),
    (b'\xff', 'invalid-lead', 0, 0),
    (b'A\xe0A\x95', 'bad-continuation', 2, 1),
    (b'\xe0\xa6', 'truncated', 2, 0),
    (b'A\xf0\x90\x80', 'truncated', 4, 1),
    ('ক'.encode() + b'\xe0', 'truncated', 4, 3),
    (b'A\x80\xff', 'stray-continuation', 1, 1),
])
def test_safe_first_error_and_atomic_failure(tmp_path, pdftex_engine, raw, code, offset, start):
    data = [b'A', raw, 'ক্ষ'.encode()]
    rows = run_cases(tmp_path, pdftex_engine, data)
    for original, row in zip(data, rows):
        assert_codec_parity(original, row)
    assert rows[1][6:] == [code, str(offset), str(start)]


def test_unicode_extremes_noncharacters_and_empty_are_encoding_valid(tmp_path, pdftex_engine):
    scalars = [0, 0x7F, 0x80, 0x7FF, 0x800, 0xD7FF, 0xE000, 0xFDD0,
               0xFEFF, 0xFFFE, 0xFFFF, 0x10000, 0x10FFFE, 0x10FFFF]
    data = [b''] + [chr(n).encode() for n in scalars]
    for raw, row in zip(data, run_cases(tmp_path, pdftex_engine, data)):
        assert_codec_parity(raw, row)


def test_all_bengali_block_scalars_as_literal_input(tmp_path, pdftex_engine):
    # Assignment/font coverage is a later concern; every scalar is valid UTF-8.
    data = [chr(n).encode() for n in range(0x0980, 0x0A00)]
    for raw, row in zip(data, run_cases(tmp_path, pdftex_engine, data, mode='literal')):
        assert_codec_parity(raw, row)


def inventory_strings():
    inv = json.loads((ROOT / 'corpus/inventories/user-alphabet-v1.json').read_text())
    forms = set(inv['digits'])
    for row in inv['vowels']:
        forms.update(x for x in row if x is not None)
    for key in ('consonant_groups', 'conjunct_groups'):
        for _, text in inv[key]:
            forms.update(text.split())
    for _, fragment, _, samples, words in inv['attached_forms']:
        forms.add(fragment)
        forms.update(samples.split())
        forms.update(words.split())
    forms.update(inv['tricky_forms'].split())
    forms.update(inv['irregular_vowels'].split())
    return sorted(forms)


def test_complete_user_inventory_literal_and_hex_agree(tmp_path, pdftex_engine):
    forms = inventory_strings()
    assert len(forms) == 261
    data = [s.encode() for s in forms]
    literal = run_cases(tmp_path / 'literal', pdftex_engine, data, mode='literal')
    hexrows = run_cases(tmp_path / 'hex', pdftex_engine, data)
    assert literal == hexrows
    for raw, row in zip(data, literal):
        assert_codec_parity(raw, row)


def test_join_controls_and_canonical_encodings_are_not_normalized(tmp_path, pdftex_engine):
    data = [s.encode() for s in ['ড়', 'ড়', 'ঢ়', 'ঢ়', 'য়', 'য়', 'কো', 'কো',
            'কৌ', 'কৌ', 'ক্\u200dষ', 'ক্\u200cষ', 'র্\u200dক', 'ত্\u200d',
            ' Latin বাংলা 😀 é ', 'বাংলা\u00a0ভাষা', '\ufeffক']]
    for raw, row in zip(data, run_cases(tmp_path, pdftex_engine, data, mode='literal')):
        assert_codec_parity(raw, row)


def test_deterministic_random_codec_differential(tmp_path, pdftex_engine):
    rng = random.Random(24092026)
    data = [bytes(rng.randrange(256) for _ in range(rng.randrange(1, 12))) for _ in range(384)]
    for _ in range(128):
        numbers = [rng.randrange(0x110000) for _ in range(rng.randrange(1, 12))]
        text = ''.join(chr(n) for n in numbers if not 0xD800 <= n <= 0xDFFF)
        data.append(text.encode())
    for raw, row in zip(data, run_cases(tmp_path, pdftex_engine, data)):
        assert_codec_parity(raw, row)


@pytest.mark.parametrize('tokens,offset', [
    (rb'\boom', 0), (rb'\undefinedcommand', 0), (rb'A{B}', 1),
    (rb'A$B', 1), (rb'A&B', 1), (rb'A#B', 1), (rb'A^B', 1),
    (rb'A_B', 1), (rb'A~B', 1), (rb'\char65', 0), (rb'\string\boom', 0),
    ('ক'.encode() + rb'\boom', 3),
])
def test_literal_rejects_tex_tokens_without_executing_them(tmp_path, pdftex_engine, tokens, offset):
    extra = rb'\def\boom{\errmessage{INPUT WAS EXPANDED}}' + b'\n'
    row = run_cases(tmp_path, pdftex_engine, [tokens], mode='literal', extra=extra)[0]
    assert row[1:] == ['error', '', '', '', '', 'non-literal', str(offset), str(offset)]


def test_active_high_bytes_are_data_not_expanded(tmp_path, pdftex_engine):
    extra = rb'\def^^e0{\errmessage{ACTIVE BYTE WAS EXPANDED}}' + b'\n'
    data = ['ক্ষ'.encode(), b'\xe0\xa6']
    for raw, row in zip(data, run_cases(tmp_path, pdftex_engine, data, mode='literal', extra=extra)):
        assert_codec_parity(raw, row)


@pytest.mark.parametrize('hexsource', [b'0', b'4G', b'41 42', b'41{42}',
                                      rb'\boom', b'e0a6X5', b'0x41'])
def test_hex_syntax_is_strict_and_failure_discards_partial_bytes(tmp_path, pdftex_engine, hexsource):
    body = rb'\def\boom{\errmessage{INPUT WAS EXPANDED}}' + b'\n'
    body += b'\\BnTeXDecodeUTFviiiHex{' + hexsource + b'}{\\Emit{0}{ok}}{\\Emit{0}{error}}'
    compile_tex(tmp_path, pdftex_engine, body)
    row = (tmp_path / 'results.txt').read_text().strip().split('|')
    assert row[1:7] == ['error', '', '', '', '', 'hex-syntax']


def test_mixed_case_hex_is_accepted_and_emits_canonical_byte_hex(tmp_path, pdftex_engine):
    compile_tex(tmp_path, pdftex_engine,
                rb'\BnTeXDecodeUTFviiiHex{E0a695}{\Emit{0}{ok}}{\Emit{0}{error}}')
    row = (tmp_path / 'results.txt').read_text().strip().split('|')
    assert_codec_parity('ক'.encode(), row)


def test_grouping_restores_the_callers_result(tmp_path, pdftex_engine):
    body = rb'''\BnTeXDecodeUTFviiiHex{41}{\Emit{0}{ok}}{\Emit{0}{error}}
{\BnTeXDecodeUTFviiiHex{80}{\Emit{1}{ok}}{\Emit{1}{error}}}
\Emit{2}{ok}
'''
    compile_tex(tmp_path, pdftex_engine, body)
    rows = [s.split('|') for s in (tmp_path / 'results.txt').read_text().splitlines()]
    assert_codec_parity(b'A', rows[0])
    assert_codec_parity(b'\x80', rows[1])
    assert rows[0][1:] == rows[2][1:]


@pytest.mark.parametrize('mode', ['literal', 'hex'])
def test_exact_resource_limit_and_one_byte_over(tmp_path, pdftex_engine, mode):
    data = [b'A' * MAX_BYTES, b'A' * (MAX_BYTES + 1), b'A']
    rows = run_cases(tmp_path, pdftex_engine, data, mode=mode)
    assert_codec_parity(data[0], rows[0])
    assert rows[1][1:] == ['error', '', '', '', '', 'input-too-long', '-1', '-1']
    assert_codec_parity(data[2], rows[2])


def test_require_wrapper_fails_with_numeric_diagnostic(tmp_path, pdftex_engine):
    log = compile_tex(tmp_path, pdftex_engine,
                      b'\\BnTeXRequireUTFviii{A\xed\xa0\x80}', expected_rc=1)
    normalized = ' '.join(log.replace('(bntex-utf8)', '').split())
    assert 'surrogate;' in normalized and 'byte 2;' in normalized and 'sequence start 1' in normalized
    assert 'Undefined control sequence' not in log


def test_loading_does_not_change_bn_or_global_input_catcodes(tmp_path, pdftex_engine):
    preamble = rb'''\documentclass{article}
\usepackage{bntex}
\let\oldbn\bn
\edef\oldcat{\the\catcode224}
\usepackage{bntex-utf8}
\ifx\oldbn\bn\else\errmessage{bn was changed}\fi
\edef\newcat{\the\catcode224}
\ifx\oldcat\newcat\else\errmessage{UTF8 catcode was changed}\fi
\begin{document}
'''
    compile_tex(tmp_path, pdftex_engine,
                'English text. \\BnTeXRequireUTFviii{বাংলা} More English.'.encode(), preamble=preamble)


def test_direct_def_api(tmp_path, pdftex_engine):
    preamble = rb'''\documentclass{article}
\usepackage{expl3}
\input{bntex-utf8.def}
\begin{document}
\ExplSyntaxOn
'''
    compile_tex(tmp_path, pdftex_engine, rb'''
\bntex_utfviii_decode_hex:nTF {E0A695E0A78DE0A6B7}
  {\str_if_eq:eeF {\seq_use:Nn \l_bntex_utfviii_offsets_seq {,}} {0,3,6}
     {\errmessage{Direct API offsets wrong}}}
  {\errmessage{Direct API failed}}
\ExplSyntaxOff
''', preamble=preamble)


def test_wheel_resources_match_authoritative_modules():
    # No font requirement; the integration marker only controls suite grouping.
    for name in ('bntex-utf8.sty', 'bntex-utf8.def'):
        assert (TEX / name).read_bytes() == (ROOT / 'src/bntex/data' / name).read_bytes()
    assert '"data/*.def"' in (ROOT / 'pyproject.toml').read_text()


def test_tex_mouth_whitespace_vs_exact_hex_transport(tmp_path, pdftex_engine):
    raw = b'A  B'
    literal = run_cases(tmp_path / 'literal', pdftex_engine, [raw], mode='literal')[0]
    assert_codec_parity(b'A B', literal)  # TeX has already collapsed two spaces.
    hexrow = run_cases(tmp_path / 'hex', pdftex_engine, [raw])[0]
    assert_codec_parity(raw, hexrow)      # Byte transport has not.


def test_repeated_package_loading_is_idempotent(tmp_path, pdftex_engine):
    compile_tex(tmp_path, pdftex_engine, rb'\BnTeXRequireUTFviii{A}',
                preamble=PREAMBLE.replace(rb'\begin{document}',
                         rb'\usepackage{bntex-utf8}\begin{document}'))


def test_wrong_engine_rejected_before_byte_decoding(tmp_path):
    engine = shutil.which('lualatex')
    if not engine:
        if os.environ.get('BNTEX_REQUIRE_INTEGRATION') == '1':
            pytest.fail('Wrong-engine regression requires lualatex.')
        pytest.skip('Install LuaLaTeX to test the unsupported-engine diagnostic.')
    log = compile_tex(tmp_path, str(Path(engine).absolute()), b'', expected_rc=1,
                      preamble=rb'\RequirePackage{bntex-utf8}' + b'\n')
    assert 'requires pdfTeX' in log


def test_all_truncated_prefix_lengths(tmp_path, pdftex_engine):
    complete = [b'\xc2\x80', b'\xdf\xbf', b'\xe0\xa0\x80', b'\xed\x9f\xbf',
                b'\xf0\x90\x80\x80', b'\xf4\x8f\xbf\xbf']
    data = [b'A' + c[:i] for c in complete for i in range(1, len(c))]
    for raw, row in zip(data, run_cases(tmp_path, pdftex_engine, data)):
        assert_codec_parity(raw, row)
        assert row[6:] == ['truncated', str(len(raw)), '1']


def test_direct_module_then_wrapper_loads_once(tmp_path, pdftex_engine):
    preamble = PREAMBLE.replace(rb'\usepackage{bntex-utf8}',
                  rb'\RequirePackage{expl3}\input{bntex-utf8.def}\usepackage{bntex-utf8}')
    compile_tex(tmp_path, pdftex_engine, rb'\BnTeXRequireUTFviii{A}', preamble=preamble)


def test_callback_paragraphs_are_supported(tmp_path, pdftex_engine):
    compile_tex(tmp_path, pdftex_engine, rb'''\BnTeXDecodeUTFviii{A}
  {First paragraph.\par Second paragraph.}{\errmessage{Unexpected failure}}
\BnTeXDecodeUTFviiiHex{80}{\errmessage{Unexpected success}}
  {Failure paragraph.\par Still controlled.}
''')


def test_literal_paragraph_is_a_controlled_nonliteral_failure(tmp_path, pdftex_engine):
    row = run_cases(tmp_path, pdftex_engine, [rb'A\par B'], mode='literal')[0]
    assert row[1:7] == ['error', '', '', '', '', 'non-literal']
