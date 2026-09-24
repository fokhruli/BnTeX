"""Corpus/oracle invariants. No test fixture constitutes a human review."""
from copy import deepcopy
from pathlib import Path
import json
import os
import random
import subprocess

import pytest
from bntex import corpus as C
from bntex.harfbuzz import HarfBuzz

ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/'corpus/bengali-v1.json'
ORACLE=ROOT/'corpus/oracles/noto-serif-bengali-regular-hb10.2.0.json'
REVIEWS=ROOT/'corpus/reviews/noto-serif-bengali-regular.pending.json'


def put(tmp_path, name, data):
    path=tmp_path/name;path.write_bytes(C.serialize(data));return path


def test_versioned_inventory_and_equivalence_groups():
    corpus,_=C.load_corpus(CORPUS)
    assert len(corpus['cases'])==138 and len(corpus['categories'])==18
    assert sum(c['expect']=='shape' for c in corpus['cases'])==128
    pairs={c['equivalence_group'] for c in corpus['cases'] if 'equivalence_group' in c}
    assert len(pairs)==5
    joined=[c for c in corpus['cases'] if c['category']=='join-controls']
    assert any('\u200d' in c['text'] for c in joined) and any('\u200c' in c['text'] for c in joined)
    assert all(bytes.fromhex(c['utf8_hex']).decode()==c['text'] for c in joined)


@pytest.mark.parametrize('mutation', ['schema','duplicate-id','unknown-category','bad-hex','changed-text',
    'valid-invalid','unknown-outcome','missing-case','bad-equivalence','invalid-with-text','too-long'])
def test_corpus_rejects_bad_inputs(tmp_path, mutation):
    data,_=C.load_corpus(CORPUS)
    if mutation=='schema':data['schema']=True
    elif mutation=='duplicate-id':data['cases'][1]['id']=data['cases'][0]['id']
    elif mutation=='unknown-category':data['cases'][0]['category']='unregistered'
    elif mutation=='bad-hex':data['cases'][0]['utf8_hex']='xx'
    elif mutation=='changed-text':data['cases'][0]['text']='ভিন্ন'
    elif mutation=='valid-invalid':data['cases'][0]['expect']='invalid-utf8'
    elif mutation=='unknown-outcome':data['cases'][0]['expect']='accept-anything'
    elif mutation=='missing-case':data['cases']=[]
    elif mutation=='bad-equivalence':data['cases'][0]['equivalence_group']='singleton'
    elif mutation=='invalid-with-text':
        next(c for c in data['cases'] if c['expect']=='invalid-utf8')['text']='replacement'
    elif mutation=='too-long':data['cases'][0].update(text='ক'*4097,utf8_hex=('ক'*4097).encode().hex())
    with pytest.raises(ValueError):C.load_corpus(put(tmp_path,'bad.json',data))


@pytest.mark.parametrize('raw',[b'{"schema":1,"schema":2}',b'{"a":NaN}',b'{"a":"\xff"}',b'[]'])
def test_json_is_strict(tmp_path,raw):
    p=tmp_path/'bad.json';p.write_bytes(raw)
    with pytest.raises(ValueError):C.read_json(p)


def test_structural_oracle_and_review_work_without_loading_harfbuzz(monkeypatch):
    def forbidden(*a,**kw):raise AssertionError('Library must not load for structural checks')
    monkeypatch.setattr(C,'HarfBuzz',forbidden)
    corpus,oracle,_=C.load_oracle(CORPUS,ORACLE)
    assert len(oracle['records'])==len(corpus['cases'])
    report=C.review_status(CORPUS,ORACLE,REVIEWS)
    assert report['counts']=={'unreviewed':128} and not report['all_accepted']


@pytest.mark.parametrize('mutation',['font-sha','corpus-sha','source-sha','config','fields','order','missing-row',
                                     'claim-human','float-gid','bad-cluster','bad-flag','rejected-glyphs'])
def test_oracle_provenance_and_structure_are_validated(tmp_path,mutation):
    _,data,_=C.load_oracle(CORPUS,ORACLE)
    if mutation=='font-sha':data['font']['sha256']='not-a-hash'
    elif mutation=='corpus-sha':data['corpus_sha256']='0'*64
    elif mutation=='source-sha':data['records'][0]['source_sha256']='0'*64
    elif mutation=='config':data['config']['cluster_level']=1
    elif mutation=='fields':data['glyph_fields']=list(reversed(C.FIELDS))
    elif mutation=='order':data['records'][0],data['records'][1]=data['records'][1],data['records'][0]
    elif mutation=='missing-row':data['records'].pop()
    elif mutation=='claim-human':data['human_review']='approved'
    elif mutation=='float-gid':data['records'][0]['glyphs'][0][0]=1.0
    elif mutation=='bad-cluster':data['records'][0]['glyphs'][0][1]=1
    elif mutation=='bad-flag':data['records'][0]['glyphs'][0][6]=128
    elif mutation=='rejected-glyphs':data['records'][-1]['glyphs']=[]
    with pytest.raises(ValueError):C.load_oracle(CORPUS,put(tmp_path,'bad.json',data))


