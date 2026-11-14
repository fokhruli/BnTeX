"""Release completeness and rebuild from the distribution's own source tree."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from bntex import distribution as d
from test_installed_distribution import tds, ROOT, REG, BOLD


@pytest.mark.parametrize('name', [
    d.TEX_DIR+'/bntex.sty',
    d.TEX_DIR+'/bntex-default-profile.def',
    d.TEX_DIR+'/bntex-auto.sty',
    d.TEX_DIR+'/bntex-native-bold.def',
    d.TEX_DIR+'/bntex-native-matchers.def',
    d.DOC_DIR+'/OFL-1.1.txt',
    d.DOC_DIR+'/FONT-NOTICES.md',
    d.DOC_DIR+'/bntex-manual.pdf',
    d.DOC_DIR+'/bntex-manual.tex',
    d.SOURCE_DIR+'/bntex/distribution.py',
    d.SOURCE_DIR+'/bntex/native_profile.py',
    d.SOURCE_DIR+'/REPRODUCING.md',
    *[d.tds_path('bnf'+d.FONT_SHA[:16]+'b0'+s) for s in ('.tfm','.enc')],
])
def test_omitting_file_and_its_inventory_record_is_not_complete(tds, tmp_path, name):
    tree=tmp_path/'tree';shutil.copytree(tds,tree)
    mp=tree/d.DOC_DIR/'distribution-manifest.json'
    m=json.loads(mp.read_text());(tree/name).unlink();m['files'].pop(name)
    mp.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Incomplete or unexpected distribution inventory'):
        d.verify(tree)
    with pytest.raises(ValueError):d.pack(tree,tmp_path/'archive')
    assert not (tmp_path/'archive').exists()


@pytest.mark.parametrize('name', ['extra.txt','fonts/truetype/public/bntex/other.ttf'])
def test_manifest_cannot_authorize_unknown_distribution_members(tds,tmp_path,name):
    tree=tmp_path/'tree';shutil.copytree(tds,tree)
    p=tree/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'not an allowed asset')
    mp=tree/d.DOC_DIR/'distribution-manifest.json';m=json.loads(mp.read_text())
    m['files'][name]=d.sha(p.read_bytes());mp.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Incomplete or unexpected'):d.verify(tree)


@pytest.mark.parametrize('key,value', [('runtime_python',True),('runtime_shell',True),
    ('runtime_python',0),('version','different'),('publication_authorized',True),
    ('browser_test','passed')])
def test_candidate_contract_cannot_be_changed_in_manifest(tds,tmp_path,key,value):
    tree=tmp_path/'tree';shutil.copytree(tds,tree)
    mp=tree/d.DOC_DIR/'distribution-manifest.json';m=json.loads(mp.read_text())
    m[key]=value;mp.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Unsupported distribution identities'):d.verify(tree)


@pytest.mark.parametrize('name,message', [
    (d.DOC_DIR+'/OFL-1.1.txt','Complete pinned font license'),
    (d.DOC_DIR+'/bntex-manual.pdf','Compiled PDF manual'),
    (d.SOURCE_DIR+'/bntex/data/bntex-auto.sty','Runtime/source module mismatch'),
    (d.TEX_DIR+'/bntex-native-profile.tex','Default/explicit installed loaders differ'),
    (d.TEX_DIR+'/bntex-default-profile.def','Installed loader does not pin the installed files'),
    (d.TEX_DIR+'/bntex-native-tounicode.def','Installed loader does not pin the installed files')])
def test_rehashed_inconsistent_artifact_is_rejected(tds,tmp_path,name,message):
    tree=tmp_path/'tree';shutil.copytree(tds,tree)
    p=tree/name;p.write_bytes(b'replacement')
    mp=tree/d.DOC_DIR/'distribution-manifest.json';m=json.loads(mp.read_text())
    m['files'][name]=d.sha(p.read_bytes());mp.write_text(json.dumps(m))
    with pytest.raises(ValueError,match=message):d.verify(tree)


def test_even_unlisted_broken_symlink_is_rejected(tds,tmp_path):
    tree=tmp_path/'tree';shutil.copytree(tds,tree)
    try:(tree/'dangling').symlink_to(tmp_path/'does-not-exist')
    except OSError:pytest.skip('Symlink creation not supported')
    with pytest.raises(ValueError,match='Symlinks'):d.verify(tree)


def test_documented_rebuild_runs_from_shipped_sources(tds,tmp_path):
    # Use the actual maintainer builder, including its stable two-pass manual.
    built=tmp_path/'built'
    build=subprocess.run([sys.executable,str(ROOT/'tools/build_distribution.py'),
                          '--out',str(built),'--regular-font',str(REG),
                          '--bold-font',str(BOLD)],cwd=tmp_path,
                         env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),
                         capture_output=True,text=True,timeout=120)
    assert build.returncode==0,build.stdout+build.stderr
    tds=built/'texmf'
    original=d.verify(tds)
    # No checkout PYTHONPATH: import and execute only the shipped build source.
    env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    source=tds/d.SOURCE_DIR
    probe=subprocess.check_output([sys.executable,'-B','-c','import bntex; print(bntex.__file__)'],
                                  cwd=source,env=env,text=True,timeout=10).strip()
    assert Path(probe).resolve()==(source/'bntex/__init__.py').resolve()
    out=tmp_path/'rebuilt'
    run=subprocess.run([sys.executable,'-B','-m','bntex.distribution','rebuild',
                        '--root','../../..','--out',str(out)],cwd=source,env=env,
                       capture_output=True,text=True,timeout=120)
    assert run.returncode==0,run.stdout+run.stderr
    report=json.loads(run.stdout)
    assert report['source_rebuild']=='exact-match'
    assert d.verify(out/'texmf')==original==d.verify(tds)
    reference=d.pack(tds,tmp_path/'reference-archives')
    assert report['archives']==reference['archives']
    assert not report['release_ready'] and not report['publication_performed']
    # Rebuild must not overwrite existing work, even when its input is valid.
    again=subprocess.run([sys.executable,'-B','-m','bntex.distribution','rebuild',
                          '--root','../../..','--out',str(out)],cwd=source,env=env,
                         capture_output=True,text=True,timeout=15)
    assert again.returncode==2 and 'fresh nonsymlink' in again.stderr
    assert d.verify(out/'texmf')==original


def test_rebuild_rejects_wrong_source_checkout(tds,tmp_path):
    tree=tmp_path/'tree';shutil.copytree(tds,tree)
    name=d.SOURCE_DIR+'/bntex/distribution.py'
    p=tree/name;p.write_bytes(p.read_bytes()+b'\n# Different shipped build source\n')
    mp=tree/d.DOC_DIR/'distribution-manifest.json';m=json.loads(mp.read_text())
    m['files'][name]=d.sha(p.read_bytes());mp.write_text(json.dumps(m))
    # Ordinary verification is structural/integrity, not source authentication.
    d.verify(tree)
    with pytest.raises(ValueError,match='sources shipped with this distribution'):
        d.rebuild(tree,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_source_inventory_covers_the_actual_package():
    actual={p.name for p in (ROOT/'src/bntex').glob('*.py')}
    assert set(d.SOURCE_MODULES)==actual
    assert r'\usepackage{bntex}' in d.REBUILD_GUIDE.decode('ascii')
    assert '../../..' in d.REBUILD_GUIDE.decode('ascii')
