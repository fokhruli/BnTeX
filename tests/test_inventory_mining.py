from pathlib import Path
from dataclasses import replace
import bz2
import gzip
import hashlib
import json
import lzma
import os
import unicodedata
import pytest
from fontTools import __version__ as fonttools_version
from bntex import harfbuzz as adapter
from bntex.harfbuzz import HarfBuzz
from bntex.corpus import check, load_corpus, load_oracle, review_template, serialize
from bntex.inventory import coverage, load_inventory, main as inventory_main, make_corpus, requirements, unpack_oracle
from bntex.mining import Limits, chain_spans, main as mining_main, mine

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / 'corpus/inventories/user-alphabet-v1.json'
FROZEN = ROOT / 'corpus/oracles/user-forms-noto-hb10.2.0.json.gz'
ORACLE_SHA = '9466f84a8117d992b034392ba4992e1d745e31c67561160153e67cb49753782f'
BASELINE_SHA = 'd5276972853fca2e76990b9497dc7c4d7a9131297ede0237036c667639f3af5a'


@pytest.fixture
def expanded(tmp_path):
    c = tmp_path / 'forms.json'; c.write_bytes(serialize(make_corpus(INV)))
    o = tmp_path / 'oracle.json'; o.write_bytes(unpack_oracle(FROZEN))
    return c, o


def test_inventory_counts_and_exact_membership():
    data, _ = load_inventory(INV)
    assert len(data['vowels']) == 11
    assert sum(len(g.split()) for _, g in data['consonant_groups']) == 39
    conjuncts = [x for _, g in data['conjunct_groups'] for x in g.split()]
    assert len(conjuncts) == len(set(conjuncts)) == 146
    assert len(data['irregular_vowels'].split()) == 9
    assert len(data['attached_forms']) == 7
    assert len(set(r['text'] for r in requirements(data))) == 261
    assert {'হ্ম','ঞ্জ','ঙ্গ','ষ্ণ','চ্ছ্ব','ঙ্ক্ষ','হৃ','স্তু'} <= set(conjuncts + data['irregular_vowels'].split())


def test_original_baseline_is_not_rewritten():
    assert hashlib.sha256((ROOT / 'corpus/bengali-v1.json').read_bytes()).hexdigest() == BASELINE_SHA


def test_standalone_coverage_is_not_embedded_coverage():
    report = coverage(INV, [ROOT / 'corpus/bengali-v1.json'])
    assert report['groups']['conjuncts'] == dict(required=146, exact=18, **{'canonical-only':0,'embedded-only':8,'absent':120})
    assert report['groups']['irregular-vowels']['exact'] == 0
    assert report['groups']['digits']['embedded-only'] == 10
    assert report['groups']['alphabet-consonants-and-signs']['exact'] == 27
    assert not report['all_exact']


def test_new_inventory_coverage_is_exact_and_unreviewed(expanded):
    c, o = expanded
    corpus, _, _ = load_oracle(c, o)
    assert len(corpus['cases']) == 261
    assert coverage(INV, [c])['all_exact']
    review = review_template(c, o)
    assert len(review['entries']) == 261
    assert all(e['status'] == 'unreviewed' and e['reviewer'] is None for e in review['entries'])
    assert hashlib.sha256(o.read_bytes()).hexdigest() == ORACLE_SHA


def test_canonical_equivalent_is_not_counted_as_exact(tmp_path):
    c = make_corpus(INV)
    case = next(ca for ca in c['cases'] if ca['text'] == 'ড়')
    case['text'] = '\u09dc'; case['utf8_hex'] = case['text'].encode().hex()
    path = tmp_path/'canonical.json'; path.write_bytes(serialize(c))
    row = next(x for x in coverage(INV, [path])['requirements'] if x['text'] == 'ড়')
    assert row['status'] == 'canonical-only'


@pytest.mark.parametrize('change', ['schema','group','orientation','approval'])
def test_bad_inventory_is_rejected(tmp_path, change):
    data, _ = load_inventory(INV)
    if change == 'schema': data['schema'] = True
    if change == 'group': data['conjunct_groups'] = [['ক']]
    if change == 'orientation': data['attached_forms'][0][2] = 'any'
    if change == 'approval': data['human_review'] = 'approved'
    p = tmp_path/'bad.json'; p.write_text(json.dumps(data,ensure_ascii=False))
    with pytest.raises(ValueError): load_inventory(p)