@pytest.mark.parametrize('field',range(7))
def test_fault_injection_detects_each_glyph_field(field):
    _,expected,_=C.load_oracle(CORPUS,ORACLE);actual=deepcopy(expected)
    actual['records'][0]['glyphs'][0][field]+=1
    errors=C.compare(expected,actual)
    assert any(C.FIELDS[field] in e for e in errors)


@pytest.mark.parametrize('mutation',['truncated-glyph','boolean-gid','extra-record-field'])
def test_differential_comparison_cannot_ignore_structure(mutation):
    _,expected,_=C.load_oracle(CORPUS,ORACLE);actual=deepcopy(expected)
    if mutation=='truncated-glyph':actual['records'][0]['glyphs'][0].pop()
    elif mutation=='boolean-gid':actual['records'][0]['glyphs'][0][0]=True
    else:actual['records'][0]['unexpected']='field'
    assert C.compare(expected,actual)


@pytest.mark.parametrize('field',['harfbuzz','fonttools','python_unicodedata','adapter_sha256'])
def test_toolchain_changes_are_not_silently_accepted(field):
    _,expected,_=C.load_oracle(CORPUS,ORACLE);actual=deepcopy(expected)
    actual['toolchain'][field]='changed'
    assert 'provenance.toolchain: mismatch' in C.compare(expected,actual)


def test_review_template_matches_tracked_pending_data():
    tracked,_=C.read_json(REVIEWS)
    assert C.review_template(CORPUS,ORACLE)==tracked
    assert all(e['reviewer'] is None and e['date'] is None for e in tracked['entries'])


@pytest.mark.parametrize('mutation',['missing-reviewer','bad-date','not-human','no-notes','open-variants',
                                     'stale-oracle','reordered','unreviewed-attribution','boolean-schema','bad-status'])
def test_review_cannot_silently_certify_missing_or_stale_evidence(tmp_path,mutation):
    data=C.review_template(CORPUS,ORACLE);e=data['entries'][0]
    # Fictional test data, never written into tracked review evidence.
    e.update(status='accepted',reviewer='Fictional unit-test reviewer',reviewer_kind='human',
             date='2026-09-23',notes='Synthetic test fixture; not an actual human review.')
    if mutation=='missing-reviewer':e['reviewer']=None
    elif mutation=='bad-date':e['date']='2026-02-30'
    elif mutation=='not-human':e['reviewer_kind']='machine'
    elif mutation=='no-notes':e['notes']=''
    elif mutation=='open-variants':e['unresolved_variants']=['Not yet resolved']
    elif mutation=='stale-oracle':data['oracle_sha256']='0'*64
    elif mutation=='reordered':data['entries'].reverse()
    elif mutation=='unreviewed-attribution':e['status']='unreviewed'
    elif mutation=='boolean-schema':data['schema']=True
    elif mutation=='bad-status':e['status']=[]
    with pytest.raises(ValueError):C.review_status(CORPUS,ORACLE,put(tmp_path,'reviews.json',data))


def test_review_release_gate_reports_pending_without_a_traceback(capsys):
    args=['review-status','--corpus',str(CORPUS),'--oracle',str(ORACLE),'--reviews',str(REVIEWS)]
    assert C.main(args)==0
    assert not json.loads(capsys.readouterr().out)['all_accepted']
    assert C.main(args+['--require-approved'])==1
    assert json.loads(capsys.readouterr().out)['counts']['unreviewed']==128


def test_safe_writes_and_source_protection(tmp_path,capsys):
    p=tmp_path/'data.json';C.write_output(p,b'original')
    with pytest.raises(FileExistsError):C.write_output(p,b'changed')
    assert p.read_bytes()==b'original'
    C.write_output(p,b'changed',force=True);assert p.read_bytes()==b'changed'
    link=tmp_path/'link';link.symlink_to(p)
    with pytest.raises(ValueError):C.write_output(link,b'bad',force=True)
    assert p.read_bytes()==b'changed'
    raw=CORPUS.read_bytes()
    assert C.main(['review-template','--corpus',str(CORPUS),'--oracle',str(ORACLE),
                   '--out',str(CORPUS),'--force'])==2
    assert CORPUS.read_bytes()==raw and 'replace an input' in capsys.readouterr().err


