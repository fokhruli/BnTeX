"""Fail-closed cleanup planning, including real atomic Git lease behavior."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bntex_cleanup',ROOT/'tools/cleanup_merged_branches.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
A, B = 'a'*40, 'b'*40

def request():
    return {'schema':1,'repository':'fokhruli/BnTeX','based_on_main':A,
            'branches':[{'name':'feat/old','sha':B}]}

@pytest.mark.parametrize('field,value', [('schema',True),('schema',2),('repository','other/repo'),
 ('based_on_main','-x'),('branches',[]),('branches',[{'name':'main','sha':B}]),
 ('branches',[{'name':'feat/a:b','sha':B}]),('branches',[{'name':'feat/old','sha':'x'}]),
 ('branches',[{'name':'feat/old','sha':B,'extra':True}])])
def test_invalid_request(field,value):
    r=request();r[field]=value
    with pytest.raises(ValueError):c.validate_request(r)

def test_duplicate_and_unknown_fields():
    r=request();r['branches']*=2
    with pytest.raises(ValueError):c.validate_request(r)
    r=request();r['extra']=1
    with pytest.raises(ValueError):c.validate_request(r)

@pytest.mark.parametrize('live,pulls,ancestor,decision',[
 ({},[],True,'absent'),
 ({'feat/old':{'sha':B,'protected':True}},[],True,'protected'),
 ({'feat/old':{'sha':A,'protected':False}},[],True,'tip-changed'),
 ({'feat/old':{'sha':B,'protected':False}},[{'head':{'ref':'feat/old'}}],True,'open-pr-dependency'),
 ({'feat/old':{'sha':B,'protected':False}},[{'base':{'ref':'feat/old'}}],True,'open-pr-dependency'),
 ({'feat/old':{'sha':B,'protected':False}},[],False,'not-ancestor-of-main'),
 ({'feat/old':{'sha':B,'protected':False}},[],True,'eligible'),
])
def test_decision_guards(live,pulls,ancestor,decision):
    rows=c.plan(request(),live,pulls,lambda _:ancestor)
    assert rows[0]['decision']==decision
    assert bool(c.deletion_command(rows))==(decision=='eligible')

def test_does_not_discover_extra_candidates():
    live={name:{'sha':B,'protected':False} for name in ('feat/old','feat/new')}
    assert len(c.plan(request(),live,[],lambda _:True))==1

def test_bad_deletion_ref_is_rejected():
    with pytest.raises(ValueError):
        c.deletion_command([{'name':'main','sha':B,'decision':'eligible'}])

def test_atomic_lease_refuses_concurrent_updates(tmp_path):
    def run(args,cwd=None,check=True):
        return subprocess.run(['git',*args],cwd=cwd,text=True,capture_output=True,check=check)
    remote=tmp_path/'remote.git'; work=tmp_path/'work'
    run(['init','--bare',str(remote)]);run(['init',str(work)])
    run(['config','user.name','Test'],work);run(['config','user.email','test@example.invalid'],work)
    (work/'a').write_text('a');run(['add','.'],work);run(['commit','-m','base'],work)
    base=run(['rev-parse','HEAD'],work).stdout.strip()
    run(['remote','add','origin',str(remote)],work)
    run(['push','origin','HEAD:refs/heads/feat/one','HEAD:refs/heads/feat/two'],work)
    (work/'a').write_text('b');run(['commit','-am','concurrent'],work)
    advanced=run(['rev-parse','HEAD'],work).stdout.strip()
    run(['push','origin','HEAD:refs/heads/feat/two'],work)
    rows=[{'name':n,'sha':base,'decision':'eligible'} for n in ('feat/one','feat/two')]
    failed=run(c.deletion_command(rows)[1:],work,check=False)
    assert failed.returncode!=0
    refs=run(['ls-remote','--heads','origin'],work).stdout
    assert 'refs/heads/feat/one' in refs and advanced in refs
    rows[1]['sha']=advanced
    run(c.deletion_command(rows)[1:],work)
    assert run(['ls-remote','--heads','origin'],work).stdout==''

def test_workflow_is_manual_request_scoped():
    text=(ROOT/'.github/workflows/branch-cleanup.yml').read_text()
    assert 'branches: [main]' in text
    assert '.github/maintenance/branch-cleanup-request.json' in text
    assert 'contents: write' in text and 'pull-requests: read' in text
    assert 'persist-credentials: false' in text
    assert 'schedule:' not in text and 'pull_request_target:' not in text