def test_inventory_cli_outputs_are_guarded(tmp_path):
    p = tmp_path/'new.json'
    assert inventory_main(['build','--inventory',str(INV),'--out',str(p)]) == 0
    assert inventory_main(['build','--inventory',str(INV),'--out',str(p)]) == 2
    o = tmp_path/'oracle.json'
    assert inventory_main(['unpack-oracle','--oracle',str(FROZEN),'--out',str(o)]) == 0
    assert inventory_main(['unpack-oracle','--oracle',str(FROZEN),'--out',str(FROZEN)]) == 2


def test_frozen_reference_decompression_bound(tmp_path):
    p = tmp_path/'large.gz'; p.write_bytes(gzip.compress(b'x'*(8*1024*1024+1),mtime=0))
    with pytest.raises(ValueError,match='8 MiB'): unpack_oracle(p)


@pytest.mark.integration
def test_pinned_supplement_reference(expanded, fonts):
    c,o = expanded
    expected = json.loads(o.read_bytes())
    with HarfBuzz(fonts['regular']) as hb:
        actual = dict(harfbuzz=hb.version, fonttools=fonttools_version,
            python_unicodedata=unicodedata.unidata_version,
            adapter_sha256=hashlib.sha256(Path(adapter.__file__).read_bytes()).hexdigest())
    pinned = actual == expected['toolchain'] and hashlib.sha256(fonts['regular'].read_bytes()).hexdigest() == expected['font']['sha256']
    if not pinned:
        if os.environ.get('BNTEX_REQUIRE_ORACLE') == '1': pytest.fail('Pinned supplementary oracle toolchain/font is required.')
        pytest.skip('Exact supplementary reference requires the pinned oracle toolchain.')
    assert check(c,o,fonts['regular'])['shaped'] == 261


@pytest.mark.integration
def test_all_listed_conjuncts_with_ten_matras_are_behavior_probes(fonts):
    data, _ = load_inventory(INV)
    bases = [x for _, group in data['conjunct_groups'] for x in group.split()]
    signs = ['', *[s for _,s,_ in data['vowels'] if s is not None]]
    count = 0
    with HarfBuzz(fonts['regular']) as hb:
        for base in bases:
            for sign in signs:
                text = base + sign
                assert hb.shape(text) == hb.shape(text)
                count += 1
    assert count == 1606  # Coverage probes, not approved words or an independent shaper.


def run_mine(path, **kwargs):
    return mine(path,INV,source_id='original-test-fixture',revision='fixture-v1',**kwargs)


def test_raw_token_preservation_counts_and_unknown_chains(tmp_path):
    p = tmp_path/'sample.txt'
    p.write_text('পদ্ম পদ্ম ক্ষি ক্\u200dষ ক্\u200cষ ক্খ\nড় ড় স্তু\n',encoding='utf8')
    result = run_mine(p)
    patterns = {r['text']:r for r in result['patterns']}
    assert patterns['দ্ম']['occurrences'] == 2 and patterns['দ্ম']['records'] == 1
    assert patterns['দ্ম']['examples'][0]['word'] == 'পদ্ম'
    raw_words = {r['text']:r for r in result['top_tokens']}
    assert raw_words['ড়']['nfc_group_key'] == raw_words['ড়']['nfc_group_key']
    assert raw_words['ড়']['utf8_hex'] != raw_words['ড়']['utf8_hex']
    chains = {r['text']:r for r in result['maximal_chain_candidates']}
    assert not chains['ক্খ']['listed_exactly'] and chains['ক্\u200cষ']['has_join_control']
    assert result['full_input_consumed'] and result['human_review'] == 'not-performed'


def test_maximal_chains_and_utf8_offsets():
    text = 'আ স্ত্রু ক্\u200cষ'
    spans = chain_spans(text)
    assert [s['text'] for s in spans] == ['স্ত্র','ক্\u200cষ']
    for s in spans:
        assert text.encode()[s['start_byte']:s['end_byte']].decode() == s['text']
    assert chain_spans('ৎ কা ক্') == []


