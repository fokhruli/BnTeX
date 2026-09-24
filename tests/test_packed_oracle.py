from pathlib import Path
import gzip
import json
import pytest
from bntex.inventory import unpack_oracle

FROZEN = Path(__file__).resolve().parents[1] / "corpus/oracles/user-forms-noto-hb10.2.0.json.gz"


def test_packed_reference_detects_changed_rows(tmp_path):
    data = json.loads(gzip.decompress(FROZEN.read_bytes()))
    data['runs'][0][1][0][0] += 1
    p = tmp_path/'changed.gz'; p.write_bytes(gzip.compress(json.dumps(data).encode(),mtime=0))
    with pytest.raises(ValueError,match='digest mismatch'): unpack_oracle(p)
