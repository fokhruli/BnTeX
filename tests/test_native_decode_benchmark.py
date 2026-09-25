"""The measurement fixture must not mislabel vocabulary or hide output failures."""
from pathlib import Path
import sys
import pytest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))
import native_decode_benchmark as measure

@pytest.mark.parametrize('kind', ['distinct','digits-free','prose','repeated'])
def test_fixture_identity_and_counts(kind):
    src,meta,words = measure.make_source(kind,1,False)
    assert meta['source_sha256'] == measure.perf.sha(src.encode())
    assert meta['token_occurrences'] == len(words)
    assert meta['distinct_tokens'] == len(set(words))
    assert not meta['memo_enabled']
    assert 'bntex-native-memo' not in src
    assert all(w in src for w in words)
    assert src.count(r'\clearpage') == 1
    if kind in {'distinct','digits-free'}:assert len(words)==len(set(words))==96
    if kind=='digits-free':assert not any(ch.isdigit() for w in words for ch in w)

def test_invalid_fixture_inputs_rejected():
    with pytest.raises(ValueError):measure.make_source('unknown',1,False)
    with pytest.raises(ValueError):measure.make_source('distinct',2,False)
    with pytest.raises(ValueError):measure.make_source('distinct',1,1)

def test_probe_uses_continuations_to_exclude_shaping_time_from_decode():
    src,words = measure.probe_source()
    assert len(words)==64
    assert src.count(r'\bnNative{')==8
    assert r'\l__bndp_start_int}#2' in src
    assert r'\l__bndp_start_int}#3' in src
    assert 'bntex-native-memo' not in src