@pytest.mark.parametrize('suffix,compress', [('.txt',lambda b:b),('.gz',gzip.compress),('.xz',lzma.compress),('.bz2',bz2.compress)])
def test_compressed_local_streams(tmp_path,suffix,compress):
    raw = 'ক্ষি\nহৃ\n'.encode(); p=tmp_path/('in'+suffix); p.write_bytes(compress(raw))
    r=run_mine(p)
    assert r['processed_prefix_sha256'] == hashlib.sha256(raw).hexdigest()
    assert r['processed_records'] == 2 and r['script_tokens'] == 2


@pytest.mark.parametrize('fmt,raw,options', [
 ('jsonl','{"text":"প্রেম পদ্ম"}\n',{}),
 ('jsonl','{"content":"প্রেম পদ্ম"}\n',{'text_field':'content'}),
 ('tsv','lemma\tপ্রেম পদ্ম\tV;PRS\n',{'text_column':1}),
])
def test_input_formats(tmp_path,fmt,raw,options):
    p=tmp_path/'in';p.write_text(raw,encoding='utf8')
    r=run_mine(p,fmt=fmt,**options)
    assert r['script_tokens']==2


@pytest.mark.parametrize('fmt,raw', [
 ('text',b'\xff'),('jsonl',b'{"text":"\\ud800"}'),('jsonl',b'{"other":"x"}'),
 ('jsonl',b'{"text":"x","text":"y"}'),('jsonl',b'{"text":NaN}'),
 ('jsonl',b'not-json'),('tsv',b'one-column'),
])
def test_invalid_input_fails_without_repair(tmp_path,fmt,raw):
    p=tmp_path/'bad';p.write_bytes(raw)
    with pytest.raises(ValueError):run_mine(p,fmt=fmt)


def test_limits_do_not_claim_full_corpus(tmp_path):
    p=tmp_path/'in';p.write_text('ক\nখ\nগ\n',encoding='utf8')
    r=run_mine(p,limits=replace(Limits(),records=1))
    assert not r['full_input_consumed'] and r['stop_reason']=='record-limit' and r['script_tokens']==1
    r=run_mine(p,limits=replace(Limits(),decoded_bytes=5))
    assert not r['full_input_consumed'] and r['stop_reason']=='byte-limit' and r['processed_decoded_bytes']==4
    assert r['processed_prefix_sha256']==hashlib.sha256('ক\n'.encode()).hexdigest()


def test_line_and_vocabulary_limits_are_hard_errors(tmp_path):
    p=tmp_path/'in';p.write_text('ক খ',encoding='utf8')
    with pytest.raises(ValueError,match='line limit'):run_mine(p,limits=replace(Limits(),line_bytes=3))
    with pytest.raises(ValueError,match='Unique-word'):run_mine(p,limits=replace(Limits(),unique_words=1))


def test_overlong_tokens_are_explicitly_counted(tmp_path):
    p=tmp_path/'in';p.write_text('ক'*10+' খ',encoding='utf8')
    r=run_mine(p,limits=replace(Limits(),word_scalars=3))
    assert r['overlong_tokens_excluded']==1 and r['script_tokens']==1


def test_mining_cli_does_not_overwrite_inputs_or_reports(tmp_path):
    p=tmp_path/'in';p.write_text('পদ্ম',encoding='utf8');o=tmp_path/'out.json'
    args=['--input',str(p),'--inventory',str(INV),'--source-id','test','--revision','1']
    assert mining_main(args+['--out',str(p)])==2
    assert mining_main(args+['--out',str(o)])==0
    before=o.read_bytes()
    assert mining_main(args+['--out',str(o)])==2 and o.read_bytes()==before


def test_deterministic_mining_and_invalid_limits(tmp_path):
    p=tmp_path/'in';p.write_text('স্তু পদ্ম',encoding='utf8')
    assert run_mine(p)==run_mine(p)
    with pytest.raises(ValueError):run_mine(p,limits=replace(Limits(),records=0))