def test_review_tex_contains_all_cases_and_keeps_controls():
    text=C.review_tex(CORPUS,ORACLE)
    cases,_=C.load_corpus(CORPUS)
    assert all(c['id'] in text for c in cases['cases'])
    assert '\u200d' in text and '\u200c' in text
    assert 'not been performed' in text and '\t' not in text


@pytest.mark.integration
def test_dynamic_oracle_roundtrip_and_real_fault_injection(tmp_path,fonts):
    first=C.record(CORPUS,fonts['regular']);second=C.record(CORPUS,fonts['regular'])
    assert C.serialize(first)==C.serialize(second)
    p=put(tmp_path,'oracle.json',first)
    assert C.check(CORPUS,p,fonts['regular'])['cases']==138
    original=p.read_bytes()
    first['records'][0]['glyphs'][0][2]+=1  # Valid structure, incorrect font-unit advance.
    p.write_bytes(C.serialize(first))
    corrupted=p.read_bytes()
    with pytest.raises(ValueError,match='x_advance'):C.check(CORPUS,p,fonts['regular'])
    assert p.read_bytes()==corrupted and corrupted!=original  # Checking never rebaselines.


@pytest.mark.integration
def test_exact_pinned_reference(fonts):
    _,expected,_=C.load_oracle(CORPUS,ORACLE)
    actual=C.record(CORPUS,fonts['regular'])
    environment={k:actual[k] for k in ('font','toolchain')}
    required={k:expected[k] for k in ('font','toolchain')}
    if environment!=required and os.environ.get('BNTEX_REQUIRE_ORACLE')!='1':
        pytest.skip('Pinned font/toolchain differs; run the pinned-oracle workflow (not a passing oracle gate).')
    assert C.check(CORPUS,ORACLE,fonts['regular'])['status']=='exact-match'


@pytest.mark.integration
def test_deterministic_generated_behavior_probes_and_byte_clusters(fonts):
    rng=random.Random(731)
    consonants=['ক','গ','ত','দ','ন','ম','র','স']
    suffixes=['','া','ি','ু','ে','ো','্ক','্র','্য','্\u200dষ','্\u200cষ','ঁ']
    probes=[rng.choice(consonants)+rng.choice(suffixes) for _ in range(192)]
    # These are behavior probes, not a claim that every constructed form is a word.
    with HarfBuzz(fonts['regular']) as hb:
        for text in probes:
            first=hb.shape(text);assert first==hb.shape(text)
            boundaries={len(text[:i].encode('utf8')) for i in range(len(text))}
            assert all(g.cluster in boundaries for g in first)
        with pytest.raises(ValueError):hb.shape('ক'*4097)
        with pytest.raises(ValueError):hb.shape('ক\0খ')


@pytest.mark.integration
def test_review_sheet_compiles_and_preserves_original_unicode(tmp_path,fonts,tex_tools):
    from bntex.build import prepare
    source=tmp_path/'review.tex';source.write_text(C.review_tex(CORPUS,ORACLE),encoding='utf8')
    out=tmp_path/'pdf';prepare([source],{'regular':fonts['regular']},out)
    for _ in range(2):
        subprocess.run(['pdflatex','-no-shell-escape','-halt-on-error','-interaction=batchmode','review.tex'],
                       cwd=out,check=True,capture_output=True,timeout=40)
    text=subprocess.run(['pdftotext','review.pdf','-'],cwd=out,check=True,capture_output=True).stdout.decode('utf8')
    for literal in ['স্বাস্থ্য','প্রযুক্তি','ক্\u200dষ','ক্\u200cষ','\u09dc','\u09a1\u09bc']:
        assert literal in text


@pytest.mark.integration
def test_review_build_checks_reference_before_emitting_assets(tmp_path,fonts,tex_tools):
    data=C.record(CORPUS,fonts['regular']);p=put(tmp_path,'oracle.json',data)
    out=tmp_path/'review-project'
    assert C.prepare_review(CORPUS,p,fonts['regular'],out)['reference_check']=='exact-match'
    original=(out/'review.tex').read_bytes()
    data['toolchain']['harfbuzz']='incorrect-version';p.write_bytes(C.serialize(data))
    with pytest.raises(ValueError,match='toolchain'):
        C.prepare_review(CORPUS,p,fonts['regular'],out)
    assert (out/'review.tex').read_bytes()==original
    with pytest.raises(ValueError,match='replace any input'):
        C.prepare_review(CORPUS,p,fonts['regular'],tmp_path)
